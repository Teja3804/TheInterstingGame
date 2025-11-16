# The Interest Game

Stock market analysis system with market direction detection.

## Setup

1. Install required dependencies:
```bash
pip install -r requirements.txt
```

## File Structure

```
.
├── data_loader.py        # Data loading from Excel/CSV files
├── market_direction.py   # Market direction detection logic
├── main.py              # Main entry point (contains local file path)
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Data File Format

Your data files (Excel or CSV) should contain the following columns (case-insensitive):
- **Date** (or DateTime, Time, Timestamp, DT)
- **Open** (or O)
- **High** (or H)
- **Low** (or L)
- **Close** (or C, Closing)
- **Volume** (or Vol, V)

## Usage

The local file path is configured in `main.py`:

```python
DATA_FILE = r"C:\Users\veenu\Downloads\ongc24-25.csv"
```

Run the analysis:

```bash
python main.py
```

Or use in your code:

```python
from data_loader import load_stock
from market_direction import determine_market_direction

# Load stock data
df = load_stock(r"C:\Users\veenu\Downloads\ongc24-25.csv")

# Determine market direction
direction = determine_market_direction(df)
# Returns: 'increasing', 'decreasing', 'sideways', or 'no_trade'
```

## Market Direction Logic

The system determines market direction based on three cases:

1. **Trending Market**: 3%+ price movement in 2-5 day periods
2. **Sideways Market**: Body in 0-1.5% range for 7+ days OR 0-3% for 20+ days
3. **No Trade**: Doesn't match above patterns

