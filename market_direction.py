"""
Market Direction Detection Module
Determines if a stock is in an increasing, decreasing, sideways, or no-trade market
"""

import pandas as pd
import numpy as np
from typing import Literal, Optional
from datetime import datetime, timedelta


class MarketDirectionDetector:
    """
    Detects market direction based on price movements and patterns.
    
    Cases:
    1. Trending (Increasing/Decreasing): 3%+ move in 2-5 days
    2. Sideways: Body in 0-1.5% range for 7+ days OR 0-3% for 20+ days
    3. No Trade: Moving but doesn't match above patterns
    """
    
    def __init__(self):
        """Initialize the Market Direction Detector."""
        pass
    
    def calculate_body_percentage(self, open_price: float, close_price: float) -> float:
        """
        Calculate the body percentage (open to close change).
        
        Args:
            open_price: Opening price
            close_price: Closing price
        
        Returns:
            Percentage change from open to close
        """
        if open_price == 0:
            return 0.0
        return ((close_price - open_price) / open_price) * 100
    
    def check_trending_market(self, df: pd.DataFrame) -> Optional[Literal['increasing', 'decreasing']]:
        """
        Case 1: Check if stock is trending (increasing or decreasing).
        
        Checks if price moves 3% or more in same direction over 2-5 day periods.
        Formula: (T1 - Tn) / Tn * 100 where n is 2,3,4, or 5
        
        Args:
            df: DataFrame with columns [date, open, high, low, close, volume]
                Must be sorted by date (ascending)
        
        Returns:
            'increasing' if trending up, 'decreasing' if trending down, None otherwise
        """
        if len(df) < 5:
            return None
        
        # Get closing prices (T1 is most recent, Tn is n days prior)
        closes = df['close'].values
        
        # Check 2, 3, 4, and 5 day periods
        for n in [2, 3, 4, 5]:
            if len(closes) < n + 1:
                continue
            
            # T1 is the most recent close (last element)
            # Tn is n days prior (n elements before last)
            T1 = closes[-1]
            Tn = closes[-(n + 1)]
            
            # Calculate percentage change
            if Tn == 0:
                continue
            
            percentage_change = ((T1 - Tn) / Tn) * 100
            
            # Check if it's a significant move (>= 3% or <= -3%)
            if percentage_change >= 3.0:
                return 'increasing'
            elif percentage_change <= -3.0:
                return 'decreasing'
        
        return None
    
    def check_sideways_market(self, df: pd.DataFrame) -> bool:
        """
        Case 2: Check if stock is in sideways market.
        
        Conditions:
        - Body (open to close) in 0-1.5% range for 7+ consecutive days, OR
        - Body in 0-3% range for 20+ consecutive days
        
        Args:
            df: DataFrame with columns [date, open, high, low, close, volume]
                Must be sorted by date (ascending)
        
        Returns:
            True if sideways, False otherwise
        """
        if len(df) < 7:
            return False
        
        # Calculate body percentage for each day
        body_percentages = []
        for _, row in df.iterrows():
            body_pct = abs(self.calculate_body_percentage(row['open'], row['close']))
            body_percentages.append(body_pct)
        
        body_percentages = np.array(body_percentages)
        
        # Check for 7+ days with body in 0-1.5% range
        condition_1 = body_percentages <= 1.5
        consecutive_1_5 = self._find_max_consecutive(condition_1)
        if consecutive_1_5 >= 7:
            return True
        
        # Check for 20+ days with body in 0-3% range
        condition_2 = body_percentages <= 3.0
        consecutive_3 = self._find_max_consecutive(condition_2)
        if consecutive_3 >= 20:
            return True
        
        return False
    
    def _find_max_consecutive(self, condition_array: np.ndarray) -> int:
        """
        Find maximum consecutive True values in a boolean array.
        
        Args:
            condition_array: Boolean numpy array
        
        Returns:
            Maximum number of consecutive True values
        """
        if len(condition_array) == 0:
            return 0
        
        max_consecutive = 0
        current_consecutive = 0
        
        for value in condition_array:
            if value:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def determine_direction(
        self, 
        df: pd.DataFrame,
        lookback_days: Optional[int] = None
    ) -> Literal['increasing', 'decreasing', 'sideways', 'no_trade']:
        """
        Determine market direction based on all cases.
        
        Priority:
        1. Check for trending market (Case 1)
        2. Check for sideways market (Case 2)
        3. Otherwise, mark as no_trade (Case 3)
        
        Args:
            df: DataFrame with columns [date, open, high, low, close, volume]
                Must be sorted by date (ascending)
            lookback_days: Number of recent days to analyze (None = use all data)
        
        Returns:
            'increasing', 'decreasing', 'sideways', or 'no_trade'
        """
        # Ensure data is sorted by date
        df = df.sort_values('date').reset_index(drop=True)
        
        # Use only recent data if lookback_days is specified
        if lookback_days is not None and len(df) > lookback_days:
            df = df.tail(lookback_days).reset_index(drop=True)
        
        # Case 1: Check for trending market
        trend = self.check_trending_market(df)
        if trend is not None:
            return trend
        
        # Case 2: Check for sideways market
        if self.check_sideways_market(df):
            return 'sideways'
        
        # Case 3: No trade (moving but doesn't match patterns)
        return 'no_trade'
    
    def analyze_stock(
        self,
        df: pd.DataFrame,
        lookback_days: Optional[int] = None,
        return_details: bool = False
    ) -> dict:
        """
        Comprehensive analysis of stock market direction.
        
        Args:
            df: DataFrame with columns [date, open, high, low, close, volume]
            lookback_days: Number of recent days to analyze (None = use all data)
            return_details: If True, returns additional analysis details
        
        Returns:
            Dictionary with direction and optional details
        """
        # Ensure data is sorted
        df = df.sort_values('date').reset_index(drop=True)
        
        # Use only recent data if specified
        analysis_df = df.copy()
        if lookback_days is not None and len(df) > lookback_days:
            analysis_df = df.tail(lookback_days).reset_index(drop=True)
        
        # Determine direction
        direction = self.determine_direction(analysis_df)
        
        result = {
            'direction': direction,
            'analysis_date': df['date'].max() if len(df) > 0 else None,
            'total_days_analyzed': len(analysis_df)
        }
        
        if return_details:
            # Add detailed information
            result['details'] = {
                'trending_check': self.check_trending_market(analysis_df),
                'sideways_check': self.check_sideways_market(analysis_df),
                'recent_closes': analysis_df['close'].tail(5).tolist() if len(analysis_df) >= 5 else analysis_df['close'].tolist(),
                'price_range': {
                    'min': float(analysis_df['low'].min()),
                    'max': float(analysis_df['high'].max()),
                    'current': float(analysis_df['close'].iloc[-1])
                }
            }
            
            # Calculate body percentages for recent days
            recent_body_pct = []
            for _, row in analysis_df.tail(20).iterrows():
                body_pct = self.calculate_body_percentage(row['open'], row['close'])
                recent_body_pct.append(abs(body_pct))
            result['details']['recent_body_percentages'] = recent_body_pct[-10:] if len(recent_body_pct) > 10 else recent_body_pct
        
        return result


# Convenience function
def determine_market_direction(
    df: pd.DataFrame,
    lookback_days: Optional[int] = None
) -> Literal['increasing', 'decreasing', 'sideways', 'no_trade']:
    """
    Quick function to determine market direction.
    
    Args:
        df: DataFrame with columns [date, open, high, low, close, volume]
        lookback_days: Number of recent days to analyze (None = use all data)
    
    Returns:
        'increasing', 'decreasing', 'sideways', or 'no_trade'
    """
    detector = MarketDirectionDetector()
    return detector.determine_direction(df, lookback_days)


if __name__ == "__main__":
    # Example usage
    print("Market Direction Detector - Example")
    print("=" * 50)
    print("\nThis module determines market direction based on:")
    print("  Case 1: Trending - 3%+ move in 2-5 days")
    print("  Case 2: Sideways - Body in 0-1.5% for 7+ days OR 0-3% for 20+ days")
    print("  Case 3: No Trade - Moving but doesn't match patterns")
    print("\nUse with stock data loaded from data_loader.py")

