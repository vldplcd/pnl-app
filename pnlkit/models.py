from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from .types import Side, Action

@dataclass(slots=True)
class ActionEvent:
    """Single order state transition (action) from the log."""
    ts: datetime
    action: Action
    trade_px: Optional[Decimal] = None
    trade_amt: Optional[Decimal] = None

@dataclass(slots=True)
class Order:
    """Logical order reconstructed from multiple log rows."""
    order_id: str
    product: str
    side: Side
    events: List[ActionEvent] = field(default_factory=list)

    def is_filled(self) -> bool:
        return any(ev.action == Action.FILLED for ev in self.events)

    def closed_timestamp(self) -> Optional[datetime]:
        if not self.events:
            return None
        return max(ev.ts for ev in self.events)

    def last_fill(self) -> Optional[ActionEvent]:
        fills = [ev for ev in self.events if ev.action == Action.FILLED]
        return fills[-1] if fills else None

@dataclass(slots=True)
class Fill:
    """Normalized execution event used by the PnL engine."""
    ts: datetime
    product: str
    side: Side
    price: Decimal
    qty: Decimal
