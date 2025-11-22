"""
Volume Weighted Average Price (VWAP) Calculation
Calculates VWAP for each trading day
"""

import pandas as pd
from typing import List, Dict


def calculate_vwap(data: pd.DataFrame) -> List[float]:
    """
    Calculate Volume Weighted Average Price (VWAP)
    VWAP = Sum(Price * Volume) / Sum(Volume)
    
    For each day, calculates cumulative VWAP from the start of the period
    
    Args:
        data: DataFrame with 'high', 'low', 'close', 'volume' columns
    
    Returns:
        List of VWAP values
    """
    required_columns = ['high', 'low', 'close', 'volume']
    for col in required_columns:
        if col not in data.columns:
            raise ValueError(f"Column '{col}' not found in data")
    
    # Calculate typical price (HLC/3)
    typical_price = (data['high'] + data['low'] + data['close']) / 3.0
    
    # Replace NaN volumes with 0 for calculation
    volume = data['volume'].fillna(0)
    
    # Calculate cumulative price * volume and cumulative volume
    cumulative_pv = (typical_price * volume).cumsum()
    cumulative_volume = volume.cumsum()
    
    # Calculate VWAP using vectorized operations
    # For days with zero cumulative volume, use typical price
    # Otherwise use standard VWAP formula: VWAP = Cumulative(PV) / Cumulative(Volume)
    import numpy as np
    vwap = cumulative_pv / cumulative_volume.replace(0, np.nan)
    
    # Replace NaN values (where volume was 0) with typical price
    vwap = vwap.fillna(typical_price)
    
    # Replace inf values with typical price
    mask_inf = (vwap == np.inf) | (vwap == -np.inf)
    vwap[mask_inf] = typical_price[mask_inf]
    
    # Final fillna to ensure no NaN values remain
    vwap = vwap.fillna(typical_price)
    
    return vwap.tolist()


def calculate_vwap_dict(data: pd.DataFrame) -> List[Dict]:
    """
    Calculate VWAP and return as list of dictionaries
    
    Args:
        data: DataFrame with stock data
    
    Returns:
        List of dicts with 'date' and 'vwap' keys
    """
    vwap_values = calculate_vwap(data)
    
    result = []
    for i, (idx, row) in enumerate(data.iterrows()):
        vwap_val = vwap_values[i]
        result.append({
            'date': row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date']),
            'vwap': float(vwap_val) if vwap_val is not None and not pd.isna(vwap_val) else None
        })
    
    return result

