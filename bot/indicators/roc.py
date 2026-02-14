"""ROC (Rate of Change) indicator."""

import pandas as pd
import numpy as np
from typing import Optional

from bot.core.interfaces import Indicator


class ROC(Indicator):
    """Rate of Change for measuring momentum speed."""
    
    INDICATOR_NAME = "roc"
    
    def __init__(self, period: int = 12):
        """
        Initialize ROC indicator.
        
        Args:
            period: Period for calculation (default 12)
        """
        super().__init__(name=self.INDICATOR_NAME, parameters={})
        self.period = period
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate ROC.
        
        Args:
            data: DataFrame with 'close' column
            
        Returns:
            DataFrame with ROC column added
        """
        df = data.copy()
        
        # ROC as percentage
        df['roc'] = ((df['close'] - df['close'].shift(self.period)) / 
                     df['close'].shift(self.period)) * 100
        
        self.last_calculated = df
        return df
    
    def is_bullish_momentum(self, data: pd.DataFrame, threshold: float = 0) -> bool:
        """Check for bullish momentum."""
        last_row = data.iloc[-1]
        return last_row['roc'] > threshold
    
    def is_bearish_momentum(self, data: pd.DataFrame, threshold: float = 0) -> bool:
        """Check for bearish momentum."""
        last_row = data.iloc[-1]
        return last_row['roc']
    def reset(self):
        """Reset indicator state."""
        self.last_calculated = None
