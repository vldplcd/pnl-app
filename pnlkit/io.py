# io.py
from __future__ import annotations
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Sequence

import pandas as pd

from .models import ActionEvent, Fill, Order
from .types import Action, Side

import logging
logger = logging.getLogger("pnlkit.io")

_VALID_SEQUENCES = [
    ("sent", "placed", "filled"),
    ("sent", "placed", "cancelling", "cancelled"),
    ("placed", "filled"),
    ("sent", "filled"),
]

def _to_dec_or_none(x) -> Optional[Decimal]:
    if x is None:
        return None
    s = str(x).strip()
    if s in {"", "nan", "NaN", "None"}:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError, TypeError):
        return None

def read_orders_from_csv(path: str) -> List[Order]:
    """
    Read CSV logs and reconstruct validated Order objects.

    Expected columns:
      currentTime;action;orderId;orderProduct;orderSide;tradePx;tradeAmt
    """
    df = pd.read_csv(
        path,
        sep=";",
        dtype={
            "orderId": str,
            "orderProduct": str,
            "orderSide": str,
            "action": str,
        },
        # СРАЗУ конвертим цены/объёмы в Decimal/None — никаких конвертаций в циклах ниже.
        converters={
            "tradePx": _to_dec_or_none,
            "tradeAmt": _to_dec_or_none,
        },
        keep_default_na=True,
    )

    # Векторная нормализация
    df["currentTime"] = pd.to_datetime(df["currentTime"], unit="ns", utc=True)
    df["action"] = df["action"].str.lower()
    df["orderSide"] = df["orderSide"].str.lower()
    df["orderProduct"] = df["orderProduct"].str.upper()

    orders: List[Order] = []
    for order_id, grp in df.groupby("orderId", sort=False):
        # сортируем один раз, стабильная сортировка
        grp = grp.sort_values("currentTime", kind="mergesort")

        # Заголовки и типы
        side = Side(grp.iloc[0]["orderSide"])
        product = str(grp.iloc[0]["orderProduct"])

        # Забираем нужные столбцы как массивы NumPy (быстрее, чем apply/itertuples)
        ts_arr   = grp["currentTime"].to_numpy()
        act_arr  = grp["action"].to_numpy()
        px_arr   = grp["tradePx"].to_numpy()
        amt_arr  = grp["tradeAmt"].to_numpy()

        # Сбор событий без конвертаций внутри цикла
        evs: List[ActionEvent] = [
            ActionEvent(
                ts=ts_arr[i].to_pydatetime(),
                action=Action(act_arr[i]),
                trade_px=px_arr[i],
                trade_amt=amt_arr[i],
            )
            for i in range(len(grp))
        ]

        # Валидация последовательности статусов (как у тебя по смыслу)
        seq = tuple(a.action.value for a in evs)
        if seq not in _VALID_SEQUENCES:
            logger.warning(
                "Skipping order %s due to invalid action sequence: %s",
                str(order_id), "|".join(seq),
            )
            continue
        orders.append(Order(order_id=str(order_id), product=product, side=side, events=evs))

    return orders

def orders_to_fills(orders: Sequence[Order]) -> List[Fill]:
    """Convert validated Orders into Fill executions (может быть несколько FILLED на ордер)."""
    fills: List[Fill] = []
    for o in orders:
        for ev in o.events:
            if ev.action == Action.FILLED and ev.trade_px is not None and ev.trade_amt is not None:
                fills.append(
                    Fill(
                        ts=ev.ts,
                        product=o.product,
                        side=o.side,
                        price=ev.trade_px,
                        qty=ev.trade_amt,
                    )
                )
    fills.sort(key=lambda f: f.ts)
    return fills
