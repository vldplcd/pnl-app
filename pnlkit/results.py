# pnlkit/results.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any

import pandas as pd


from pnlkit.viz import plot_combined, plot_per_symbol


@dataclass
class PnLResult:
    """
    Container for processed PnL data and a snapshot of position states.

    df: per-fill timeseries with columns:
        ts, symbol,
        realized_total, unrealized_total, gross_total,
        realized_symbol, unrealized_symbol, gross_symbol

    states: snapshot of positions per symbol:
        {
          "AA": {
            "last_price": float | None,
            "realized_total": float,
            "long_lots":  [{"qty": float, "price": float, "ts_open": str}, ...],
            "short_lots": [{"qty": float, "price": float, "ts_open": str}, ...],
            "long_qty": float,
            "short_qty": float,
            "net_qty": float,
            "avg_cost_long": float | None,
            "avg_price_short": float | None,
          },
          ...
        }
    """
    df: pd.DataFrame
    states: Dict[str, Any]

    # -------- numeric accessors --------
    def _unrealized_from_state_entry(self, s: dict) -> float:
        """Compute unrealized PnL for a single symbol from the snapshot state."""
        last_px = s.get("last_price", None)
        if last_px is None:
            return 0.0

        upnl = 0.0
        for l in s.get("long_lots", []) or []:
            qty = float(l.get("qty", 0.0))
            px  = float(l.get("price", 0.0))
            upnl += (last_px - px) * qty
        for sh in s.get("short_lots", []) or []:
            qty = float(sh.get("qty", 0.0))
            px  = float(sh.get("price", 0.0))
            upnl += (px - last_px) * qty
        return upnl
    
    def _realized_deltas(self):
        """
        Per-fill realized PnL deltas (proxy for trade-level PnL).
        """
        import pandas as pd
        if self.df.empty or "realized_symbol" not in self.df.columns:
            return pd.Series(dtype=float)
        d = self.df["realized_symbol"].astype(float)
        return d[d != 0.0]

    def win_rate(self) -> float:
        """Fraction of positive realized PnL deltas."""
        d = self._realized_deltas()
        return float((d > 0).mean()) if not d.empty else 0.0

    def average_trade_pnl(self) -> float:
        """Average realized PnL per non-zero delta."""
        d = self._realized_deltas()
        return float(d.mean()) if not d.empty else 0.0

    def profit_factor(self) -> float:
        """Sum of wins / abs(sum of losses)."""
        d = self._realized_deltas()
        if d.empty:
            return 0.0
        wins = float(d[d > 0].sum())
        losses = abs(float(d[d < 0].sum()))
        if losses == 0.0:
            return float("inf") if wins > 0 else 0.0
        return wins / losses
    
    # -------- numeric accessors (reworked to use states) --------
    def total_gross(self) -> float:
        """Total gross PnL (portfolio) computed from position states snapshot."""
        if not self.states:
            return 0.0
        total = 0.0
        for s in self.states.values():
            realized = float(s.get("realized_total", 0.0))
            unreal   = self._unrealized_from_state_entry(s)
            total += realized + unreal
        return total

    def gross_by_symbol(self) -> Dict[str, float]:
        """Gross PnL per symbol computed from states snapshot."""
        if not self.states:
            return {}
        out: Dict[str, float] = {}
        for sym, s in self.states.items():
            realized = float(s.get("realized_total", 0.0))
            unreal   = self._unrealized_from_state_entry(s)
            out[sym] = realized + unreal
        return out

    def realized_total(self) -> float:
        """Portfolio realized PnL computed from states snapshot."""
        if not self.states:
            return 0.0
        return sum(float(s.get("realized_total", 0.0)) for s in self.states.values())

    def unrealized_total(self) -> float:
        """Portfolio unrealized PnL computed from states snapshot."""
        if not self.states:
            return 0.0
        return sum(self._unrealized_from_state_entry(s) for s in self.states.values())

    # -------- positions / states --------
    def positions_snapshot(self) -> Dict[str, Any]:
        """Return the snapshot dict as provided (already JSON-friendly)."""
        return self.states

    def positions_string(self, top_n: Optional[int] = None) -> str:
        """Human-readable positions overview built from states snapshot."""
        items = []
        for sym, s in self.states.items():
            net = s.get("net_qty", 0.0)
            lp = s.get("last_price", None)
            long_q = s.get("long_qty", 0.0)
            short_q = s.get("short_qty", 0.0)
            avg_long = s.get("avg_cost_long", None)
            avg_short = s.get("avg_price_short", None)
            items.append((sym, net, long_q, short_q, lp, avg_long, avg_short))
        # сортируем по |net|
        items.sort(key=lambda t: abs(t[1]), reverse=True)
        if top_n is not None:
            items = items[:top_n]

        sym_w = max([len("Symbol")] + [len(x[0]) for x in items]) if items else len("Symbol")
        num_w = 14
        lines = []
        lines.append("Open Positions Snapshot")
        lines.append("=" * (sym_w + 5 + num_w * 5))
        lines.append(f"{'Symbol'.ljust(sym_w)}  {'Net'.rjust(num_w)}  {'Long'.rjust(num_w)}  {'Short'.rjust(num_w)}  {'LastPx'.rjust(num_w)}  {'AvgLong'.rjust(num_w)}  {'AvgShort'.rjust(num_w)}")
        lines.append("-" * (sym_w + 5 + num_w * 5))
        for sym, net, lq, sq, lp, avgl, avgs in items:
            def fmt(x):
                return f"{x:,.4f}" if isinstance(x, float) else ("-" if x is None else str(x))
            lines.append(
                f"{sym.ljust(sym_w)}  {fmt(net).rjust(num_w)}  {fmt(lq).rjust(num_w)}  {fmt(sq).rjust(num_w)}  {fmt(lp).rjust(num_w)}  {fmt(avgl).rjust(num_w)}  {fmt(avgs).rjust(num_w)}"
            )
        return "\n".join(lines)

    # -------- exports --------
    def to_csv(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.df.to_csv(path, index=False)

    def to_dataframe(self) -> pd.DataFrame:
        return self.df.copy()
    
    def kpis(self) -> dict:
        """
        KPIs based on realized PnL deltas only.
        """
        return {
            "realized_total": float(self.realized_total()),
            "unrealized_total": float(self.unrealized_total()),
            "gross_total": float(self.total_gross()),
            "win_rate": float(self.win_rate()),
            "average_trade_pnl": float(self.average_trade_pnl()),
            "profit_factor": float(self.profit_factor()),
        }

    # -------- reporting --------
    def report_string(self, top_n: Optional[int] = None) -> str:
        """
        Covers:
          1) Calculate total gross PnL
          2) Calculate total gross PnL over each asset ID
        """
        total = self.total_gross()
        by_sym = self.gross_by_symbol()
        win_rate = float(self.win_rate())*100
        average_trade_pnl = float(self.average_trade_pnl())
        profit_factor = float(self.profit_factor())

        pairs = sorted(by_sym.items(), key=lambda kv: abs(kv[1]), reverse=True)
        if top_n is not None:
            pairs = pairs[:top_n]

        sym_w = max([len("Symbol")] + [len(k) for k, _ in pairs]) if pairs else len("Symbol")
        num_w = 16

        lines = []
        lines.append("PnL Report")
        lines.append("=" * (sym_w + num_w + 5))
        lines.append(f"Total Gross PnL: {total:,.2f}")
        lines.append("")
        lines.append("Breakdown by Symbol:")
        lines.append(f"{'Symbol'.ljust(sym_w)}  {'Gross PnL'.rjust(num_w)}")
        lines.append("-" * (sym_w + num_w + 2))
        for sym, val in pairs:
            lines.append(f"{sym.ljust(sym_w)}  {val:>{num_w},.2f}")
        lines.append("")
        lines.append("Additional metrics:")
        lines.append("")
        lines.append(f"Win-Rate: {win_rate:,.2f}%")
        lines.append(f"Avg Trade rPnL: {average_trade_pnl:,.2f}")
        lines.append(f"Profit Factor: {profit_factor:,.2f}")
        lines.append("=" * (sym_w + num_w + 5))
        return "\n".join(lines)

    # -------- quick plotting pass-throughs --------
    def plot_combined(self, **kwargs):
        return plot_combined(self.df, **kwargs)

    def plot_per_symbol(self, **kwargs):
        return plot_per_symbol(self.df, **kwargs)
