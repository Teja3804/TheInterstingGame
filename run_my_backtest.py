"""
Run Backtest on Your Excel Data
Usage: python run_my_backtest.py "path/to/your/file.xlsx"
   OR: python run_my_backtest.py  (will prompt for file path)
"""

from backtest_trades import backtest_from_excel
import os
import sys
from pathlib import Path

def main():
    """Run backtest on your Excel file"""
    print("="*80)
    print("RUNNING BACKTEST ON YOUR EXCEL DATA")
    print("="*80)
    
    # Get file path from command line argument or prompt user
    if len(sys.argv) > 1:
        excel_file_path = sys.argv[1]
    else:
        # Try to find Excel files in current directory
        current_dir_files = list(Path(".").glob("*.xlsx")) + list(Path(".").glob("*.xls"))
        data_dir = Path("data")
        data_dir_files = []
        if data_dir.exists():
            data_dir_files = list(data_dir.glob("*.xlsx")) + list(data_dir.glob("*.xls"))
        
        all_files = current_dir_files + data_dir_files
        
        if all_files:
            print(f"\nFound {len(all_files)} Excel file(s):")
            for i, file in enumerate(all_files, 1):
                print(f"  {i}. {file}")
            print(f"\nUsing first file: {all_files[0]}")
            excel_file_path = str(all_files[0])
        else:
            print("\nNo Excel files found automatically.")
            excel_file_path = input("Please enter the path to your Excel file: ").strip().strip('"').strip("'")
    
    stock_name = None  # Will be extracted from filename if None
    
    # Check if file exists
    if not os.path.exists(excel_file_path):
        print(f"\n✗ Excel file not found: {excel_file_path}")
        print("\nPlease update the 'excel_file_path' variable in this script with your Excel file path.")
        print("\nExample:")
        print('  excel_file_path = "data/RELIANCE.xlsx"')
        print('  OR')
        print('  excel_file_path = "C:/Users/veenu/Desktop/stock_data.xlsx"')
        return
    
    # Extract stock name from filename if not provided
    if stock_name is None:
        from pathlib import Path
        stock_name = Path(excel_file_path).stem
        # Remove common suffixes
        for suffix in ['_data', '_ohlc', '_historical', '_daily', '_weekly', '_2024', '_2023', '_2025']:
            if stock_name.endswith(suffix):
                stock_name = stock_name[:-len(suffix)]
    
    print(f"\nExcel File: {excel_file_path}")
    print(f"Stock Name: {stock_name}")
    print(f"Quantity per trade: 100")
    print(f"Max holding days: 30")
    print("\n" + "-"*80)
    
    try:
        # Run backtest
        trades_df = backtest_from_excel(
            excel_file_path=excel_file_path,
            stock_name=stock_name,
            quantity=100,  # 100 shares per trade
            max_days=30,   # Maximum 30 days holding period
            output_file=f'backtest_results_{stock_name}.xlsx'
        )
        
        if not trades_df.empty:
            print(f"\n✓ Backtest completed successfully!")
            print(f"✓ Results saved to: backtest_results_{stock_name}.xlsx")
            print(f"\nYou can now open the Excel file to see:")
            print(f"  - All individual trades with entry/exit details")
            print(f"  - Profit/Loss for each trade")
            print(f"  - Summary row with net P&L of all trades")
        else:
            print(f"\n⚠ No trades were executed.")
            print("This could mean:")
            print("  - No trading signals were generated from your data")
            print("  - Check that your Excel file has the required columns (Date, Open, High, Low, Close, Volume)")
            
    except Exception as e:
        print(f"\n✗ Error running backtest: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\nTroubleshooting:")
        print("  1. Make sure your Excel file has columns: Date, Open, High, Low, Close, Volume")
        print("  2. Check that the file path is correct")
        print("  3. Ensure the file is not open in another program")


if __name__ == "__main__":
    main()

