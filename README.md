# pnlkit

A powerful and minimal PnL (Profit and Loss) calculation toolkit for trading systems, supporting both FIFO/LIFO strategies and long/short positions.

## Features

- 📊 **Accurate PnL Calculation**: Calculate realized, unrealized, and gross PnL
- 📈 **Multiple Strategies**: Support for FIFO (First In, First Out) and LIFO (Last In, First Out)
- 💹 **Long/Short Positions**: Full support for both long and short trading positions
- 🎯 **Initial Positions**: Set starting positions before processing trades
- 📉 **Beautiful Visualizations**: Generate professional charts for PnL analysis
- 🔧 **Flexible Usage**: Use as CLI tool or Python library
- 📝 **Detailed Reports**: Get comprehensive PnL breakdowns by symbol
  
## Project Structure

```
pnl-app/
├── pnlkit/                 # Main package directory
│   ├── __init__.py
│   ├── engine.py          # Core PnL calculation engine
│   ├── models.py          # Data models
│   ├── io.py              # Input/output operations
│   ├── strategies.py      # FIFO/LIFO strategies
│   ├── types.py           # Type definitions
│   ├── results.py         # Result container
│   └── viz.py             # Visualization functions
├── run.py                 # CLI entry point
├── test_logs.csv          # Sample data file
├── init_position.json     # Sample initial positions
├── pyproject.toml         # Package configuration
├── setup.cfg              # Setup configuration
└── README.md              # This file
```

## Installation

### From ZIP Archibe

```bash
# Extract the archive
unzip pnl-app.zip
cd pnl-app

# Install in development mode
pip install -e .

# Or install normally
pip install .
```


### Without Package Installation (Direct Usage)

If you don't want to install the package, you can use it directly:

```bash
# Extract the archive
unzip pnl-app.zip
cd pnl-app

# Install only dependencies
pip install pandas>=2.0 numpy>=1.23 matplotlib>=3.7

# Run directly
python run.py test_logs.csv --strategy FIFO --plot
```

For Python/Jupyter usage without installation:
```python
import sys
sys.path.append('/path/to/pnl-app')  # Add pnl-app directory to Python path

# Now you can import pnlkit
from pnlkit import PnLEngine, read_orders_from_csv, orders_to_fills
```


### Dependencies

- Python >= 3.10
- pandas >= 2.0
- numpy >= 1.23
- matplotlib >= 3.7

## Quick Start

### Python Library Usage

```python
from pnlkit import PnLEngine, read_orders_from_csv, orders_to_fills
from pnlkit.strategies import get_strategy

# Read and process orders
orders = read_orders_from_csv("test_logs.csv")
fills = orders_to_fills(orders)

# Initialize engine with strategy
strategy = get_strategy("FIFO")  # or "LIFO"
engine = PnLEngine(strategy=strategy)

# Optional: Set initial positions
engine.set_initial_position(
    symbol="AAPL",
    qty=100,        # positive for long, negative for short
    avg_price=150.50
)

# Process fills and get results
result = engine.process_fills(fills)

# Access results
print(f"Total Gross PnL: {result.total_gross():.2f}")
print(f"By Symbol: {result.gross_by_symbol()}")

# Generate report
print(result.report_string())

# Save to CSV
result.to_csv("pnl_results.csv")

# Generate plots
result.plot_combined(save_path="pnl_combined")
result.plot_per_symbol(save_dir="plots/")
```

### Command Line Usage

#### Basic usage with FIFO strategy:
```bash
python run.py test_logs.csv --strategy FIFO --all-plots
```

#### With initial positions:
```bash
python run.py test_logs.csv -s FIFO -i init_position.json --all-plots
```

#### Generate all visualizations:
```bash
python run.py test_logs.csv --strategy LIFO --all-plots --out results/
```

## Command Line Arguments

```
usage: run.py [-h] [--strategy {FIFO,LIFO}] [--initial-positions PATH]
              [--out DIR] [--all-plots] [--sep-plots] [--simple-plot]
              [--per-symbol] [--log-level LEVEL] csv

Arguments:
  csv                        Path to input CSV (semicolon-separated)

Options:
  -s, --strategy {FIFO,LIFO}  Lot selection strategy (default: FIFO)
  -i, --initial-positions      Path to JSON file with initial positions
  -o, --out DIR               Output directory for CSV/plots (default: out)
  --all-plots                 Save all possible plots
  --sep-plots                 Save separate plots for realized/unrealized/gross
  --plot                      Save combined plot with all series
  --per-symbol                Save per-symbol plots
  --log-level LEVEL           Logging level (DEBUG, INFO, WARNING, ERROR)
```

## Data Formats

### Input CSV Format

The input CSV must be semicolon-separated with the following columns:

```csv
currentTime;action;orderId;orderProduct;orderSide;tradePx;tradeAmt
1577836800000000000;sent;order1;AAPL;buy;;
1577836801000000000;placed;order1;AAPL;buy;;
1577836802000000000;filled;order1;AAPL;buy;150.00;100
```

**Column descriptions:**
- `currentTime`: Timestamp in nanoseconds
- `action`: Order status (sent, placed, filled, cancelling, cancelled)
- `orderId`: Unique order identifier
- `orderProduct`: Symbol/Asset ID
- `orderSide`: buy or sell
- `tradePx`: Trade price (for filled orders)
- `tradeAmt`: Trade amount/quantity (for filled orders)

### Initial Positions JSON Format

```json
{
    "AAPL": {
        "qty": 100,
        "avg_price": 150.50
    },
    "GOOGL": {
        "qty": -50,
        "avg_price": 2800.00,
        "timestamp": "2024-01-01T09:00:00"
    }
}
```

**Fields:**
- `qty`: Position quantity (positive = long, negative = short)
- `avg_price`: Average entry price (must be positive)
- `timestamp`: Optional ISO format timestamp (if not provided, set to 1 minute before first trade). **!!!** If provided no validation executed - this might lead to unexpected bugs.

## Jupyter Notebook Usage

```python
# Import the library
from pnlkit import PnLEngine, read_orders_from_csv, orders_to_fills
from pnlkit.strategies import get_strategy
from pnlkit.viz import plot_combined, plot_per_symbol
import pandas as pd

# Load data
orders = read_orders_from_csv("test_logs.csv")
fills = orders_to_fills(orders)

# Setup engine
engine = PnLEngine(strategy=get_strategy("FIFO"))

# Set initial positions programmatically
initial_positions = {
    "AAPL": {"qty": 100, "avg_price": 150.50},
    "GOOGL": {"qty": -50, "avg_price": 2800.00}
}
engine.set_initial_positions_from_dict(initial_positions)

# Process and analyze
result = engine.process_fills(fills)

# Get DataFrame for analysis
df = result.to_dataframe()
display(df.head())

# Show statistics
print(f"Total Gross PnL: ${result.total_gross():,.2f}")
print(f"Realized PnL: ${result.realized_total():,.2f}")
print(f"Unrealized PnL: ${result.unrealized_total():,.2f}")

# Display breakdown by symbol
breakdown = result.gross_by_symbol()
pd.DataFrame(breakdown.items(), columns=['Symbol', 'Gross PnL']).sort_values('Gross PnL', ascending=False)

# Generate interactive plots (in notebook)
result.plot_combined(show=True)

# Get current positions
positions = engine.get_current_positions()
print(result.positions_string())
```

## Advanced Usage

### Custom Position Management

```python
from pnlkit.engine import InitialPosition
from decimal import Decimal

# Using InitialPosition objects
positions = [
    InitialPosition(
        symbol="AAPL",
        qty=Decimal("100"),
        avg_price=Decimal("150.50"),
        timestamp=datetime(2024, 1, 1, 9, 30)
    ),
    InitialPosition(
        symbol="GOOGL",
        qty=Decimal("-50"),
        avg_price=Decimal("2800.00")
    )
]

engine.set_initial_positions(positions)
```

### Accessing Detailed Results

```python
# Get result object
result = engine.process_fills(fills)

# Access timeseries DataFrame
df = result.df
# Columns: ts, symbol, realized_total, unrealized_total, gross_total,
#          realized_symbol, unrealized_symbol, gross_symbol,
#          realized_total_symbol, gross_total_symbol

# Get position snapshots
positions = result.positions_snapshot()
# Returns dict with detailed position info including:
# - Open lots (long and short)
# - Average prices
# - Current quantities
# - Last prices

# Generate formatted reports
print(result.report_string())        # PnL summary
print(result.positions_string())     # Position details
```

## Output Files

When using the CLI tool, the following files are generated in the output directory:

- `pnl_combined.png` - Combined portfolio PnL chart
- `pnl_realized.png` - Realized PnL chart (with --sep-plots)
- `pnl_unrealized.png` - Unrealized PnL chart (with --sep-plots)
- `pnl_gross.png` - Gross PnL chart (with --sep-plots)
- `pnl_[SYMBOL].png` - Individual symbol charts (with --per-symbol)

got it — here’s a drop-in README section you can paste in.

## PnL Web UI (Streamlit)

Interactive dashboard for PnL analysis built on top of the project’s core engine and strategies.
Based on Streamlit package.

### Requirements

* Python 3.10+ (recommended)
* Packages:

  ```bash
  pip install -r requirements-ui.txt
  ```

  *(If your project isn’t installed as a package, running from repo root is fine.)*

### File Location

Place `web-ui.py` next to `run.py` in the repo root.

### Run

```bash
streamlit run web-ui.py
```

This will open the app in your browser (usually at [http://localhost:8501](http://localhost:8501)).

### Demo deployment

I've also deployed this service to Render.com (a free microservices hosting platform I found) - you can check it out at [https://pnl-test-app-0-1-3.onrender.com/](https://pnl-test-app-0-1-3.onrender.com/)

Please note: This deployment uses free tier resources, which may result in slower performance and occasional issues. For the best experience, I recommend running the service locally.

### Usage

1. **Upload Trades CSV** (semicolon-separated) in the sidebar.
2. (Optional) **Upload Initial Positions JSON** — same format as in the CLI.
3. Choose **Lot selection strategy**: `FIFO` or `LIFO`.
4. (Optional) Toggle **Normalize scales**:

   * **Off (default):** left (bars) and right (line) Y-axes share one symmetric scale, so zero lines align exactly.
   * **On:** left and right axes use independent symmetric scales (useful if magnitudes differ a lot).
5. Review:

   * **Top KPIs**: Realized, Unrealized, Gross (totals).
   * **Open Positions Snapshot** (monospace table).
   * **Charts**:

     * **Portfolio**: bars = instant `gross_symbol`, line+area = cumulative `gross_total`.
     * **Per symbol**: bars = instant `gross_symbol`, line+area = `gross_total_symbol`.

At the bottom you can **download** the time series as CSV.

### Input Formats

#### Trades CSV (semicolon-separated)

Required columns (as produced by your logs):

```
currentTime;action;orderId;orderProduct;orderSide;tradePx;tradeAmt
1577836800000000000;sent;order1;AAPL;buy;;
1577836801000000000;placed;order1;AAPL;buy;;
1577836802000000000;filled;order1;AAPL;buy;150.00;100
```

* `currentTime`: timestamp **in nanoseconds**
* `action`: rows with `filled` are converted to fills; other statuses are ignored
* `orderSide`: `buy` or `sell`
* `tradePx`, `tradeAmt`: numeric

#### Initial Positions JSON (optional)

Same semantics as the CLI:

```json
{
  "AAPL": { "qty": 100, "avg_price": 150.50 },
  "GOOGL": { "qty": -50, "avg_price": 2800.00, "timestamp": "2024-01-01T09:00:00" }
}
```

Notes:

* `qty` > 0 → long; `qty` < 0 → short.
* `avg_price` must be positive.
* `timestamp` is optional (ISO 8601). If omitted, the engine seeds positions slightly before the first trade.
* Uploaded initial positions are **shown in the UI** and applied before processing fills.

### What the UI Shows

* **KPIs**
  `Realized PnL (total)`, `Unrealized PnL (total)`, `Gross PnL (total)`.
* **Open Positions Snapshot**
  Monospace report with Net/Long/Short/LastPx/AvgLong/AvgShort.
* **Charts**

  * **Portfolio Overview:**
    Bars = instant PnL (`gross_symbol`) with green/red colors;
    Right-axis line+area = cumulative `gross_total`.
    The **Normalize scales** toggle controls whether axes share a domain (zero aligned) or use separate symmetric domains.
  * **Per-Symbol:**
    Bars = instant `gross_symbol`; right-axis line+area = `gross_total_symbol`.

## Troubleshooting

* **No data calculated:** Ensure your CSV contains `action=filled` rows and numeric `tradePx`/`tradeAmt`.
* **Weird axes:** Use the **Normalize scales** toggle to switch between shared vs separate Y-axis domains.
* **Initial positions not applied:** Check JSON structure, numeric fields, and ISO timestamp. Errors are shown as warnings in the sidebar.




## PnL Calculation Methodology

1. **Realized PnL**: Profit/loss from closed positions
2. **Unrealized PnL**: Mark-to-market value of open positions using last traded price
3. **Gross PnL**: Sum of realized and unrealized PnL - **no comissions** taken into account

### Strategies

- **FIFO (First In, First Out)**: Oldest positions are closed first
- **LIFO (Last In, First Out)**: Newest positions are closed first

### Position Handling

- Long positions: Created by BUY orders, closed by SELL orders
- Short positions: Created by SELL orders, closed by BUY orders
- Positions are tracked separately per symbol

## Development

### Running Tests
```bash
# Install development dependencies
pip install -e ".[dev]"
```

### Code Style
```bash
# Format code
black pnlkit/
isort pnlkit/

# Check style
flake8 pnlkit/
```

## Troubleshooting

### Common Issues

1. **CSV parsing errors**: Ensure your CSV is semicolon-separated and has all required columns
2. **Invalid initial positions**: Check JSON format and ensure all required fields (qty, avg_price) are present
3. **No plots generated**: Add plot flags (--plot, --all-plots, etc.) to generate visualizations

### Logging

Use `--log-level DEBUG` for detailed execution information:
```bash
python run.py test_logs.csv --log-level DEBUG --plot
```

## Credits
* **Developed by [Vladimir Shilov](https://www.linkedin.com/in/vladimir-shilov-215993163/)**
* **[Telegram](https://t.me/vldplcd)**

