#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PnL Web UI (Streamlit)
Run:
    streamlit run web-ui.py
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Tuple

import pandas as pd
import altair as alt
import streamlit as st

# --- Imports from package or local modules ---
try:
    from pnlkit.io import read_orders_from_csv, orders_to_fills
    from pnlkit.engine import PnLEngine
    from pnlkit.strategies import get_strategy
except Exception:
    # fallback for local repo layout
    from io import read_orders_from_csv, orders_to_fills       # type: ignore
    from engine import PnLEngine                               # type: ignore
    from strategies import get_strategy                         # type: ignore


# ===== INITIAL POSITIONS LOADING (adapted from run.py) =====
def load_initial_positions_like_cli(json_bytes: bytes) -> Dict[str, Dict[str, Any]]:
    """
    Expected format:
    {
        "AAPL": {"qty": 100, "avg_price": 150.50},
        "GOOGL": {"qty": -50, "avg_price": 2800.00, "timestamp": "2024-01-01T09:00:00"}
    }
    """
    from datetime import datetime

    positions = json.loads(json_bytes.decode("utf-8", errors="ignore"))
    if not isinstance(positions, dict):
        raise ValueError("JSON root must be an object/dict")

    for symbol, data in positions.items():
        if "qty" not in data or "avg_price" not in data:
            raise ValueError(f"Missing fields for {symbol}: need qty and avg_price")

        # normalize/validate
        data["qty"] = float(data["qty"])
        price = float(data["avg_price"])
        if price <= 0:
            raise ValueError(f"avg_price for {symbol} must be positive")
        data["avg_price"] = price

        if "timestamp" in data and isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
    return positions


# ===== UI =====
st.set_page_config(page_title="PnL Dashboard", layout="wide")
st.title("📊 PnL Dashboard")
st.caption("Ready to buid PnL Dashboard over your CSV!")

with st.sidebar:
    st.header("Input Data")
    csv_file = st.file_uploader("Trades CSV (semicolon-separated)", type=["csv"])
    init_json = st.file_uploader("Initial Positions JSON (optional)", type=["json"])
    strategy_name = st.selectbox("Lot selection strategy", ["FIFO", "LIFO"], index=0)
    top_n_positions = st.number_input("Positions to show in snapshot (top N)", min_value=1, max_value=200, value=20)
    normalize_scales = st.checkbox(
        "Normalize scales",
        value=False,
        help="On: left (bars) and right (line) axes have separate symmetric domains.\n"
             "Off: both axes share one symmetric domain so zero lines align exactly."
    )
    st.markdown("---")
    st.markdown(
        "<p style='text-align: left; font-size: 0.85em;'>"
        "Developed by "
        "<a href='https://www.linkedin.com/in/vladimir-shilov-215993163/' target='_blank'>Vladimir Shilov</a>"
        "<br>"
        "<a href='https://t.me/vldplcd' target='_blank'>Telegram</a>"
        "</p>",
        unsafe_allow_html=True
    )

if not csv_file:
    st.info("⬅️ Upload a CSV to get started.")
    st.stop()

# --- Read CSV via pnlkit.io.read_orders_from_csv (expects a path) ---
with tempfile.NamedTemporaryFile(prefix="pnl_csv_", suffix=".csv", delete=False) as tf:
    tf.write(csv_file.read())
    csv_tmp_path = tf.name

try:
    orders = read_orders_from_csv(csv_tmp_path)
    fills = orders_to_fills(orders)
except Exception as e:
    st.error(f"Error parsing CSV: {e}")
    st.stop()
finally:
    try:
        Path(csv_tmp_path).unlink(missing_ok=True)
    except Exception:
        pass

if not fills:
    st.warning("No valid FILLED entries found in CSV — nothing to calculate.")
    st.stop()

# --- Engine ---
engine = PnLEngine(strategy=get_strategy(strategy_name))

initial_positions_ui = None
# --- Initial positions ---
if init_json is not None:
    try:
        positions = load_initial_positions_like_cli(init_json.read())
        engine.set_initial_positions_from_dict(positions)
        initial_positions_ui = positions  # keep for displaying in UI
    except Exception as e:
        st.warning(f"Initial positions not applied: {e}")

# --- Calculation ---
result = engine.process_fills(fills)
df: pd.DataFrame = result.df  # columns include: ts, symbol, realized_total, unrealized_total, gross_total, gross_symbol, gross_total_symbol

# --- Initial Positions
if initial_positions_ui:
    st.markdown("### Initial Positions (from JSON)")
    init_df = (
        pd.DataFrame.from_dict(initial_positions_ui, orient="index")
            .rename_axis("symbol")
            .reset_index()
    )
    # derived columns for readability
    init_df["side"] = init_df["qty"].apply(lambda q: "long" if q >= 0 else "short")
    init_df["abs_qty"] = init_df["qty"].abs()
    cols = ["symbol", "side", "abs_qty", "avg_price"]
    st.dataframe(init_df[cols], use_container_width=True)

# ===== KPIs =====
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Realized PnL (total)", f"{result.realized_total():,.2f}")
with c2:
    st.metric("Unrealized PnL (total)", f"{result.unrealized_total():,.2f}")
with c3:
    st.metric("Gross PnL (total)", f"{result.total_gross():,.2f}")

# ===== Additional KPIs from realized deltas =====
k = result.kpis() if hasattr(result, "kpis") else {}
wr = float(k.get("win_rate", 0.0))
pf = k.get("profit_factor", 0.0)
atp = k.get("average_trade_pnl", 0.0)

c4, c5, c6 = st.columns(3)
with c4:
    # delta vs 50% to give green/red arrow automatically
    st.metric("Win Rate", f"{wr*100:.1f}%", delta=f"{(wr-0.5)*100:+.1f} pp")
with c5:
    # delta vs 1.00 baseline
    if pf == float("inf"):
        pf_str, delta_str = "∞", "+∞"
    else:
        pf_str, delta_str = f"{pf:.2f}", f"{pf-1.0:+.2f}"
    st.metric("Profit Factor", pf_str, delta=delta_str)
with c6:
    # sign-based delta; value itself carries the sign
    st.metric("Avg Trade PnL", f"{atp:,.2f}", delta=f"{atp:,.2f}")

st.markdown("### Positions Snapshot")
st.code(result.positions_string(top_n=int(top_n_positions)), language=None)


# ===== Helpers for axis domains =====
def symmetric_domain_from_cols(data: pd.DataFrame, cols: List[str]) -> Tuple[float, float]:
    """Return a symmetric domain [-M, M] where M is max abs across given columns."""
    max_abs = 0.0
    for c in cols:
        if c in data.columns and not data[c].dropna().empty:
            s = data[c].astype(float)
            local = max(abs(float(s.min())), abs(float(s.max())))
            if local > max_abs:
                max_abs = local
    M = max(max_abs, 1e-9)  # avoid zero-height domain
    return (-M * 1.05, M * 1.05)  # small pad


# ===== Charts (Altair) =====
st.markdown("### Charts")

def portfolio_chart(data: pd.DataFrame, normalize: bool) -> alt.Chart:
    # Decide domains
    if normalize:
        dom_left = symmetric_domain_from_cols(data, ["gross_symbol"])
        dom_right = symmetric_domain_from_cols(data, ["gross_total"])
    else:
        shared = symmetric_domain_from_cols(data, ["gross_symbol", "realized_total", "unrealized_total", "gross_total"])
        dom_left = dom_right = shared

    base = alt.Chart(data).encode(
        x=alt.X("ts:T", title="Time", axis=alt.Axis(labelOverlap="greedy", tickCount=8))
    )

    # Bars: instant PnL (left y)
    bars = base.mark_bar(opacity=0.85).encode(
        y=alt.Y(
            "gross_symbol:Q",
            title="PnL (instant)",
            scale=alt.Scale(domain=list(dom_left)),
            axis=alt.Axis(labelOverlap=True, tickCount=6)
        ),
        color=alt.condition("datum.gross_symbol >= 0", alt.value("#32CD32"), alt.value("#FF4500")),
        tooltip=[
            alt.Tooltip("ts:T", title="Time"),
            alt.Tooltip("gross_symbol:Q", title="PnL (instant)", format=",.2f")
        ],
    )

    # Line + area: cumulative gross (right y)
    line = base.mark_line(strokeWidth=2.5, point=False).encode(
        y=alt.Y(
            "gross_total:Q",
            axis=alt.Axis(title="Cumulative Gross PnL", orient="right", titlePadding=28, labelOverlap=True, tickCount=6),
            scale=alt.Scale(domain=list(dom_right))
        ),
        tooltip=[
            alt.Tooltip("ts:T", title="Time"),
            alt.Tooltip("gross_total:Q", title="Gross (cumulative)", format=",.2f"),
            alt.Tooltip("realized_total:Q", title="Realized (cumulative)", format=",.2f"),
            alt.Tooltip("unrealized_total:Q", title="Unrealized", format=",.2f"),
        ],
    )

    area = base.mark_area(opacity=0.18).encode(
        y=alt.Y("gross_total:Q", scale=alt.Scale(domain=list(dom_right)))
    )

    layered = alt.layer(bars, area, line).resolve_scale(
        y="independent"  # twin axes, with domains set above
    ).properties(
        width="container",
        height=420,
        title="Portfolio PnL Overview"
    )

    # --- interactive hover selection ---
    nearest = alt.selection_point(nearest=True, on="pointermove", fields=["ts"], empty=False)
    selectors = base.mark_point().encode(x="ts:T").add_params(nearest)

    # --- annotations bound to proper axes ---
    vline = base.mark_rule(color="gray").encode(x="ts:T").transform_filter(nearest)

    line_point = base.mark_circle(size=64).encode(
        y=alt.Y("gross_total:Q", axis=None, scale=alt.Scale(domain=list(dom_right)))
    ).transform_filter(nearest)

    line_text = base.mark_text(align="left", color="var(--text-color)", dx=6, dy=-6).encode(
        y=alt.Y("gross_total:Q", axis=None, scale=alt.Scale(domain=list(dom_right))),
        text=alt.Text("gross_total:Q", format=",.2f"),
    ).transform_filter(nearest)

    bar_text = base.mark_text(dy=-6, color="var(--text-color)", baseline="bottom").encode(
        y=alt.Y("gross_symbol:Q", axis=None, scale=alt.Scale(domain=list(dom_left))),
        text=alt.Text("gross_symbol:Q", format=",.2f"),
    ).transform_filter(nearest)

    return alt.layer(layered, selectors, vline, line_point, line_text, bar_text)


st.altair_chart(portfolio_chart(df, normalize_scales), use_container_width=True)


def per_symbol_chart(g: pd.DataFrame, sym: str, normalize: bool) -> alt.Chart:
    if normalize:
        dom_left = symmetric_domain_from_cols(g, ["gross_symbol"])
        dom_right = symmetric_domain_from_cols(g, ["gross_total_symbol"])
    else:
        shared = symmetric_domain_from_cols(g, ["gross_symbol", "gross_total_symbol"])
        dom_left = dom_right = shared

    base = alt.Chart(g).encode(
        x=alt.X("ts:T", title="Time", axis=alt.Axis(labelOverlap="greedy", tickCount=8))
    )

    bars = base.mark_bar(opacity=0.85).encode(
        y=alt.Y(
            "gross_symbol:Q",
            title="PnL (instant)",
            scale=alt.Scale(domain=list(dom_left)),
            axis=alt.Axis(labelOverlap=True, tickCount=6)
        ),
        color=alt.condition("datum.gross_symbol >= 0", alt.value("#32CD32"), alt.value("#FF4500")),
        tooltip=[
            alt.Tooltip("ts:T", title="Time"),
            alt.Tooltip("gross_symbol:Q", title="PnL (instant)", format=",.2f"),
        ],
    )

    line = base.mark_line(strokeWidth=2.5, point=False).encode(
        y=alt.Y(
            "gross_total_symbol:Q",
            axis=alt.Axis(title="Cumulative Gross PnL", orient="right", titlePadding=26, labelOverlap=True, tickCount=6),
            scale=alt.Scale(domain=list(dom_right))
        ),
        tooltip=[
            alt.Tooltip("ts:T", title="Time"),
            alt.Tooltip("gross_total_symbol:Q", title="Gross (cum)", format=",.2f"),
        ],
    )

    area = base.mark_area(opacity=0.18).encode(
        y=alt.Y("gross_total_symbol:Q", scale=alt.Scale(domain=list(dom_right)))
    )

    layered = alt.layer(bars, area, line).resolve_scale(y="independent").properties(
        width="container",
        height=360,
        title=f"{sym} — PnL"
    )

    # interactive + annotations
    nearest = alt.selection_point(nearest=True, on="pointermove", fields=["ts"], empty=False)
    selectors = base.mark_point().encode(x="ts:T").add_params(nearest)
    vline = base.mark_rule(color="gray").encode(x="ts:T").transform_filter(nearest)

    line_point = base.mark_circle(size=60).encode(
        y=alt.Y("gross_total_symbol:Q", axis=None, scale=alt.Scale(domain=list(dom_right)))
    ).transform_filter(nearest)

    line_text = base.mark_text(align="left", color="var(--text-color)", dx=6, dy=-6).encode(
        y=alt.Y("gross_total_symbol:Q", axis=None, scale=alt.Scale(domain=list(dom_right))),
        text=alt.Text("gross_total_symbol:Q", format=",.2f"),
    ).transform_filter(nearest)

    bar_text = base.mark_text(dy=-6, color="var(--text-color)", baseline="bottom").encode(
        y=alt.Y("gross_symbol:Q", axis=None, scale=alt.Scale(domain=list(dom_left))),
        text=alt.Text("gross_symbol:Q", format=",.2f"),
    ).transform_filter(nearest)

    return alt.layer(layered, selectors, vline, line_point, line_text, bar_text)


if "symbol" in df.columns and not df.empty:
    for sym, g in df.groupby("symbol", sort=False):
        st.subheader(sym)
        st.altair_chart(per_symbol_chart(g, sym, normalize_scales), use_container_width=True)

# ===== Export =====
st.markdown("### Export")
st.download_button(
    "Download Time Series (CSV)",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="pnl_timeseries.csv",
    mime="text/csv",
)
