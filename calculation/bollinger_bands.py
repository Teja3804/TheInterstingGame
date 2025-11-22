"""
Bollinger Bands Calculation
Calculates Upper Band, Middle Band (SMA), and Lower Band
"""

import pandas as pd
import numpy as np
from typing import List, Dict


def calculate_bollinger_bands(
    data: pd.DataFrame,
    period: int = 20,
    num_std: float = 2.0,
    column: str = 'close'
) -> Dict[str, List[float]]:
    """
    Calculate Bollinger Bands
    
    Args:
        data: DataFrame with stock data
        period: Number of periods for moving average (default: 20)
        num_std: Number of standard deviations (default: 2.0)
        column: Column to calculate on (default: 'close')
    
    Returns:
        Dictionary with 'upper', 'middle', 'lower' bands as lists
    """
    if column not in data.columns:
        raise ValueError(f"Column '{column}' not found in data")
    
    # Calculate middle band (SMA)
    middle = data[column].rolling(window=period, min_periods=1).mean()
    
    # Calculate standard deviation
    std = data[column].rolling(window=period, min_periods=1).std()
    
    # Calculate upper and lower bands
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    
    return {
        'upper': upper.tolist(),
        'middle': middle.tolist(),
        'lower': lower.tolist()
    }


def calculate_bollinger_bands_dict(
    data: pd.DataFrame,
    period: int = 20,
    num_std: float = 2.0
) -> List[Dict]:
    """
    Calculate Bollinger Bands and return as list of dictionaries
    
    Args:
        data: DataFrame with stock data
        period: Number of periods for moving average (default: 20)
        num_std: Number of standard deviations (default: 2.0)
    
    Returns:
        List of dicts with 'date', 'upper', 'middle', 'lower' keys
    """
    bands = calculate_bollinger_bands(data, period, num_std)
    
    result = []
    for idx, row in data.iterrows():
        result.append({
            'date': row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date']),
            'upper': float(bands['upper'][idx]) if not pd.isna(bands['upper'][idx]) else None,
            'middle': float(bands['middle'][idx]) if not pd.isna(bands['middle'][idx]) else None,
            'lower': float(bands['lower'][idx]) if not pd.isna(bands['lower'][idx]) else None
        })
    
    return result

