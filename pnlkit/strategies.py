from __future__ import annotations
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from typing import Deque, Generator, Iterable, Tuple

from .engine import Lot

TakeGen = Generator[Tuple[Decimal, "Lot"], None, None]

class LotSelectionStrategy(ABC):
    """Abstract strategy for selecting quantities from lots."""
    name: str

    @abstractmethod
    def take(self, lots: Deque[Lot], need: Decimal) -> TakeGen:
        """Yield (take_qty, lot_ref) while decrementing lots in-place."""
        ...

@dataclass
class FIFOSelector(LotSelectionStrategy):
    name: str = "FIFO"

    def take(self, lots: Deque[Lot], need: Decimal) -> TakeGen:
        while need > 0 and lots:
            lot = lots[0]
            take = min(lot.qty, need)
            yield take, lot
            lot.qty -= take
            need -= take
            if lot.qty == 0:
                lots.popleft()

@dataclass
class LIFOSelector(LotSelectionStrategy):
    name: str = "LIFO"

    def take(self, lots: Deque[Lot], need: Decimal) -> TakeGen:
        while need > 0 and lots:
            lot = lots[-1]
            take = min(lot.qty, need)
            yield take, lot
            lot.qty -= take
            need -= take
            if lot.qty == 0:
                lots.pop()

# Simple factory/registry
_STRATEGIES = {
    "FIFO": FIFOSelector,
    "LIFO": LIFOSelector,
}

def get_strategy(name: str) -> LotSelectionStrategy:
    key = name.upper()
    if key not in _STRATEGIES:
        raise ValueError(f"Unknown strategy '{name}'. Available: {', '.join(_STRATEGIES)}")
    return _STRATEGIES[key]()
