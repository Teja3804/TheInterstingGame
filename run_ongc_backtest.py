"""Run backtest on ONGC CSV file"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from backtest_trades import backtest_from_excel
    print("✓ Imported backtest_trades module")
except Exception as e:
    print(f"✗ Error importing: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

if __name__ == "__main__":
    excel_file_path = r"C:\Users\veenu\Downloads\ongc24-25.csv"
    stock_name = "ONGC"
    
    print("="*80)
    print("RUNNING BACKTEST ON ONGC DATA")
    print("="*80)
    print(f"File: {excel_file_path}")
    print(f"Stock: {stock_name}")
    print(f"Checking if file exists...")
    
    if not os.path.exists(excel_file_path):
        print(f"✗ File not found: {excel_file_path}")
        sys.exit(1)
    
    print(f"✓ File exists")
    print(f"Starting backtest...\n")
    sys.stdout.flush()
    
    try:
        trades_df = backtest_from_excel(
            excel_file_path=excel_file_path,
            stock_name=stock_name,
            quantity=100,  # 100 shares per trade
            max_days=30,   # Maximum 30 days holding period
            output_file='backtest_results_ongc.xlsx'
        )
        
        sys.stdout.flush()
        
        if not trades_df.empty:
            print(f"\n✓ Backtest completed successfully!")
            print(f"✓ Results saved to: backtest_results_ongc.xlsx")
            print(f"\nTotal trades executed: {len(trades_df) - 1}")  # -1 for summary row
        else:
            print(f"\n⚠ No trades were executed.")
            
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

