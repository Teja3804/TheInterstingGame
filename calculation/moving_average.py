"""
Moving Average Calculation
Calculates Simple Moving Average (SMA) for stock data
"""

import pandas as pd
from typing import List, Dict


def calculate_ma(data: pd.DataFrame, period: int = 10, column: str = 'close') -> List[float]:
    """
    Calculate Simple Moving Average (SMA)
    
    Args:
        data: DataFrame with stock data (must have 'close' column)
        period: Number of periods for moving average (default: 10)
        column: Column to calculate MA on (default: 'close')
    
    Returns:
        List of MA values (NaN for first period-1 values)
    """
    if column not in data.columns:
        raise ValueError(f"Column '{column}' not found in data")
    
    ma = data[column].rolling(window=period, min_periods=1).mean()
    return ma.tolist()


def calculate_ma_dict(data: pd.DataFrame, period: int = 10) -> List[Dict]:
    """
    Calculate Moving Average and return as list of dictionaries
    
    Args:
        data: DataFrame with stock data
        period: Number of periods for moving average (default: 10)
    
    Returns:
        List of dicts with 'date' and 'ma' keys
    """
    ma_values = calculate_ma(data, period)
    
    result = []
    for idx, row in data.iterrows():
        result.append({
            'date': row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date']),
            'ma': float(ma_values[idx]) if not pd.isna(ma_values[idx]) else None
        })
    
    return result

