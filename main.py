"""
Main entry point for The Interest Game
"""

from data_loader import load_stock
from market_direction import MarketDirectionDetector, determine_market_direction

# Local file path for data
DATA_FILE = r"C:\Users\veenu\Downloads\ongc24-25.csv"


def main():
    """Analyze stock data and determine market direction."""
    # Load stock data
    df = load_stock(DATA_FILE)
    
    # Determine market direction
    direction = determine_market_direction(df)
    
    print(f"Market Direction: {direction.upper()}")
    print(f"Data points: {len(df)} days")
    print(f"Date range: {df['date'].min().date()} to {df['date'].max().date()}")
    print(f"Current price: ₹{df['close'].iloc[-1]:.2f}")


if __name__ == "__main__":
    main()

