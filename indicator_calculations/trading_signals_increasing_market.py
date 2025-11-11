"""
Trading Signals for Increasing Market
Implements three cases for detecting falling/sideways market signals during uptrends
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from .moving_averages_calc import calculate_10_ma, calculate_20_ma, are_mas_close
from .bollinger_bands_calc import calculate_bollinger_bands
from .stochastic_rsi_calc import calculate_stochastic_rsi
from .volatility_calc import calculate_volatility


def is_red_candle(ohlc_data: pd.DataFrame, idx: int) -> bool:
    """
    Check if candle is red (open > close)
    
    Args:
        ohlc_data: DataFrame with OHLC data
        idx: Index of the candle
        
    Returns:
        True if red candle, False otherwise
    """
    if idx >= len(ohlc_data):
        return False
    return ohlc_data.iloc[idx]['Open'] > ohlc_data.iloc[idx]['Close']


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


def is_above_upper_bb(ohlc_data: pd.DataFrame, bb_data: Dict, idx: int, lookback: int = 3) -> bool:
    """
    Check if previous candle(s) are above upper Bollinger Band
    
    Args:
        ohlc_data: DataFrame with OHLC data
        bb_data: Bollinger Bands data dictionary
        idx: Current index
        lookback: Number of previous candles to check
        
    Returns:
        True if any previous candle is above upper BB
    """
    if idx < lookback:
        return False
    
    # bb_data is already the daily_bollinger_bands dict with 'upper', 'middle', 'lower' keys
    if isinstance(bb_data, dict) and 'upper' in bb_data:
        upper_bb = bb_data['upper']
    elif isinstance(bb_data, dict) and 'daily_bollinger_bands' in bb_data:
        upper_bb = bb_data['daily_bollinger_bands']['upper']
    else:
        return False
    closes = ohlc_data['Close']
    
    for i in range(max(0, idx - lookback), idx):
        if i < len(upper_bb) and not pd.isna(upper_bb.iloc[i]):
            if closes.iloc[i] > upper_bb.iloc[i]:
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


def is_volume_decreasing(ohlc_data: pd.DataFrame, idx: int, lookback: int = 3) -> bool:
    """
    Check if volume is decreasing relative to previous candles
    
    Args:
        ohlc_data: DataFrame with OHLC data
        idx: Current index
        lookback: Number of previous candles to compare
        
    Returns:
        True if volume is decreasing
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
    return current_volume < avg_prev_volume


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


def is_volatility_decreased(volatility_data: pd.Series, idx: int, lookback: int = 3) -> bool:
    """
    Check if volatility has decreased compared to previous candles
    
    Args:
        volatility_data: Series of volatility values
        idx: Current index
        lookback: Number of previous candles to compare
        
    Returns:
        True if volatility decreased
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
    return current_vol < avg_prev_vol


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


def calculate_dynamic_target_case_1a(ma10_val: float, ma20_val: float, entry_price: float, 
                                     current_price: float = None) -> float:
    """
    Calculate dynamic target for Case 1.a
    Target is average of 10 MA and 20 MA, or just below 10 MA if in profits
    
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
    
    # Check if in profits (current price is below entry, meaning we're short and price fell)
    # For short positions, we're in profit when price decreases
    is_in_profits = current_price < entry_price
    
    if is_in_profits:
        # When in profits, target is just below 10 MA
        target = ma10_val * 0.995  # 0.5% below 10 MA
    else:
        # Initial target is average of 10 MA and 20 MA
        target = (ma10_val + ma20_val) / 2
    
    # For SHORT trades, target must be BELOW entry price
    # If calculated target is above entry, use a percentage below entry
    if target >= entry_price:
        target = entry_price * 0.97  # 3% below entry
    
    return target


def case_1a_signal(ohlc_data: pd.DataFrame, indicators: Dict, idx: int) -> Optional[Dict]:
    """
    Case 1.a: Upper BB rejection with red/neutral candle and Stoch RSI > 80
    
    Conditions:
    - Previous candle(s) above upper Bollinger Band
    - Current candle is red (open > close) or neutral (open very close to close)
    - Stochastic RSI > 80
    - If neutral: volatility similar (10-20%) and volume decreasing → falling market
    - If neutral: volume same and volatility decreased → sideways market
    
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
    
    # Check if previous candles above upper BB
    if not is_above_upper_bb(ohlc_data, bb_data, idx):
        return None
    
    # Check current candle type
    is_red = is_red_candle(ohlc_data, idx)
    is_neutral = is_neutral_candle(ohlc_data, idx)
    
    if not (is_red or is_neutral):
        return None
    
    # Check Stochastic RSI > 80
    if idx >= len(stoch_rsi) or pd.isna(stoch_rsi.iloc[idx]['%K']):
        return None
    
    stoch_k = stoch_rsi.iloc[idx]['%K']
    if stoch_k <= 80:
        return None
    
    # For neutral candles, check additional conditions
    market_direction = None
    if is_neutral:
        vol_similar = check_volatility_similarity(volatility, idx)
        vol_decreasing = is_volume_decreasing(ohlc_data, idx)
        vol_decreased = is_volatility_decreased(volatility, idx)
        vol_same = is_volume_same(ohlc_data, idx)
        
        if vol_similar and vol_decreasing:
            market_direction = "falling"
        elif vol_same and vol_decreased:
            market_direction = "sideways"
        else:
            return None  # Conditions not met for neutral candle
    
    # Calculate SL
    current_high = ohlc_data.iloc[idx]['High']
    prev_high = ohlc_data.iloc[idx - 1]['High'] if idx > 0 else current_high
    max_high = max(current_high, prev_high)
    
    tick_size = calculate_tick_size(ohlc_data.iloc[idx]['Close'])
    sl1 = max_high + (2 * tick_size)
    
    # Calculate target (average of 10 MA and 20 MA)
    if idx >= len(ma10) or idx >= len(ma20):
        return None
    
    ma10_val = ma10.iloc[idx]
    ma20_val = ma20.iloc[idx]
    
    if pd.isna(ma10_val) or pd.isna(ma20_val):
        return None
    
    # Calculate initial target (will be updated dynamically as MAs change)
    entry_price = ohlc_data.iloc[idx]['Close']
    target = calculate_dynamic_target_case_1a(ma10_val, ma20_val, entry_price)
    
    # For SHORT: Target must be BELOW entry, SL must be ABOVE entry
    # Ensure target is below entry (if MAs are above entry, use percentage below)
    if target >= entry_price:
        # If target is above entry, calculate as percentage below entry
        target = entry_price * 0.97  # 3% below entry as default
    
    # SL2: For SHORT, SL should be above entry (inverse of target percentage)
    # If target is X% below entry, SL should be X% above entry
    target_pct_below = (entry_price - target) / entry_price
    sl2 = entry_price * (1 + target_pct_below)  # Same percentage above entry
    
    # Final SL is average of SL1 and SL2, but ensure it's above entry
    sl = (sl1 + sl2) / 2
    if sl <= entry_price:
        sl = entry_price * 1.02  # At least 2% above entry
    
    return {
        'case': '1a',
        'direction': 'SHORT',  # Short position (expecting price to fall)
        'entry_price': entry_price,
        'stop_loss': sl,  # Fixed at entry
        'target': target,  # Dynamic, updates with 10 MA and 20 MA
        'target_ma10': ma10_val,
        'target_ma20': ma20_val,
        'market_direction': market_direction,
        'stoch_rsi': stoch_k,
        'candle_type': 'red' if is_red else 'neutral',
        'note': 'Target is dynamic and updates with 10 MA and 20 MA. SL is fixed.'
    }


def case_1b_signal(ohlc_data: pd.DataFrame, indicators: Dict, idx: int) -> Optional[Dict]:
    """
    Case 1.b: Price rejection between 20 MA and lower BB
    
    Conditions:
    - Price is on lower side (between 20 MA and lower Bollinger Band)
    - 10 MA and 20 MA are close to each other
    - Price gets rejected (enters range of 20/10 MA, goes up, then comes back below both or falls between middle)
    
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
    if isinstance(bb_data, dict) and 'lower' in bb_data:
        lower_bb = bb_data['lower']
    elif isinstance(bb_data, dict) and 'daily_bollinger_bands' in bb_data:
        lower_bb = bb_data['daily_bollinger_bands']['lower']
    else:
        return None
    
    if idx >= len(ma10) or idx >= len(ma20) or idx >= len(lower_bb):
        return None
    
    ma10_val = ma10.iloc[idx]
    ma20_val = ma20.iloc[idx]
    lower_bb_val = lower_bb.iloc[idx]
    current_price = ohlc_data.iloc[idx]['Close']
    
    if pd.isna(ma10_val) or pd.isna(ma20_val) or pd.isna(lower_bb_val):
        return None
    
    # Check if price is between 20 MA and lower BB
    if not (lower_bb_val <= current_price <= ma20_val):
        return None
    
    # Check if 10 MA and 20 MA are close
    if not are_mas_close(ma10, ma20, threshold_pct=0.02).iloc[idx]:
        return None
    
    # Check for price rejection (simplified: price was above MAs recently, now below)
    if idx < 5:
        return None
    
    # Check if price was above one or both MAs in recent past
    was_above = False
    for i in range(max(0, idx - 5), idx):
        if i < len(ma10) and i < len(ma20):
            price_at_i = ohlc_data.iloc[i]['Close']
            if price_at_i > ma10.iloc[i] or price_at_i > ma20.iloc[i]:
                was_above = True
                break
    
    if not was_above:
        return None
    
    # Check if current price is below both MAs or between them
    is_below_both = current_price < ma10_val and current_price < ma20_val
    is_between = ma10_val < current_price < ma20_val or ma20_val < current_price < ma10_val
    
    if not (is_below_both or is_between):
        return None
    
    # Calculate SL: 1.5-2% above current price based on volatility
    if idx >= len(volatility) or pd.isna(volatility.iloc[idx]):
        vol_factor = 0.0175  # Default 1.75%
    else:
        vol_val = volatility.iloc[idx]
        # Scale SL based on volatility (higher vol = higher SL)
        if vol_val > 0.3:  # High volatility
            vol_factor = 0.02  # 2%
        else:
            vol_factor = 0.015  # 1.5%
    
    sl = current_price * (1 + vol_factor)
    
    # Calculate target: low of current or previous candle
    current_low = ohlc_data.iloc[idx]['Low']
    prev_low = ohlc_data.iloc[idx - 1]['Low'] if idx > 0 else current_low
    target = min(current_low, prev_low)
    
    # If target < 2.5%, then target is avg 3-5% based on volatility
    target_pct = (current_price - target) / current_price
    if target_pct < 0.025:
        if idx >= len(volatility) or pd.isna(volatility.iloc[idx]):
            target_pct = 0.04  # Default 4%
        else:
            vol_val = volatility.iloc[idx]
            if vol_val > 0.3:
                target_pct = 0.05  # 5% for high volatility
            else:
                target_pct = 0.03  # 3% for normal volatility
        target = current_price * (1 - target_pct)
    
    # For SHORT: Ensure target is BELOW entry
    if target >= current_price:
        target = current_price * 0.97  # Force 3% below entry
    
    return {
        'case': '1b',
        'direction': 'SHORT',  # Short position (expecting price to fall)
        'entry_price': current_price,
        'stop_loss': sl,
        'target': target,
        'ma10': ma10_val,
        'ma20': ma20_val
    }


def case_1c_signal(ohlc_data: pd.DataFrame, indicators: Dict, idx: int) -> Optional[Dict]:
    """
    Case 1.c: Range breakdown after consolidation
    
    Conditions:
    - Price closing in range of 2-3% over period of 5+ days
    - Current day price closing below that range → falling market
    
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
    if isinstance(bb_data, dict) and 'lower' in bb_data:
        lower_bb = bb_data['lower']
    elif isinstance(bb_data, dict) and 'daily_bollinger_bands' in bb_data:
        lower_bb = bb_data['daily_bollinger_bands']['lower']
    else:
        return None
    
    if idx >= len(ma20) or idx >= len(lower_bb):
        return None
    
    ma20_val = ma20.iloc[idx]
    lower_bb_val = lower_bb.iloc[idx]
    current_close = ohlc_data.iloc[idx]['Close']
    
    if pd.isna(ma20_val) or pd.isna(lower_bb_val):
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
    
    # Check if current close is below the range
    if current_close >= min_close:
        return None
    
    # Calculate target based on price position relative to 20 MA
    # For SHORT: Target must ALWAYS be BELOW entry price
    if current_close > ma20_val:
        # Price > 20 MA: target should be below entry, use 20 MA only if it's below entry
        if ma20_val < current_close:
            # Use 20 MA if it's below entry, otherwise use percentage below
            target = min(ma20_val, current_close * 0.97)  # At most 3% below entry
        else:
            target = current_close * 0.97  # 3% below entry
    else:
        # Price < 20 MA: target is lower BB or 3% below entry (whichever is bigger but still below entry)
        target_bb = lower_bb_val
        target_3pct = current_close * 0.97  # 3% below
        target = max(target_bb, target_3pct)
        # Ensure target is below entry
        if target >= current_close:
            target = current_close * 0.97  # Force 3% below entry
    
    return {
        'case': '1c',
        'direction': 'SHORT',  # Short position (expecting price to fall)
        'entry_price': current_close,
        'stop_loss': None,  # SL not specified for this case
        'target': target,
        'ma20': ma20_val,
        'range_breakdown': True
    }


def detect_increasing_market_signals(ohlc_data: pd.DataFrame, indicators: Dict, idx: int) -> Optional[Dict]:
    """
    Detect trading signals for increasing market scenarios
    
    Tries all three cases and returns the first match
    
    Args:
        ohlc_data: DataFrame with OHLC data
        indicators: Dictionary of calculated indicators
        idx: Current index
        
    Returns:
        Dictionary with signal info or None
    """
    # Try Case 1.a first
    signal = case_1a_signal(ohlc_data, indicators, idx)
    if signal:
        return signal
    
    # Try Case 1.b
    signal = case_1b_signal(ohlc_data, indicators, idx)
    if signal:
        return signal
    
    # Try Case 1.c
    signal = case_1c_signal(ohlc_data, indicators, idx)
    if signal:
        return signal
    
    return None

