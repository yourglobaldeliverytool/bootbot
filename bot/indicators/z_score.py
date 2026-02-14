"""Z-Score indicator for statistical analysis."""

import pandas as pd
import numpy as np
from typing import Optional

from bot.core.interfaces import Indicator


class ZScore(Indicator):
    """Z-Score for mean reversion and statistical analysis."""
    
    INDICATOR_NAME = "z_score"
    
    def __init__(self, period: int = 20):
        """
        Initialize Z-Score indicator.
        
        Args:
            period: Period for calculation (default 20)
        """
        super().__init__(name=self.INDICATOR_NAME, parameters={})
        self.period = period
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Z-Score.
        
        Args:
            data: DataFrame with 'close' column
            
        Returns:
            DataFrame with Z-Score column added
        """
        df = data.copy()
        
        # Mean and standard deviation
        df['z_score_mean'] = df['close'].rolling(window=self.period).mean()
        df['z_score_std'] = df['close'].rolling(window=self.period).std()
        
        # Z-Score
        df['z_score'] = (df['close'] - df['z_score_mean']) / df['z_score_std']
        
        self.last_calculated = df
        return df
    
    def is_overextended_up(self, data: pd.DataFrame, threshold: float = 2.0) -> bool:
        """Check if price is overextended to upside."""
        last_row = data.iloc[-1]
        return last_row['z_score'] > threshold
    
    def is_overextended_down(self, data: pd.DataFrame, threshold: float = -2.0) -> bool:
        """Check if price is overextended to downside."""
        last_row = data.iloc[-1]
        return last_row['z_score']
    def reset(self):
        """Reset indicator state."""
        self.last_calculated = None
