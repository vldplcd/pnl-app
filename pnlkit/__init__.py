"""pnlkit: Minimal PnL calculation toolkit (FIFO/LIFO, long/short)."""
from .models import Order, Fill, ActionEvent
from .engine import PnLEngine
from .io import read_orders_from_csv, orders_to_fills
from .viz import plot_cumulative_series

__all__ = [
    "Order",
    "Fill",
    "ActionEvent",
    "PnLEngine",
    "read_orders_from_csv",
    "read_fills_from_csv", "orders_to_fills",
    "plot_cumulative_series",
]

__version__ = "0.1.0"
