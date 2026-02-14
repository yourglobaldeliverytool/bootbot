"""Williams %R indicator."""

import pandas as pd
import numpy as np
from typing import Optional

from bot.core.interfaces import Indicator


class WilliamsR(Indicator):
    """Williams %R for momentum and overbought/oversold conditions."""
    
    INDICATOR_NAME = "williams_r"
    
    def __init__(self, period: int = 14):
        """
        Initialize Williams %R indicator.
        
        Args:
            period: Period for calculation (default 14)
        """
        super().__init__(name=self.INDICATOR_NAME, parameters={})
        self.period = period
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Williams %R.
        
        Args:
            data: DataFrame with 'high', 'low', 'close' columns
            
        Returns:
            DataFrame with Williams %R column added
        """
        df = data.copy()
        
        # Highest high and lowest low
        df['high_max'] = df['high'].rolling(window=self.period).max()
        df['low_min'] = df['low'].rolling(window=self.period).min()
        
        # Williams %R
        df['williams_r'] = -100 * (
            (df['high_max'] - df['close']) / (df['high_max'] - df['low_min'])
        )
        
        self.last_calculated = df
        return df
    
    def is_overbought(self, data: pd.DataFrame, threshold: float = -20) -> bool:
        """Check if overbought."""
        last_row = data.iloc[-1]
        return last_row['williams_r'] > threshold
    
    def is_oversold(self, data: pd.DataFrame, threshold: float = -80) -> bool:
        """Check if oversold."""
        last_row = data.iloc[-1]
        return last_row['williams_r']
    def reset(self):
        """Reset indicator state."""
        self.last_calculated = None
