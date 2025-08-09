from __future__ import annotations
from enum import Enum

class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"

class Action(str, Enum):
    SENT = "sent"
    PLACED = "placed"
    FILLED = "filled"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
