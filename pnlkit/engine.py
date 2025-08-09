from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Deque, Dict, List, Optional, Tuple, Union
from collections import deque, defaultdict

import pandas as pd

from .models import Fill
from .types import Side
from .results import PnLResult


Money = Decimal

@dataclass(slots=True)
class Lot:
    """Open position lot (long or short)."""
    qty: Decimal  # positive
    price: Money
    ts_open: datetime

@dataclass(slots=True)
class SymbolState:
    """Per-symbol state maintained by the PnL engine."""
    long_lots: Deque[Lot] = field(default_factory=deque)
    short_lots: Deque[Lot] = field(default_factory=deque)
    realized_pnl: Money = Money("0")
    rpnl_hist: List[Money] = field(default_factory=list)
    upnl_hist: List[Money] = field(default_factory=list)
    last_price: Optional[Money] = None

    def long_qty(self) -> Decimal:
        return sum(l.qty for l in self.long_lots)

    def short_qty(self) -> Decimal:
        return sum(l.qty for l in self.short_lots)

    def position(self) -> Decimal:
        return self.long_qty() - self.short_qty()

    def unrealized(self) -> Money:
        if self.last_price is None:
            return Money("0")
        up = Money("0")
        for l in self.long_lots:
            up += (self.last_price - l.price) * l.qty
        for s in self.short_lots:
            up += (s.price - self.last_price) * s.qty
        return up

@dataclass
class InitialPosition:
    """Initial position configuration for a symbol."""
    symbol: str
    qty: Decimal  # positive for long, negative for short
    avg_price: Money
    timestamp: Optional[datetime] = None  # when position was opened

class PnLEngine:
    """Long/short PnL calculator with pluggable lot-selection strategies.

    Supports setting initial positions for symbols.

    Returns tidy time series with columns:
        ['ts','symbol','realized_total','unrealized','gross']
    """

    def __init__(self, strategy) -> None:
        """strategy: instance with .take(lots, need) -> yields (take_qty, lot)"""
        self.strategy = strategy
        self.state: Dict[str, SymbolState] = {}
        self.realized_total: Money = Money("0")
        self._pending_initial_positions: List[Dict] = []  # Store positions to set later

    # --- initial position setup ---
    def set_initial_position(
        self, 
        symbol: str, 
        qty: Union[Decimal, float, int], 
        avg_price: Union[Money, float],
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Set initial position for a symbol.
        
        Args:
            symbol: The symbol/asset ID
            qty: Position quantity (positive for long, negative for short, 0 to clear)
            avg_price: Average entry price for the position
            timestamp: When the position was opened (default: will be set to 1 minute before first fill)
        """
        qty = Decimal(str(qty))
        avg_price = Money(str(avg_price))
        
        if timestamp is None:
            # Store for later processing when we know the first fill time
            self._pending_initial_positions.append({
                "symbol": symbol,
                "qty": qty,
                "avg_price": avg_price,
                "timestamp": None
            })
            return
        
        st = self._get(symbol)
        
        # Clear existing lots for this symbol
        st.long_lots.clear()
        st.short_lots.clear()
        
        # Set the initial position
        if qty > 0:
            # Long position
            st.long_lots.append(Lot(qty=qty, price=avg_price, ts_open=timestamp))
        elif qty < 0:
            # Short position (store as positive qty in short_lots)
            st.short_lots.append(Lot(qty=abs(qty), price=avg_price, ts_open=timestamp))
        # If qty == 0, position is cleared (both deques remain empty)
        
        # Update last price if provided
        if avg_price > 0:
            st.last_price = avg_price

    def set_initial_positions(self, positions: List[InitialPosition]) -> None:
        """
        Set multiple initial positions at once.
        
        Args:
            positions: List of InitialPosition objects
        """
        for pos in positions:
            self.set_initial_position(
                symbol=pos.symbol,
                qty=pos.qty,
                avg_price=pos.avg_price,
                timestamp=pos.timestamp
            )

    def set_initial_positions_from_dict(
        self, 
        positions: Dict[str, Dict[str, Union[float, Decimal, datetime]]]
    ) -> None:
        """
        Set initial positions from a dictionary format.
        
        Args:
            positions: Dict with format:
                {
                    "AAPL": {"qty": 100, "avg_price": 150.50, "timestamp": datetime(...)},
                    "GOOGL": {"qty": -50, "avg_price": 2800.00},
                    ...
                }
        """
        for symbol, data in positions.items():
            self.set_initial_position(
                symbol=symbol,
                qty=data["qty"],
                avg_price=data["avg_price"],
                timestamp=data.get("timestamp")
            )

    # --- internal helpers ---
    def _get(self, sym: str) -> SymbolState:
        return self.state.setdefault(sym, SymbolState())
    
    def _snapshot_states(self) -> Dict[str, Any]:
        """
        Create a JSON-friendly snapshot of internal symbol states.
        """
        def lots_view(lots):
            out = []
            for l in lots:
                out.append({
                    "qty": float(l.qty),
                    "price": float(l.price),
                    "ts_open": l.ts_open.isoformat(),
                })
            return out

        snap = {}
        for sym, st in self.state.items():
            # avg cost for long / avg entry for short
            long_qty = sum(l.qty for l in st.long_lots)
            short_qty = sum(l.qty for l in st.short_lots)
            def avg_cost(lots):
                q = sum(l.qty for l in lots)
                if q == 0:
                    return None
                return float(sum(l.qty * l.price for l in lots) / q)

            snap[sym] = {
                "last_price": float(st.last_price) if st.last_price is not None else None,
                "realized_total": float(st.realized_pnl),
                "long_lots": lots_view(st.long_lots),
                "short_lots": lots_view(st.short_lots),
                "long_qty": float(long_qty),
                "short_qty": float(short_qty),
                "net_qty": float(long_qty - short_qty),
                "avg_cost_long": avg_cost(st.long_lots),
                "avg_price_short": avg_cost(st.short_lots),
            }
        return snap

    def get_current_positions(self) -> Dict[str, Dict[str, float]]:
        """
        Get current positions summary.
        
        Returns:
            Dict with format:
                {
                    "AAPL": {"net_qty": 100.0, "long_qty": 100.0, "short_qty": 0.0, ...},
                    ...
                }
        """
        return self._snapshot_states()

    # --- core logic ---
    def apply_fill(self, f: Fill) -> Tuple[Money, Money, Money, Money, Money, Money, Money, Money]:
        st = self._get(f.product)
        st.last_price = f.price
        pnl = 0
        if f.side == Side.SELL:
            left = f.qty
            for take, lot in self.strategy.take(st.long_lots, f.qty):
                pnl = (f.price - lot.price) * take
                self.realized_total += pnl
                st.realized_pnl += pnl
                st.rpnl_hist.append(pnl)
                left -= take
            if left > 0:
                st.short_lots.append(Lot(qty=left, price=f.price, ts_open=f.ts))
        else:  # BUY
            left = f.qty
            for take, lot in self.strategy.take(st.short_lots, f.qty):
                pnl = (lot.price - f.price) * take
                self.realized_total += pnl
                st.realized_pnl += pnl
                st.rpnl_hist.append(pnl)
                left -= take
            if left > 0:
                st.long_lots.append(Lot(qty=left, price=f.price, ts_open=f.ts))
        
        up_total = self.unrealized_total()
        up = st.unrealized()
        st.upnl_hist.append(up)
        gross = pnl + up
        gross_total = self.realized_total + up_total
        gross_total_symbol = st.realized_pnl + up
        return self.realized_total, st.realized_pnl, pnl, up_total, up, gross_total, gross_total_symbol, gross

    def unrealized_total(self) -> Money:
        return sum(st.unrealized() for st in self.state.values())

    # --- batch processing ---
    def process_fills(self, fills: List[Fill]) -> PnLResult:
        # Apply pending initial positions with timestamp = 1 minute before first fill
        if self._pending_initial_positions and fills:
            first_fill_time = min(f.ts for f in fills)
            initial_timestamp = first_fill_time - timedelta(minutes=1)
            
            for pos_data in self._pending_initial_positions:
                self.set_initial_position(
                    symbol=pos_data["symbol"],
                    qty=pos_data["qty"],
                    avg_price=pos_data["avg_price"],
                    timestamp=initial_timestamp
                )
            
            # Clear pending positions after applying them
            self._pending_initial_positions.clear()
        
        rows = []
        for f in sorted(fills, key=lambda x: x.ts):
            (realized_total, rp_total_symbol, rp, up_total, up, 
            gross_total, gross_total_symbol, gross) = self.apply_fill(f)

            rows.append({
                "ts": f.ts, 
                "symbol": f.product, 
                "realized_total": float(realized_total), 
                "unrealized_total": float(up_total), 
                "gross_total": float(gross_total),
                "realized_symbol": float(rp),
                "unrealized_symbol": float(up),
                "gross_symbol": float(gross),
                "realized_total_symbol": float(rp_total_symbol), 
                "gross_total_symbol": float(gross_total_symbol),
            })
        
        df = pd.DataFrame(rows)
        return PnLResult(df=df, states=self._snapshot_states())