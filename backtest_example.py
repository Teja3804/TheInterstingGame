"""
Example: Backtesting Trading Signals from Excel Data
This script demonstrates how to backtest trading signals and generate trade results table
"""

from excel_data_loader import ExcelDataLoader
from main_algorithm import StockAnalyzer
from backtest_trades import TradeBacktester, backtest_from_excel
import os


def main():
    """
    Example workflow: Load Excel data, generate signals, and backtest
    """
    print("="*80)
    print("BACKTESTING TRADING SIGNALS - EXAMPLE")
    print("="*80)
    
    # Option 1: Quick method - Use the complete workflow function
    print("\n[Option 1] Using complete workflow function...")
    print("-" * 80)
    
    # Replace with your Excel file path
    excel_file = "data/STOCK_NAME.xlsx"  # Change this to your Excel file path
    
    if os.path.exists(excel_file):
        try:
            trades_df = backtest_from_excel(
                excel_file_path=excel_file,
                stock_name="STOCK_NAME",  # Optional: extracted from filename if not provided
                quantity=100,  # Number of shares per trade
                max_days=30,  # Maximum days to hold each trade
                lookback_days=None,  # None = analyze all data
                output_file='backtest_results.xlsx'
            )
            
            if not trades_df.empty:
                print("\n✓ Backtest complete! Check 'backtest_results.xlsx' for detailed results.")
        except Exception as e:
            print(f"✗ Error in backtest: {str(e)}")
    else:
        print(f"✗ Excel file not found: {excel_file}")
        print("  Please update the excel_file path in the script")
    
    # Option 2: Step-by-step method for more control
    print("\n\n[Option 2] Step-by-step method (for more control)...")
    print("-" * 80)
    
    data_directory = "data"  # Change this to your data directory
    
    if not os.path.exists(data_directory):
        print(f"✗ Data directory not found: {data_directory}")
        print("  Please create the directory and add your Excel files")
        return
    
    try:
        # Step 1: Load data
        print("\n[Step 1] Loading stock data...")
        loader = ExcelDataLoader(data_directory)
        
        # Load a specific stock (replace with your stock name)
        stock_name = "RELIANCE"  # Change this to your stock name
        try:
            ohlc_data = loader.load_stock_data(stock_name)
            print(f"✓ Loaded {len(ohlc_data)} rows for {stock_name}")
        except FileNotFoundError:
            print(f"✗ No Excel files found for {stock_name}")
            print("  Please check your data directory and stock name")
            return
        
        # Step 2: Analyze and generate signals
        print(f"\n[Step 2] Analyzing {stock_name} and generating signals...")
        analyzer = StockAnalyzer()
        result = analyzer.analyze_stock(ohlc_data, stock_name)
        signals = result['trading_signals']
        print(f"✓ Generated {len(signals)} trading signals")
        
        if not signals:
            print("  No trading signals found. Cannot backtest.")
            return
        
        # Display first few signals
        print(f"\n  First 3 signals preview:")
        for i, signal in enumerate(signals[:3], 1):
            print(f"    Signal {i}: {signal.get('direction')} at ₹{signal.get('entry_price', 0):.2f} "
                  f"on {signal.get('date')} (Case: {signal.get('case', 'N/A')})")
        
        # Step 3: Backtest signals
        print(f"\n[Step 3] Backtesting {len(signals)} signals...")
        backtester = TradeBacktester(quantity=100)  # 100 shares per trade
        trades_df = backtester.backtest_signals(signals, ohlc_data, max_days=30)
        
        if trades_df.empty:
            print("  No trades executed.")
            return
        
        # Step 4: Display results
        print(f"\n[Step 4] Backtest Results:")
        print("-" * 80)
        backtester.print_summary(trades_df)
        
        # Display first few trades
        print(f"\n  First 5 trades:")
        print(trades_df.head(5).to_string(index=False))
        
        # Step 5: Export to Excel
        print(f"\n[Step 5] Exporting results to Excel...")
        output_file = f'backtest_results_{stock_name}.xlsx'
        backtester.export_to_excel(trades_df, output_file)
        
        print(f"\n✓ Complete! Results saved to {output_file}")
        print("="*80)
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

