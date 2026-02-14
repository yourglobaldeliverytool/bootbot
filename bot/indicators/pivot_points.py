"""Pivot Points indicator."""

import pandas as pd
import numpy as np
from typing import Optional

from bot.core.interfaces import Indicator


class PivotPoints(Indicator):
    """Pivot Points for support/resistance levels."""
    
    INDICATOR_NAME = "pivot_points"
    
    def __init__(self):
        """Initialize Pivot Points indicator."""
        super().__init__(name=self.INDICATOR_NAME, parameters={})
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Pivot Points (Daily).
        
        Args:
            data: DataFrame with 'high', 'low', 'close' columns
            
        Returns:
            DataFrame with Pivot Points columns added
        """
        df = data.copy()
        
        # Traditional Pivot Points (using previous day's data)
        df['pivot'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
        
        # Resistance levels
        df['r1'] = 2 * df['pivot'] - df['low'].shift(1)
        df['r2'] = df['pivot'] + (df['high'].shift(1) - df['low'].shift(1))
        df['r3'] = df['high'].shift(1) + 2 * (df['pivot'] - df['low'].shift(1))
        
        # Support levels
        df['s1'] = 2 * df['pivot'] - df['high'].shift(1)
        df['s2'] = df['pivot'] - (df['high'].shift(1) - df['low'].shift(1))
        df['s3'] = df['low'].shift(1) - 2 * (df['high'].shift(1) - df['pivot'])
        
        self.last_calculated = df
        return df
    
    def get_position(self, data: pd.DataFrame) -> str:
        """
        Get price position relative to pivot.
        
        Args:
            data: DataFrame with Pivot data
            
        Returns:
            'ABOVE_R2', 'ABOVE_R1', 'BEARISH', 'AT_PIVOT', 'BULLISH', 'BELOW_S1', 'BELOW_S2'
        """
        last_row = data.iloc[-1]
        close = last_row['close']
        pivot = last_row['pivot']
        r1 = last_row['r1']
        s1 = last_row['s1']
        
        if close > r1:
            return 'ABOVE_R1'
        elif close > pivot:
            return 'BULLISH'
        elif close < s1:
            return 'BELOW_S1'
        else:
            return 'BEARISH'
    def reset(self):
        """Reset indicator state."""
        self.last_calculated = None
