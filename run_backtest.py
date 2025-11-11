"""
Run Backtest on Excel Data
Automatically finds Excel files and runs backtesting
"""

import os
from pathlib import Path
from backtest_trades import backtest_from_excel, TradeBacktester
from excel_data_loader import ExcelDataLoader
from main_algorithm import StockAnalyzer


def find_excel_files(directory="."):
    """Find all Excel files in the given directory and subdirectories"""
    excel_files = []
    directory = Path(directory)
    
    # Search in current directory
    for ext in ['*.xlsx', '*.xls']:
        excel_files.extend(directory.glob(ext))
    
    # Search in data directory if it exists
    data_dir = directory / "data"
    if data_dir.exists():
        for ext in ['*.xlsx', '*.xls']:
            excel_files.extend(data_dir.glob(ext))
    
    return list(set(excel_files))  # Remove duplicates


def main():
    """Main function to run backtest"""
    print("="*80)
    print("AUTOMATED BACKTESTING")
    print("="*80)
    
    # Find Excel files
    print("\n[Step 1] Searching for Excel files...")
    excel_files = find_excel_files()
    
    if not excel_files:
        print("✗ No Excel files found!")
        print("\nPlease ensure you have Excel files (.xlsx or .xls) in:")
        print("  - Current directory")
        print("  - data/ directory")
        print("\nOr specify the file path manually in the script.")
        return
    
    print(f"✓ Found {len(excel_files)} Excel file(s):")
    for i, file in enumerate(excel_files, 1):
        print(f"  {i}. {file}")
    
    # Process each Excel file
    for excel_file in excel_files:
        print("\n" + "="*80)
        print(f"Processing: {excel_file.name}")
        print("="*80)
        
        try:
            # Extract stock name from filename (remove extension and common suffixes)
            stock_name = excel_file.stem
            for suffix in ['_data', '_ohlc', '_historical', '_daily', '_weekly', '_2024', '_2023', '_2025']:
                if stock_name.endswith(suffix):
                    stock_name = stock_name[:-len(suffix)]
            
            print(f"Stock name: {stock_name}")
            
            # Run backtest
            trades_df = backtest_from_excel(
                excel_file_path=str(excel_file),
                stock_name=stock_name,
                quantity=100,  # 100 shares per trade
                max_days=30,   # Maximum 30 days holding period
                output_file=f'backtest_results_{stock_name}.xlsx'
            )
            
            if not trades_df.empty:
                print(f"\n✓ Backtest completed successfully!")
                print(f"  Results saved to: backtest_results_{stock_name}.xlsx")
            else:
                print(f"\n⚠ No trades were executed for this file.")
                
        except Exception as e:
            print(f"\n✗ Error processing {excel_file.name}: {str(e)}")
            import traceback
            traceback.print_exc()
            continue
    
    print("\n" + "="*80)
    print("BACKTESTING COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()

