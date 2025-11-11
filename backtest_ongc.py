"""
Simple script to backtest ONGC data from CSV file
Run: python backtest_ongc.py
"""

import pandas as pd
from pathlib import Path
from backtest_trades import TradeBacktester
from main_algorithm import StockAnalyzer
from excel_data_loader import ExcelDataLoader

# File path
csv_file = r"C:\Users\veenu\Downloads\ongc24-25.csv"
stock_name = "ONGC"

print("="*80)
print("ONGC BACKTEST")
print("="*80)

# Step 1: Load CSV
print(f"\n[1] Loading CSV file: {csv_file}")
try:
    df = pd.read_csv(csv_file)
    print(f"    [OK] Loaded {len(df)} rows")
    print(f"    Columns: {list(df.columns)}")
except Exception as e:
    print(f"    [ERROR] Error: {e}")
    exit(1)

# Step 2: Normalize data
print(f"\n[2] Normalizing data format...")
try:
    loader = ExcelDataLoader(data_directory=".")
    ohlc_data = loader._normalize_dataframe(df)
    print(f"    [OK] Normalized to {len(ohlc_data)} rows")
    print(f"    Date range: {ohlc_data['Date'].min()} to {ohlc_data['Date'].max()}")
except Exception as e:
    print(f"    [ERROR] Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Step 3: Generate signals
print(f"\n[3] Analyzing and generating trading signals...")
try:
    analyzer = StockAnalyzer()
    result = analyzer.analyze_stock(ohlc_data, stock_name)
    signals = result['trading_signals']
    print(f"    [OK] Generated {len(signals)} trading signals")
except Exception as e:
    print(f"    [ERROR] Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

if not signals:
    print("\n[WARNING] No trading signals found. Cannot backtest.")
    exit(0)

# Step 4: Backtest
print(f"\n[4] Backtesting {len(signals)} signals (quantity: 100, max days: 14)...")
try:
    backtester = TradeBacktester(quantity=100)
    trades_df = backtester.backtest_signals(signals, ohlc_data, max_days=14)
    
    if trades_df.empty:
        print("    [WARNING] No trades executed")
        exit(0)
    
    print(f"    [OK] Executed {len(trades_df) - 1} trades")
except Exception as e:
    print(f"    [ERROR] Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Step 5: Display summary
print(f"\n[5] Results Summary:")
backtester.print_summary(trades_df)

# Step 6: Export to Excel
output_file = 'backtest_results_ongc.xlsx'
print(f"\n[6] Exporting to Excel: {output_file}")
backtester.export_to_excel(trades_df, output_file)

print("\n" + "="*80)
print("BACKTEST COMPLETE!")
print(f"Results saved to: {output_file}")
print("="*80)

