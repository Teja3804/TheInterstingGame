"""
Backtesting Module for Trading Signals
Simulates trades based on trading signals and calculates profit/loss
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
from main_algorithm import StockAnalyzer
from excel_data_loader import ExcelDataLoader


class TradeBacktester:
    """
    Backtests trading signals and generates trade results table
    """
    
    def __init__(self, quantity: int = 100):
        """
        Initialize backtester
        
        Args:
            quantity: Number of shares/units per trade (default: 100)
        """
        self.quantity = quantity
        self.trades = []
    
    def simulate_trade(self, signal: Dict, ohlc_data: pd.DataFrame, 
                      max_days: int = 14, start_from_idx: int = None) -> Dict:
        """
        Simulate a single trade from entry to exit
        
        Args:
            signal: Trading signal dictionary with entry_price, stop_loss, target, direction, date, index
            ohlc_data: DataFrame with OHLC data
            max_days: Maximum days to hold trade before forced exit (default: 30)
            
        Returns:
            Dictionary with trade execution details and result
        """
        entry_date = signal['date']
        entry_index = signal['index']
        entry_price = signal['entry_price']
        stop_loss = signal.get('stop_loss')
        target = signal.get('target')
        direction = signal['direction']  # 'LONG' or 'SHORT'
        case = signal.get('case', 'Unknown')
        
        # Validate entry index
        if entry_index >= len(ohlc_data):
            return None
        
        # Start checking from day after entry
        # If start_from_idx is provided, use it to check for conflicting signals
        if start_from_idx is not None and start_from_idx > entry_index:
            # Check if we can even enter this trade (might be cut short by conflicting signal)
            pass
        
        start_idx = entry_index + 1
        # Ensure we don't exceed max_days from entry
        end_idx = min(start_idx + max_days, len(ohlc_data))
        
        exit_reason = None
        exit_date = None
        exit_price = None
        exit_index = None
        
        # Check each day after entry for exit conditions
        # Priority: Stop Loss first (to limit losses), then Target
        for idx in range(start_idx, end_idx):
            day_data = ohlc_data.iloc[idx]
            high = day_data['High']
            low = day_data['Low']
            close = day_data['Close']
            date = day_data['Date']
            
            if direction == 'LONG':
                # For LONG: exit if stop_loss hit (low touches SL) or target hit (high touches target)
                # Check stop loss first (priority)
                if stop_loss is not None and low <= stop_loss:
                    exit_reason = 'Stop Loss Hit'
                    exit_price = stop_loss
                    exit_date = date
                    exit_index = idx
                    break
                # Then check target
                if target is not None and high >= target:
                    exit_reason = 'Target Hit'
                    exit_price = target
                    exit_date = date
                    exit_index = idx
                    break
            else:  # SHORT
                # For SHORT: exit if stop_loss hit (high touches SL) or target hit (low touches target)
                # Check stop loss first (priority)
                if stop_loss is not None and high >= stop_loss:
                    exit_reason = 'Stop Loss Hit'
                    exit_price = stop_loss
                    exit_date = date
                    exit_index = idx
                    break
                # Then check target
                if target is not None and low <= target:
                    exit_reason = 'Target Hit'
                    exit_price = target
                    exit_date = date
                    exit_index = idx
                    break
        
        # If no exit condition met, exit at end of max_days or last available data
        if exit_reason is None:
            if end_idx < len(ohlc_data):
                exit_index = end_idx - 1
                exit_date = ohlc_data.iloc[exit_index]['Date']
                exit_price = ohlc_data.iloc[exit_index]['Close']
                exit_reason = f'Max Days ({max_days})'
            else:
                # No more data available
                exit_index = len(ohlc_data) - 1
                exit_date = ohlc_data.iloc[exit_index]['Date']
                exit_price = ohlc_data.iloc[exit_index]['Close']
                exit_reason = 'End of Data'
        
        # Calculate profit/loss
        if direction == 'LONG':
            pnl = (exit_price - entry_price) * self.quantity
            pnl_percent = ((exit_price - entry_price) / entry_price) * 100
        else:  # SHORT
            pnl = (entry_price - exit_price) * self.quantity
            pnl_percent = ((entry_price - exit_price) / entry_price) * 100
        
        # Calculate holding period
        if isinstance(entry_date, pd.Timestamp) and isinstance(exit_date, pd.Timestamp):
            holding_days = (exit_date - entry_date).days
        else:
            holding_days = exit_index - entry_index
        
        return {
            'Trade #': len(self.trades) + 1,
            'Case': case,
            'Direction': direction,
            'Entry Date': entry_date,
            'Entry Price': round(entry_price, 2),
            'Stop Loss': round(stop_loss, 2) if stop_loss is not None else 'N/A',
            'Target': round(target, 2) if target is not None else 'N/A',
            'Exit Date': exit_date,
            'Exit Price': round(exit_price, 2),
            'Exit Reason': exit_reason,
            'Quantity': self.quantity,
            'Holding Days': holding_days,
            'PnL': round(pnl, 2),
            'PnL %': round(pnl_percent, 2)
        }
    
    def backtest_signals(self, signals: List[Dict], ohlc_data: pd.DataFrame,
                        max_days: int = 14) -> pd.DataFrame:
        """
        Backtest multiple trading signals with position management
        Only one position (LONG or SHORT) can exist at a time
        
        Args:
            signals: List of trading signal dictionaries
            ohlc_data: DataFrame with OHLC data
            max_days: Maximum days to hold each trade (default: 14)
            
        Returns:
            DataFrame with all trade results
        """
        self.trades = []
        
        # Track current position
        current_position = None  # None, or dict with position details
        current_position_entry_idx = None
        
        total_signals = len(signals)
        print(f"Processing {total_signals} signals...", end='', flush=True)
        
        for signal_idx, signal in enumerate(signals):
            # Progress indicator every 20 signals
            if signal_idx > 0 and signal_idx % 20 == 0:
                print(f" {signal_idx}/{total_signals}...", end='', flush=True)
            # Validate signal has required fields
            if not signal or 'date' not in signal or 'index' not in signal or 'direction' not in signal:
                continue  # Skip invalid signal
            
            signal_date = signal.get('date')
            signal_index = signal.get('index')
            signal_direction = signal.get('direction')
            
            # Validate all required fields are present and not None
            if signal_date is None or signal_index is None or signal_direction is None:
                continue  # Skip invalid signal
            
            # Validate signal_index is within bounds
            if signal_index >= len(ohlc_data) or signal_index < 0:
                continue  # Skip invalid signal index
            
            # Check if we have an active position
            if current_position is not None:
                # First, check if current position has exceeded max_days
                if isinstance(current_position['entry_date'], pd.Timestamp) and isinstance(signal_date, pd.Timestamp):
                    holding_days_check = (signal_date - current_position['entry_date']).days
                else:
                    holding_days_check = signal_index - current_position_entry_idx
                
                if holding_days_check >= max_days:
                    # Position exceeded max_days - exit at market price
                    exit_day_data = ohlc_data.iloc[signal_index]
                    exit_price = exit_day_data['Close']
                    exit_date = exit_day_data['Date']
                    
                    if current_position['direction'] == 'LONG':
                        pnl = (exit_price - current_position['entry_price']) * self.quantity
                        pnl_percent = ((exit_price - current_position['entry_price']) / current_position['entry_price']) * 100
                    else:  # SHORT
                        pnl = (current_position['entry_price'] - exit_price) * self.quantity
                        pnl_percent = ((current_position['entry_price'] - exit_price) / current_position['entry_price']) * 100
                    
                    exited_trade = {
                        'Trade #': len(self.trades) + 1,
                        'Case': current_position['case'],
                        'Direction': current_position['direction'],
                        'Entry Date': current_position['entry_date'],
                        'Entry Price': round(current_position['entry_price'], 2),
                        'Stop Loss': round(current_position['stop_loss'], 2) if current_position['stop_loss'] is not None else 'N/A',
                        'Target': round(current_position['target'], 2) if current_position['target'] is not None else 'N/A',
                        'Exit Date': exit_date,
                        'Exit Price': round(exit_price, 2),
                        'Exit Reason': f'Max Days ({max_days})',
                        'Quantity': self.quantity,
                        'Holding Days': holding_days_check,
                        'PnL': round(pnl, 2),
                        'PnL %': round(pnl_percent, 2)
                    }
                    self.trades.append(exited_trade)
                    current_position = None
                    current_position_entry_idx = None
                    # Continue to process this signal (which will enter new position if no conflict)
                    # Note: current_position is now None, so we'll skip the conflict check below
                
                # Check if new signal conflicts with current position (only if position still exists)
                if current_position is not None and current_position['direction'] != signal_direction:
                    # Opposite direction - exit current position first at market price
                    if signal_index >= len(ohlc_data):
                        continue  # Skip if index out of bounds
                    exit_day_data = ohlc_data.iloc[signal_index]
                    exit_price = exit_day_data['Close']
                    exit_date = exit_day_data['Date']
                    
                    # Calculate P&L for exited position
                    if current_position['direction'] == 'LONG':
                        pnl = (exit_price - current_position['entry_price']) * self.quantity
                        pnl_percent = ((exit_price - current_position['entry_price']) / current_position['entry_price']) * 100
                    else:  # SHORT
                        pnl = (current_position['entry_price'] - exit_price) * self.quantity
                        pnl_percent = ((current_position['entry_price'] - exit_price) / current_position['entry_price']) * 100
                    
                    # Calculate holding days
                    if isinstance(current_position['entry_date'], pd.Timestamp) and isinstance(exit_date, pd.Timestamp):
                        holding_days = (exit_date - current_position['entry_date']).days
                    else:
                        holding_days = signal_index - current_position_entry_idx
                    
                    # Record the exited trade
                    exited_trade = {
                        'Trade #': len(self.trades) + 1,
                        'Case': current_position['case'],
                        'Direction': current_position['direction'],
                        'Entry Date': current_position['entry_date'],
                        'Entry Price': round(current_position['entry_price'], 2),
                        'Stop Loss': round(current_position['stop_loss'], 2) if current_position['stop_loss'] is not None else 'N/A',
                        'Target': round(current_position['target'], 2) if current_position['target'] is not None else 'N/A',
                        'Exit Date': exit_date,
                        'Exit Price': round(exit_price, 2),
                        'Exit Reason': 'Opposite Signal - Market Exit',
                        'Quantity': self.quantity,
                        'Holding Days': holding_days,
                        'PnL': round(pnl, 2),
                        'PnL %': round(pnl_percent, 2)
                    }
                    self.trades.append(exited_trade)
                    
                    # Clear current position
                    current_position = None
                    current_position_entry_idx = None
                else:
                    # Same direction - UPDATE stop loss and target, don't enter new position
                    # Keep the original entry price and date, but update SL and Target
                    current_position['stop_loss'] = signal.get('stop_loss')
                    current_position['target'] = signal.get('target')
                    current_position['case'] = signal.get('case', current_position['case'])
                    
                    # Check if position has exceeded max_days
                    if isinstance(current_position['entry_date'], pd.Timestamp) and isinstance(signal_date, pd.Timestamp):
                        holding_days_check = (signal_date - current_position['entry_date']).days
                    else:
                        holding_days_check = signal_index - current_position_entry_idx
                    
                    # Check if updated SL or Target is hit on this signal day
                    signal_day_data = ohlc_data.iloc[signal_index]
                    high = signal_day_data['High']
                    low = signal_day_data['Low']
                    close = signal_day_data['Close']
                    date = signal_day_data['Date']
                    
                    exit_hit = False
                    exit_reason = None
                    exit_price = None
                    
                    # Check max days first
                    if holding_days_check >= max_days:
                        exit_hit = True
                        exit_reason = f'Max Days ({max_days})'
                        exit_price = close
                    elif current_position['direction'] == 'LONG':
                        if current_position['stop_loss'] is not None and low <= current_position['stop_loss']:
                            exit_hit = True
                            exit_reason = 'Stop Loss Hit'
                            exit_price = current_position['stop_loss']
                        elif current_position['target'] is not None and high >= current_position['target']:
                            exit_hit = True
                            exit_reason = 'Target Hit'
                            exit_price = current_position['target']
                    else:  # SHORT
                        if current_position['stop_loss'] is not None and high >= current_position['stop_loss']:
                            exit_hit = True
                            exit_reason = 'Stop Loss Hit'
                            exit_price = current_position['stop_loss']
                        elif current_position['target'] is not None and low <= current_position['target']:
                            exit_hit = True
                            exit_reason = 'Target Hit'
                            exit_price = current_position['target']
                    
                    if exit_hit:
                        # Position exited - calculate P&L and record trade
                        if current_position['direction'] == 'LONG':
                            pnl = (exit_price - current_position['entry_price']) * self.quantity
                            pnl_percent = ((exit_price - current_position['entry_price']) / current_position['entry_price']) * 100
                        else:  # SHORT
                            pnl = (current_position['entry_price'] - exit_price) * self.quantity
                            pnl_percent = ((current_position['entry_price'] - exit_price) / current_position['entry_price']) * 100
                        
                        if isinstance(current_position['entry_date'], pd.Timestamp) and isinstance(date, pd.Timestamp):
                            holding_days = (date - current_position['entry_date']).days
                        else:
                            holding_days = signal_index - current_position_entry_idx
                        
                        exited_trade = {
                            'Trade #': len(self.trades) + 1,
                            'Case': current_position['case'],
                            'Direction': current_position['direction'],
                            'Entry Date': current_position['entry_date'],
                            'Entry Price': round(current_position['entry_price'], 2),
                            'Stop Loss': round(current_position['stop_loss'], 2) if current_position['stop_loss'] is not None else 'N/A',
                            'Target': round(current_position['target'], 2) if current_position['target'] is not None else 'N/A',
                            'Exit Date': date,
                            'Exit Price': round(exit_price, 2),
                            'Exit Reason': exit_reason,
                            'Quantity': self.quantity,
                            'Holding Days': holding_days,
                            'PnL': round(pnl, 2),
                            'PnL %': round(pnl_percent, 2)
                        }
                        self.trades.append(exited_trade)
                        current_position = None
                        current_position_entry_idx = None
                    else:
                        # Position continues with updated SL/Target - continue to next signal
                        continue
            
            # Enter new position - set as current position immediately
            # This allows future same-direction signals to update SL/Target
            # Validate signal has required fields (already checked above, but double-check entry_price)
            if signal.get('entry_price') is None:
                continue  # Skip invalid signal
            
            current_position = {
                'direction': signal_direction,
                'entry_price': signal['entry_price'],
                'entry_date': signal['date'],
                'stop_loss': signal.get('stop_loss'),
                'target': signal.get('target'),
                'case': signal.get('case', 'Unknown')
            }
            current_position_entry_idx = signal_index
            
            # Check if exit conditions are hit on the entry day itself
            entry_day_data = ohlc_data.iloc[signal_index]
            entry_high = entry_day_data['High']
            entry_low = entry_day_data['Low']
            entry_close = entry_day_data['Close']
            entry_date = entry_day_data['Date']
            
            exit_hit = False
            exit_reason = None
            exit_price = None
            
            # Check SL and Target on entry day
            if signal_direction == 'LONG':
                if signal.get('stop_loss') is not None and entry_low <= signal['stop_loss']:
                    exit_hit = True
                    exit_reason = 'Stop Loss Hit'
                    exit_price = signal['stop_loss']
                elif signal.get('target') is not None and entry_high >= signal['target']:
                    exit_hit = True
                    exit_reason = 'Target Hit'
                    exit_price = signal['target']
            else:  # SHORT
                if signal.get('stop_loss') is not None and entry_high >= signal['stop_loss']:
                    exit_hit = True
                    exit_reason = 'Stop Loss Hit'
                    exit_price = signal['stop_loss']
                elif signal.get('target') is not None and entry_low <= signal['target']:
                    exit_hit = True
                    exit_reason = 'Target Hit'
                    exit_price = signal['target']
            
            # If exit hit on entry day, record trade and clear position
            if exit_hit:
                if signal_direction == 'LONG':
                    pnl = (exit_price - signal['entry_price']) * self.quantity
                    pnl_percent = ((exit_price - signal['entry_price']) / signal['entry_price']) * 100
                else:  # SHORT
                    pnl = (signal['entry_price'] - exit_price) * self.quantity
                    pnl_percent = ((signal['entry_price'] - exit_price) / signal['entry_price']) * 100
                
                trade_result = {
                    'Trade #': len(self.trades) + 1,
                    'Case': signal.get('case', 'Unknown'),
                    'Direction': signal_direction,
                    'Entry Date': signal['date'],
                    'Entry Price': round(signal['entry_price'], 2),
                    'Stop Loss': round(signal.get('stop_loss'), 2) if signal.get('stop_loss') is not None else 'N/A',
                    'Target': round(signal.get('target'), 2) if signal.get('target') is not None else 'N/A',
                    'Exit Date': entry_date,
                    'Exit Price': round(exit_price, 2),
                    'Exit Reason': exit_reason,
                    'Quantity': self.quantity,
                    'Holding Days': 0,
                    'PnL': round(pnl, 2),
                    'PnL %': round(pnl_percent, 2)
                }
                self.trades.append(trade_result)
                current_position = None
                current_position_entry_idx = None
            # Otherwise, position is set as current_position and will be checked/updated by future signals
        
        # If there's still an active position at the end, exit it
        if current_position is not None:
            last_idx = len(ohlc_data) - 1
            exit_day_data = ohlc_data.iloc[last_idx]
            exit_price = exit_day_data['Close']
            exit_date = exit_day_data['Date']
            
            if current_position['direction'] == 'LONG':
                pnl = (exit_price - current_position['entry_price']) * self.quantity
                pnl_percent = ((exit_price - current_position['entry_price']) / current_position['entry_price']) * 100
            else:  # SHORT
                pnl = (current_position['entry_price'] - exit_price) * self.quantity
                pnl_percent = ((current_position['entry_price'] - exit_price) / current_position['entry_price']) * 100
            
            if isinstance(current_position['entry_date'], pd.Timestamp) and isinstance(exit_date, pd.Timestamp):
                holding_days = (exit_date - current_position['entry_date']).days
            else:
                holding_days = last_idx - current_position_entry_idx
            
            final_trade = {
                'Trade #': len(self.trades) + 1,
                'Case': current_position['case'],
                'Direction': current_position['direction'],
                'Entry Date': current_position['entry_date'],
                'Entry Price': round(current_position['entry_price'], 2),
                'Stop Loss': round(current_position['stop_loss'], 2) if current_position['stop_loss'] is not None else 'N/A',
                'Target': round(current_position['target'], 2) if current_position['target'] is not None else 'N/A',
                'Exit Date': exit_date,
                'Exit Price': round(exit_price, 2),
                'Exit Reason': 'End of Data',
                'Quantity': self.quantity,
                'Holding Days': holding_days,
                'PnL': round(pnl, 2),
                'PnL %': round(pnl_percent, 2)
            }
            self.trades.append(final_trade)
        
        print(f" Done!")  # Complete progress indicator
        
        if not self.trades:
            return pd.DataFrame()
        
        # Convert to DataFrame
        trades_df = pd.DataFrame(self.trades)
        
        # Add summary row
        total_pnl = trades_df['PnL'].sum()
        total_pnl_percent = trades_df['PnL %'].sum()
        winning_trades = len(trades_df[trades_df['PnL'] > 0])
        losing_trades = len(trades_df[trades_df['PnL'] < 0])
        total_trades = len(trades_df)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        summary_row = {
            'Trade #': 'SUMMARY',
            'Case': '-',
            'Direction': '-',
            'Entry Date': '-',
            'Entry Price': '-',
            'Stop Loss': '-',
            'Target': '-',
            'Exit Date': '-',
            'Exit Price': '-',
            'Exit Reason': '-',
            'Quantity': '-',
            'Holding Days': '-',
            'PnL': round(total_pnl, 2),
            'PnL %': round(total_pnl_percent, 2)
        }
        
        # Add additional summary columns to trades (empty for individual trades)
        for col in ['Win Rate', 'Winning Trades', 'Losing Trades', 'Total Trades']:
            trades_df[col] = ''
        
        # Update summary row with additional info
        summary_row['Win Rate'] = f'{win_rate:.2f}%'
        summary_row['Winning Trades'] = winning_trades
        summary_row['Losing Trades'] = losing_trades
        summary_row['Total Trades'] = total_trades
        
        # Add summary row to DataFrame
        summary_df = pd.DataFrame([summary_row])
        result_df = pd.concat([trades_df, summary_df], ignore_index=True)
        
        return result_df
    
    def export_to_excel(self, trades_df: pd.DataFrame, output_file: str = 'backtest_results.xlsx'):
        """
        Export backtest results to Excel file (or CSV if openpyxl not available)
        
        Args:
            trades_df: DataFrame with trade results
            output_file: Output Excel file path
        """
        if trades_df.empty:
            print("No trades to export")
            return
        
        try:
            trades_df.to_excel(output_file, index=False, engine='openpyxl')
            print(f"[OK] Backtest results exported to {output_file}")
        except Exception as e:
            # Fallback to CSV if openpyxl is not available
            csv_file = output_file.replace('.xlsx', '.csv')
            try:
                trades_df.to_csv(csv_file, index=False)
                print(f"[OK] Backtest results exported to {csv_file} (CSV format)")
                print(f"[INFO] Install openpyxl (pip install openpyxl) to export as Excel")
            except Exception as e2:
                print(f"[ERROR] Error exporting to Excel: {str(e)}")
                print(f"[ERROR] Error exporting to CSV: {str(e2)}")
    
    def print_summary(self, trades_df: pd.DataFrame):
        """
        Print summary of backtest results
        
        Args:
            trades_df: DataFrame with trade results
        """
        if trades_df.empty:
            print("No trades to summarize")
            return
        
        # Get summary row (last row)
        summary = trades_df.iloc[-1]
        
        print("\n" + "="*80)
        print("BACKTEST SUMMARY")
        print("="*80)
        print(f"Total Trades: {summary['Total Trades']}")
        print(f"Winning Trades: {summary['Winning Trades']}")
        print(f"Losing Trades: {summary['Losing Trades']}")
        print(f"Win Rate: {summary['Win Rate']}")
        print(f"Net P&L: Rs {summary['PnL']:,.2f}")
        print(f"Net P&L %: {summary['PnL %']:.2f}%")
        print("="*80)


def backtest_from_excel(excel_file_path: str, stock_name: str = None, 
                        quantity: int = 100, max_days: int = 14,
                        lookback_days: int = None,
                        output_file: str = 'backtest_results.xlsx') -> pd.DataFrame:
    """
    Complete backtesting workflow from Excel or CSV file
    
    Args:
        excel_file_path: Path to Excel or CSV file with OHLC data
        stock_name: Name of the stock (optional, extracted from filename if not provided)
        quantity: Number of shares per trade (default: 100)
        max_days: Maximum days to hold each trade (default: 30)
        lookback_days: Number of days to analyze for signals (None for all)
        output_file: Output Excel file path for results
        
    Returns:
        DataFrame with backtest results
    """
    # Load data
    print(f"Loading data from {excel_file_path}...")
    file_path = Path(excel_file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {excel_file_path}")
    
    loader = ExcelDataLoader(data_directory=".")
    
    # Check if it's a CSV file
    if file_path.suffix.lower() == '.csv':
        # Read CSV file
        df = pd.read_csv(excel_file_path)
        ohlc_data = loader._normalize_dataframe(df)
    else:
        # Read Excel file
        ohlc_data = loader.read_excel_file(excel_file_path, combine_sheets=True)
    
    print(f"✓ Loaded {len(ohlc_data)} rows of data")
    
    # Analyze stock
    print(f"\nAnalyzing stock and generating signals...")
    analyzer = StockAnalyzer()
    result = analyzer.analyze_stock(ohlc_data, stock_name or "Stock")
    signals = result['trading_signals']
    print(f"✓ Generated {len(signals)} trading signals")
    
    if not signals:
        print("No trading signals found. Cannot backtest.")
        return pd.DataFrame()
    
    # Backtest signals
    print(f"\nBacktesting {len(signals)} signals with quantity {quantity}...")
    backtester = TradeBacktester(quantity=quantity)
    trades_df = backtester.backtest_signals(signals, ohlc_data, max_days=max_days)
    
    if trades_df.empty:
        print("No trades executed.")
        return pd.DataFrame()
    
    # Print summary
    backtester.print_summary(trades_df)
    
    # Export to Excel
    print(f"\nExporting results to {output_file}...")
    backtester.export_to_excel(trades_df, output_file)
    
    return trades_df


if __name__ == "__main__":
    """
    Example usage:
    
    # Option 1: Use the complete workflow function
    trades_df = backtest_from_excel('data/STOCK_NAME.xlsx', stock_name='STOCK_NAME', quantity=100)
    
    # Option 2: Use the class directly for more control
    loader = ExcelDataLoader(data_directory="data")
    ohlc_data = loader.read_excel_file('data/STOCK_NAME.xlsx')
    
    analyzer = StockAnalyzer()
    result = analyzer.analyze_stock(ohlc_data, "STOCK_NAME")
    signals = result['trading_signals']
    
    backtester = TradeBacktester(quantity=100)
    trades_df = backtester.backtest_signals(signals, ohlc_data, max_days=30)
    backtester.print_summary(trades_df)
    backtester.export_to_excel(trades_df, 'backtest_results.xlsx')
    """
    print("Backtesting Module for Trading Signals")
    print("="*80)
    print("\nUsage:")
    print("  from backtest_trades import backtest_from_excel")
    print("  trades_df = backtest_from_excel('data/STOCK.xlsx', stock_name='STOCK', quantity=100)")
    print("\nOr use the TradeBacktester class directly for more control.")
    print("="*80)

