"""
Trading Signals for Decreasing Market
Implements three cases for detecting rising/sideways market signals during downtrends
This is the inverse logic of increasing market signals
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from .moving_averages_calc import calculate_10_ma, calculate_20_ma, are_mas_close
from .bollinger_bands_calc import calculate_bollinger_bands
from .stochastic_rsi_calc import calculate_stochastic_rsi
from .volatility_calc import calculate_volatility


def is_green_candle(ohlc_data: pd.DataFrame, idx: int) -> bool:
    """
    Check if candle is green (close > open)
    
    Args:
        ohlc_data: DataFrame with OHLC data
        idx: Index of the candle
        
    Returns:
        True if green candle, False otherwise
    """
    if idx >= len(ohlc_data):
        return False
    return ohlc_data.iloc[idx]['Close'] > ohlc_data.iloc[idx]['Open']


def is_neutral_candle(ohlc_data: pd.DataFrame, idx: int, threshold_pct: float = 0.001) -> bool:
    """
    Check if candle is neutral (open very close to close)
    
    Args:
        ohlc_data: DataFrame with OHLC data
        idx: Index of the candle
        threshold_pct: Percentage threshold for neutral (default 0.1%)
        
    Returns:
        True if neutral candle, False otherwise
    """
    if idx >= len(ohlc_data):
        return False
    open_price = ohlc_data.iloc[idx]['Open']
    close_price = ohlc_data.iloc[idx]['Close']
    diff_pct = abs(open_price - close_price) / open_price
    return diff_pct <= threshold_pct


def is_below_lower_bb(ohlc_data: pd.DataFrame, bb_data: Dict, idx: int, lookback: int = 3) -> bool:
    """
    Check if previous candle(s) are below lower Bollinger Band
    
    Args:
        ohlc_data: DataFrame with OHLC data
        bb_data: Bollinger Bands data dictionary
        idx: Current index
        lookback: Number of previous candles to check
        
    Returns:
        True if any previous candle is below lower BB
    """
    if idx < lookback:
        return False
    
    # bb_data is already the daily_bollinger_bands dict
    if isinstance(bb_data, dict) and 'lower' in bb_data:
        lower_bb = bb_data['lower']
    elif isinstance(bb_data, dict) and 'daily_bollinger_bands' in bb_data:
        lower_bb = bb_data['daily_bollinger_bands']['lower']
    else:
        return False
    closes = ohlc_data['Close']
    
    for i in range(max(0, idx - lookback), idx):
        if i < len(lower_bb) and not pd.isna(lower_bb.iloc[i]):
            if closes.iloc[i] < lower_bb.iloc[i]:
                return True
    return False


def check_volatility_similarity(volatility_data: pd.Series, idx: int, lookback: int = 3, 
                                threshold_pct: float = 0.15) -> bool:
    """
    Check if current volatility is within 10-20% of previous candles' volatility
    
    Args:
        volatility_data: Series of volatility values
        idx: Current index
        lookback: Number of previous candles to compare
        threshold_pct: Percentage threshold (default 15% for 10-20% range)
        
    Returns:
        True if volatility is similar
    """
    if idx < lookback or idx >= len(volatility_data):
        return False
    
    current_vol = volatility_data.iloc[idx]
    if pd.isna(current_vol) or current_vol == 0:
        return False
    
    # Get previous volatilities
    prev_vols = []
    for i in range(max(0, idx - lookback), idx):
        if i < len(volatility_data) and not pd.isna(volatility_data.iloc[i]):
            prev_vols.append(volatility_data.iloc[i])
    
    if not prev_vols:
        return False
    
    avg_prev_vol = np.mean(prev_vols)
    diff_pct = abs(current_vol - avg_prev_vol) / avg_prev_vol
    
    return diff_pct <= threshold_pct


def is_volume_increasing(ohlc_data: pd.DataFrame, idx: int, lookback: int = 3) -> bool:
    """
    Check if volume is increasing relative to previous candles
    
    Args:
        ohlc_data: DataFrame with OHLC data
        idx: Current index
        lookback: Number of previous candles to compare
        
    Returns:
        True if volume is increasing
    """
    if idx < lookback or idx >= len(ohlc_data):
        return False
    
    current_volume = ohlc_data.iloc[idx]['Volume']
    prev_volumes = []
    
    for i in range(max(0, idx - lookback), idx):
        if i < len(ohlc_data):
            prev_volumes.append(ohlc_data.iloc[i]['Volume'])
    
    if not prev_volumes:
        return False
    
    avg_prev_volume = np.mean(prev_volumes)
    return current_volume > avg_prev_volume


def is_volume_same(ohlc_data: pd.DataFrame, idx: int, lookback: int = 3, threshold_pct: float = 0.1) -> bool:
    """
    Check if volume is the same (within threshold) relative to previous candles
    
    Args:
        ohlc_data: DataFrame with OHLC data
        idx: Current index
        lookback: Number of previous candles to compare
        threshold_pct: Percentage threshold for "same" (default 10%)
        
    Returns:
        True if volume is similar (not significantly increasing or decreasing)
    """
    if idx < lookback or idx >= len(ohlc_data):
        return False
    
    current_volume = ohlc_data.iloc[idx]['Volume']
    prev_volumes = []
    
    for i in range(max(0, idx - lookback), idx):
        if i < len(ohlc_data):
            prev_volumes.append(ohlc_data.iloc[i]['Volume'])
    
    if not prev_volumes:
        return False
    
    avg_prev_volume = np.mean(prev_volumes)
    if avg_prev_volume == 0:
        return False
    
    diff_pct = abs(current_volume - avg_prev_volume) / avg_prev_volume
    return diff_pct <= threshold_pct


def is_volatility_increased(volatility_data: pd.Series, idx: int, lookback: int = 3) -> bool:
    """
    Check if volatility has increased compared to previous candles
    
    Args:
        volatility_data: Series of volatility values
        idx: Current index
        lookback: Number of previous candles to compare
        
    Returns:
        True if volatility increased
    """
    if idx < lookback or idx >= len(volatility_data):
        return False
    
    current_vol = volatility_data.iloc[idx]
    if pd.isna(current_vol):
        return False
    
    prev_vols = []
    for i in range(max(0, idx - lookback), idx):
        if i < len(volatility_data) and not pd.isna(volatility_data.iloc[i]):
            prev_vols.append(volatility_data.iloc[i])
    
    if not prev_vols:
        return False
    
    avg_prev_vol = np.mean(prev_vols)
    return current_vol > avg_prev_vol


def calculate_tick_size(price: float) -> float:
    """
    Calculate tick size based on price (approximation)
    For stocks, typically $0.01 for prices < $1, $0.01 for prices >= $1
    
    Args:
        price: Current price
        
    Returns:
        Tick size
    """
    if price < 1.0:
        return 0.01
    else:
        return 0.01


def calculate_dynamic_target_case_2a(ma10_val: float, ma20_val: float, entry_price: float, 
                                     current_price: float = None) -> float:
    """
    Calculate dynamic target for Case 2.a (inverse of Case 1.a)
    Target is average of 10 MA and 20 MA, or just above 10 MA if in profits
    
    Args:
        ma10_val: Current 10 MA value
        ma20_val: Current 20 MA value
        entry_price: Entry price of the trade
        current_price: Current price (if None, uses entry_price to check profits)
        
    Returns:
        Target price
    """
    if current_price is None:
        current_price = entry_price
    
    # Check if in profits (current price is above entry, meaning we're long and price rose)
    # For long positions, we're in profit when price increases
    is_in_profits = current_price > entry_price
    
    if is_in_profits:
        # When in profits, target is just above 10 MA
        target = ma10_val * 1.005  # 0.5% above 10 MA
    else:
        # Initial target is average of 10 MA and 20 MA
        target = (ma10_val + ma20_val) / 2
    
    # For LONG trades, target must be ABOVE entry price
    # If calculated target is below entry, use a percentage above entry
    if target <= entry_price:
        target = entry_price * 1.03  # 3% above entry
    
    return target


def case_2a_signal(ohlc_data: pd.DataFrame, indicators: Dict, idx: int) -> Optional[Dict]:
    """
    Case 2.a: Lower BB rejection with green/neutral candle and Stoch RSI < 20
    (Inverse of Case 1.a)
    
    Conditions:
    - Previous candle(s) below lower Bollinger Band
    - Current candle is green (close > open) or neutral (open very close to close)
    - Stochastic RSI < 20
    - If neutral: volatility similar (10-20%) and volume increasing → rising market
    - If neutral: volume same and volatility increased → sideways market
    
    Args:
        ohlc_data: DataFrame with OHLC data
        indicators: Dictionary of calculated indicators
        idx: Current index
        
    Returns:
        Dictionary with signal info (case, entry, sl, target) or None
    """
    if idx < 20:  # Need enough data for indicators
        return None
    
    # Get indicators
    bb_data = indicators.get('daily_bollinger_bands', {})
    stoch_rsi = indicators.get('daily_stochastic_rsi', pd.DataFrame())
    ma10 = indicators.get('ma_10', pd.Series())
    ma20 = indicators.get('ma_20', pd.Series())
    volatility = indicators.get('daily_volatility', pd.Series())
    
    if not bb_data or stoch_rsi.empty or ma10.empty or ma20.empty:
        return None
    
    # Check if previous candles below lower BB
    if not is_below_lower_bb(ohlc_data, bb_data, idx):
        return None
    
    # Check current candle type
    is_green = is_green_candle(ohlc_data, idx)
    is_neutral = is_neutral_candle(ohlc_data, idx)
    
    if not (is_green or is_neutral):
        return None
    
    # Check Stochastic RSI < 20
    if idx >= len(stoch_rsi) or pd.isna(stoch_rsi.iloc[idx]['%K']):
        return None
    
    stoch_k = stoch_rsi.iloc[idx]['%K']
    if stoch_k >= 20:
        return None
    
    # For neutral candles, check additional conditions
    market_direction = None
    if is_neutral:
        vol_similar = check_volatility_similarity(volatility, idx)
        vol_increasing = is_volume_increasing(ohlc_data, idx)
        vol_increased = is_volatility_increased(volatility, idx)
        vol_same = is_volume_same(ohlc_data, idx)
        
        if vol_similar and vol_increasing:
            market_direction = "rising"
        elif vol_same and vol_increased:
            market_direction = "sideways"
        else:
            return None  # Conditions not met for neutral candle
    
    # Calculate SL (below the low)
    current_low = ohlc_data.iloc[idx]['Low']
    prev_low = ohlc_data.iloc[idx - 1]['Low'] if idx > 0 else current_low
    min_low = min(current_low, prev_low)
    
    tick_size = calculate_tick_size(ohlc_data.iloc[idx]['Close'])
    sl1 = min_low - (2 * tick_size)
    
    # Calculate target (average of 10 MA and 20 MA)
    if idx >= len(ma10) or idx >= len(ma20):
        return None
    
    ma10_val = ma10.iloc[idx]
    ma20_val = ma20.iloc[idx]
    
    if pd.isna(ma10_val) or pd.isna(ma20_val):
        return None
    
    # Calculate initial target (will be updated dynamically as MAs change)
    entry_price = ohlc_data.iloc[idx]['Close']
    target = calculate_dynamic_target_case_2a(ma10_val, ma20_val, entry_price)
    
    # For LONG: Target must be ABOVE entry, SL must be BELOW entry
    # Ensure target is above entry (if MAs are below entry, use percentage above)
    if target <= entry_price:
        # If target is below entry, calculate as percentage above entry
        target = entry_price * 1.03  # 3% above entry as default
    
    # SL2: For LONG, SL should be below entry
    # Use percentage below entry based on target distance
    target_pct_above = (target - entry_price) / entry_price
    sl2 = entry_price * (1 - target_pct_above)  # Same percentage below entry
    
    # Final SL is average of SL1 and SL2, but ensure it's below entry
    sl = (sl1 + sl2) / 2
    if sl >= entry_price:
        sl = entry_price * 0.98  # At least 2% below entry
    
    return {
        'case': '2a',
        'direction': 'LONG',  # Long position (expecting price to rise)
        'entry_price': entry_price,
        'stop_loss': sl,  # Fixed at entry
        'target': target,  # Dynamic, updates with 10 MA and 20 MA
        'target_ma10': ma10_val,
        'target_ma20': ma20_val,
        'market_direction': market_direction,
        'stoch_rsi': stoch_k,
        'candle_type': 'green' if is_green else 'neutral',
        'note': 'Target is dynamic and updates with 10 MA and 20 MA. SL is fixed.'
    }


def case_2b_signal(ohlc_data: pd.DataFrame, indicators: Dict, idx: int) -> Optional[Dict]:
    """
    Case 2.b: Price rejection between 20 MA and upper BB
    (Inverse of Case 1.b)
    
    Conditions:
    - Price is on upper side (between 20 MA and upper Bollinger Band)
    - 10 MA and 20 MA are close to each other
    - Price gets rejected (enters range of 20/10 MA, goes down, then comes back above both or rises between middle)
    
    Args:
        ohlc_data: DataFrame with OHLC data
        indicators: Dictionary of calculated indicators
        idx: Current index
        
    Returns:
        Dictionary with signal info or None
    """
    if idx < 20:
        return None
    
    bb_data = indicators.get('daily_bollinger_bands', {})
    ma10 = indicators.get('ma_10', pd.Series())
    ma20 = indicators.get('ma_20', pd.Series())
    volatility = indicators.get('daily_volatility', pd.Series())
    
    if not bb_data or ma10.empty or ma20.empty:
        return None
    
    # bb_data is already the daily_bollinger_bands dict
    if isinstance(bb_data, dict) and 'upper' in bb_data:
        upper_bb = bb_data['upper']
    elif isinstance(bb_data, dict) and 'daily_bollinger_bands' in bb_data:
        upper_bb = bb_data['daily_bollinger_bands']['upper']
    else:
        return None
    
    if idx >= len(ma10) or idx >= len(ma20) or idx >= len(upper_bb):
        return None
    
    ma10_val = ma10.iloc[idx]
    ma20_val = ma20.iloc[idx]
    upper_bb_val = upper_bb.iloc[idx]
    current_price = ohlc_data.iloc[idx]['Close']
    
    if pd.isna(ma10_val) or pd.isna(ma20_val) or pd.isna(upper_bb_val):
        return None
    
    # Check if price is between 20 MA and upper BB
    if not (ma20_val <= current_price <= upper_bb_val):
        return None
    
    # Check if 10 MA and 20 MA are close
    if not are_mas_close(ma10, ma20, threshold_pct=0.02).iloc[idx]:
        return None
    
    # Check for price rejection (simplified: price was below MAs recently, now above)
    if idx < 5:
        return None
    
    # Check if price was below one or both MAs in recent past
    was_below = False
    for i in range(max(0, idx - 5), idx):
        if i < len(ma10) and i < len(ma20):
            price_at_i = ohlc_data.iloc[i]['Close']
            if price_at_i < ma10.iloc[i] or price_at_i < ma20.iloc[i]:
                was_below = True
                break
    
    if not was_below:
        return None
    
    # Check if current price is above both MAs or between them
    is_above_both = current_price > ma10_val and current_price > ma20_val
    is_between = ma10_val < current_price < ma20_val or ma20_val < current_price < ma10_val
    
    if not (is_above_both or is_between):
        return None
    
    # Calculate SL: 1.5-2% below current price based on volatility
    if idx >= len(volatility) or pd.isna(volatility.iloc[idx]):
        vol_factor = 0.0175  # Default 1.75%
    else:
        vol_val = volatility.iloc[idx]
        # Scale SL based on volatility (higher vol = higher SL)
        if vol_val > 0.3:  # High volatility
            vol_factor = 0.02  # 2%
        else:
            vol_factor = 0.015  # 1.5%
    
    sl = current_price * (1 - vol_factor)  # Below entry for long
    
    # Calculate target: high of current or previous candle
    current_high = ohlc_data.iloc[idx]['High']
    prev_high = ohlc_data.iloc[idx - 1]['High'] if idx > 0 else current_high
    target = max(current_high, prev_high)
    
    # If target < 2.5%, then target is avg 3-5% based on volatility
    target_pct = (target - current_price) / current_price
    if target_pct < 0.025:
        if idx >= len(volatility) or pd.isna(volatility.iloc[idx]):
            target_pct = 0.04  # Default 4%
        else:
            vol_val = volatility.iloc[idx]
            if vol_val > 0.3:
                target_pct = 0.05  # 5% for high volatility
            else:
                target_pct = 0.03  # 3% for normal volatility
        target = current_price * (1 + target_pct)  # Above entry for long
    
    # For LONG: Ensure target is ABOVE entry
    if target <= current_price:
        target = current_price * 1.03  # Force 3% above entry
    
    return {
        'case': '2b',
        'direction': 'LONG',  # Long position
        'entry_price': current_price,
        'stop_loss': sl,
        'target': target,
        'ma10': ma10_val,
        'ma20': ma20_val
    }


def case_2c_signal(ohlc_data: pd.DataFrame, indicators: Dict, idx: int) -> Optional[Dict]:
    """
    Case 2.c: Range breakout after consolidation
    (Inverse of Case 1.c)
    
    Conditions:
    - Price closing in range of 2-3% over period of 5+ days
    - Current day price closing above that range → rising market
    
    Args:
        ohlc_data: DataFrame with OHLC data
        indicators: Dictionary of calculated indicators
        idx: Current index
        
    Returns:
        Dictionary with signal info or None
    """
    if idx < 5:
        return None
    
    ma20 = indicators.get('ma_20', pd.Series())
    bb_data = indicators.get('daily_bollinger_bands', {})
    
    if ma20.empty or not bb_data:
        return None
    
    # bb_data is already the daily_bollinger_bands dict
    if isinstance(bb_data, dict) and 'upper' in bb_data:
        upper_bb = bb_data['upper']
    elif isinstance(bb_data, dict) and 'daily_bollinger_bands' in bb_data:
        upper_bb = bb_data['daily_bollinger_bands']['upper']
    else:
        return None
    
    if idx >= len(ma20) or idx >= len(upper_bb):
        return None
    
    ma20_val = ma20.iloc[idx]
    upper_bb_val = upper_bb.iloc[idx]
    current_close = ohlc_data.iloc[idx]['Close']
    
    if pd.isna(ma20_val) or pd.isna(upper_bb_val):
        return None
    
    # Check if price was in 2-3% range for 5+ days
    if idx < 5:
        return None
    
    closes = ohlc_data['Close']
    recent_closes = closes.iloc[max(0, idx - 5):idx]
    
    if len(recent_closes) < 5:
        return None
    
    max_close = recent_closes.max()
    min_close = recent_closes.min()
    range_pct = (max_close - min_close) / min_close
    
    # Check if range is 2-3%
    if not (0.02 <= range_pct <= 0.03):
        return None
    
    # Check if current close is above the range
    if current_close <= max_close:
        return None
    
    # Calculate target based on price position relative to 20 MA
    # For LONG: Target must ALWAYS be ABOVE entry price
    if current_close < ma20_val:
        # Price < 20 MA: target should be above entry, use 20 MA only if it's above entry
        if ma20_val > current_close:
            # Use 20 MA if it's above entry, otherwise use percentage above
            target = max(ma20_val, current_close * 1.03)  # At least 3% above entry
        else:
            target = current_close * 1.03  # 3% above entry
    else:
        # Price > 20 MA: target is upper BB or 3% above entry (whichever is smaller but still above entry)
        target_bb = upper_bb_val
        target_3pct = current_close * 1.03  # 3% above
        target = min(target_bb, target_3pct)
        # Ensure target is above entry
        if target <= current_close:
            target = current_close * 1.03  # Force 3% above entry
    
    return {
        'case': '2c',
        'direction': 'LONG',  # Long position
        'entry_price': current_close,
        'stop_loss': None,  # SL not specified for this case
        'target': target,
        'ma20': ma20_val,
        'range_breakout': True
    }


def detect_decreasing_market_signals(ohlc_data: pd.DataFrame, indicators: Dict, idx: int) -> Optional[Dict]:
    """
    Detect trading signals for decreasing market scenarios
    (Inverse of increasing market signals)
    
    Tries all three cases and returns the first match
    
    Args:
        ohlc_data: DataFrame with OHLC data
        indicators: Dictionary of calculated indicators
        idx: Current index
        
    Returns:
        Dictionary with signal info or None
    """
    # Try Case 2.a first
    signal = case_2a_signal(ohlc_data, indicators, idx)
    if signal:
        return signal
    
    # Try Case 2.b
    signal = case_2b_signal(ohlc_data, indicators, idx)
    if signal:
        return signal
    
    # Try Case 2.c
    signal = case_2c_signal(ohlc_data, indicators, idx)
    if signal:
        return signal
    
    return None

