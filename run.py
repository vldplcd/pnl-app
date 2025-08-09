#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import logging
from datetime import datetime
from typing import Dict, Any

from pnlkit.io import read_orders_from_csv, orders_to_fills
from pnlkit.engine import PnLEngine
from pnlkit.strategies import get_strategy
from pnlkit.viz import plot_cumulative_series, plot_combined, plot_per_symbol

# Set up logger for this module
logger = logging.getLogger(__name__)


def load_initial_positions(json_path: str) -> Dict[str, Dict[str, Any]]:
    """
    Load initial positions from a JSON file.
    
    Expected format:
    {
        "AAPL": {"qty": 100, "avg_price": 150.50},
        "GOOGL": {"qty": -50, "avg_price": 2800.00, "timestamp": "2024-01-01T09:00:00"},
        ...
    }
    
    Args:
        json_path: Path to JSON file with initial positions
        
    Returns:
        Dictionary with initial positions
        
    Raises:
        ValueError: If required fields are missing or invalid
    """
    with open(json_path, 'r') as f:
        positions = json.load(f)
    
    # Validate structure and required fields
    if not isinstance(positions, dict):
        raise ValueError(f"JSON root must be an object/dict, got {type(positions).__name__}")
    
    for symbol, data in positions.items():
        # Check symbol is a string
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError(f"Symbol must be a non-empty string, got: {symbol}")
        
        # Check data is a dict
        if not isinstance(data, dict):
            raise ValueError(f"Position data for {symbol} must be an object/dict, got {type(data).__name__}")
        
        # Check required fields
        if "qty" not in data:
            raise ValueError(f"Missing required field 'qty' for symbol {symbol}")
        if "avg_price" not in data:
            raise ValueError(f"Missing required field 'avg_price' for symbol {symbol}")
        
        # Validate qty (must be numeric)
        try:
            qty = float(data["qty"])
            if qty == 0:
                logging.warning(f"Symbol {symbol} has qty=0, position will be empty")
        except (TypeError, ValueError):
            raise ValueError(f"Invalid qty for {symbol}: {data['qty']} (must be numeric)")
        
        # Validate avg_price (must be positive numeric)
        try:
            price = float(data["avg_price"])
            if price <= 0:
                raise ValueError(f"avg_price for {symbol} must be positive, got: {price}")
        except (TypeError, ValueError):
            raise ValueError(f"Invalid avg_price for {symbol}: {data['avg_price']} (must be numeric)")
        
        # Parse timestamp if present
        if "timestamp" in data:
            if isinstance(data["timestamp"], str):
                try:
                    data["timestamp"] = datetime.fromisoformat(data["timestamp"])
                except ValueError as e:
                    raise ValueError(f"Invalid timestamp format for {symbol}: {data['timestamp']}. "
                                   f"Use ISO format (e.g., '2024-01-01T09:00:00'). Error: {e}")
            elif data["timestamp"] is not None and not isinstance(data["timestamp"], datetime):
                raise ValueError(f"Timestamp for {symbol} must be ISO string or null, got: {type(data['timestamp']).__name__}")
    
    return positions


def main():
    parser = argparse.ArgumentParser(description="PnL calculator (long/short, FIFO/LIFO).")
    parser.add_argument("csv", help="Path to input CSV (semicolon-separated).")
    parser.add_argument("--strategy", "-s", default="FIFO", choices=["FIFO", "LIFO"], help="Lot selection strategy.")
    parser.add_argument("--initial-positions", "-i", help="Path to JSON file with initial positions.")
    parser.add_argument("--out", "-o", default="out", help="Output directory for CSV/plots.")
    parser.add_argument("--all-plots", action="store_true", help="Save all possible plots.")
    parser.add_argument("--sep-plots", action="store_true", help="Save separate plots for uPnL rPnl and gross PnL (3 files).")
    parser.add_argument("--simple-plot", action="store_true", help="Save one combined plot with all series.")
    parser.add_argument("--per-symbol", action="store_true", help="Save a per-symbol plot (one file per symbol).")
    parser.add_argument("--log-level", default="INFO", help="Logging level (e.g., DEBUG, INFO, WARNING, ERROR).")
    args = parser.parse_args()

    # Configure logging with a nice format
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format=log_format,
        datefmt=date_format
    )
    
    # Adjust logger name for cleaner output
    global logger
    logger = logging.getLogger("pnlkit.run")
    
    logger.info("="*60)
    logger.info("PnL Calculator Started")
    logger.info(f"Strategy: {args.strategy}")
    logger.info(f"Input CSV: {args.csv}")
    logger.info(f"Output directory: {args.out}")
    logger.info("="*60)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Created output directory: {out_dir}")

    # Read & validate orders
    logger.info("Reading orders from CSV...")
    try:
        orders = read_orders_from_csv(args.csv)
        logger.info(f"Successfully loaded {len(orders)} orders")
    except Exception as e:
        logger.error(f"Failed to read CSV file: {e}")
        return 1

    # Convert to fills (preserving order-side/product)
    logger.info("Converting orders to fills...")
    fills = orders_to_fills(orders)
    logger.info(f"Converted to {len(fills)} fills")
    
    # Log symbol summary
    symbols = set(f.product for f in fills)
    logger.debug(f"Found {len(symbols)} unique symbols: {', '.join(sorted(symbols))}")

    # Run engine with pluggable strategy
    logger.info(f"Initializing PnL engine with {args.strategy} strategy...")
    strategy = get_strategy(args.strategy)
    eng = PnLEngine(strategy=strategy)
    
    # Load and set initial positions if provided
    if args.initial_positions:
        logger.info(f"Loading initial positions from: {args.initial_positions}")
        try:
            initial_positions = load_initial_positions(args.initial_positions)
            eng.set_initial_positions_from_dict(initial_positions)
            logger.info(f"Successfully loaded {len(initial_positions)} initial positions")
            
            # Log loaded positions with nice formatting
            for symbol, data in initial_positions.items():
                qty = data.get("qty", 0)
                price = data.get("avg_price", 0)
                ts = data.get("timestamp", "auto")
                side = "LONG" if qty > 0 else "SHORT" if qty < 0 else "FLAT"
                logger.debug(f"  {symbol:8s} | {side:5s} | qty={qty:8.2f} | avg_price={price:10.2f} | timestamp={ts}")
        except FileNotFoundError:
            logger.error(f"Initial positions file not found: {args.initial_positions}")
            return 1
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in initial positions file: {e}")
            return 1
        except ValueError as e:
            logger.error(f"Invalid initial positions data: {e}")
            return 1
        except Exception as e:
            logger.error(f"Unexpected error loading initial positions: {e}")
            logger.exception("Full traceback:")
            return 1
    else:
        logger.info("No initial positions provided, starting with empty positions")
    
    # Process fills
    logger.info("Processing fills...")
    result = eng.process_fills(fills)
    logger.info("Fill processing completed")

    # Report results
    logger.info("-"*60)
    logger.info("PnL REPORT")
    logger.info("-"*60)
    
    # Get report as string and log it line by line for proper formatting
    report = result.report_string()
    for line in report.split('\n'):
        logger.info(line)
    
    # Log position snapshot if we had initial positions
    if args.initial_positions:
        logger.info("-"*60)
        logger.info("FINAL POSITIONS")
        logger.info("-"*60)
        positions_report = result.positions_string(top_n=10)
        for line in positions_report.split('\n'):
            logger.info(line)


    # out_csv = out_dir / "pnl_timeseries.csv"
    # try:
    #     result.to_csv(out_csv)
    #     logger.info(f"Saved timeseries to: {out_csv}")
    # except Exception as e:
    #     logger.error(f"Failed to save CSV: {e}")
    #     return 1

    df = result.df

    # 7) Generate plots
    logger.info("-"*60)
    logger.info("GENERATING PLOTS")
    logger.info("-"*60)
    
    if args.all_plots:
        args.sep_plots = True
        args.simple_plot = True
        args.per_symbol = True
        logger.debug("All plots mode enabled")

    plots_generated = []
    
    if args.sep_plots:
        try:
            plot_cumulative_series(df, save_path=str(out_dir / "pnl"))
            logger.info(f"Generated separate plots (realized/unrealized/gross)")
            plots_generated.append("separate plots")
        except Exception as e:
            logger.error(f"Failed to generate separate plots: {e}")

    if args.simple_plot:
        try:
            plot_combined(df, save_path=str(out_dir / "pnl"))
            logger.info(f"Generated combined plot")
            plots_generated.append("combined plot")
        except Exception as e:
            logger.error(f"Failed to generate combined plot: {e}")

    if args.per_symbol:
        try:
            plot_per_symbol(df, save_dir=str(out_dir))
            num_symbols = len(set(df['symbol']))
            logger.info(f"Generated per-symbol plots ({num_symbols} symbols)")
            plots_generated.append(f"per-symbol plots ({num_symbols} files)")
        except Exception as e:
            logger.error(f"Failed to generate per-symbol plots: {e}")
    
    if not plots_generated:
        logger.warning("No plots were generated. Use --simple-plot, --sep-plots, --per-symbol, or --all-plots flags")
    
    logger.info("="*60)
    logger.info("PnL Calculator Completed Successfully")
    logger.info(f"All outputs saved to: {out_dir}")
    logger.info("="*60)

    return 0


if __name__ == "__main__":
    exit(main())