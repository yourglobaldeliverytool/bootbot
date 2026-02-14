"""CCI (Commodity Channel Index) indicator."""

import pandas as pd
import numpy as np
from typing import Optional

from bot.core.interfaces import Indicator


class CCI(Indicator):
    """Commodity Channel Index for identifying cyclical trends."""
    
    INDICATOR_NAME = "cci"
    
    def __init__(self, period: int = 20):
        """
        Initialize CCI indicator.
        
        Args:
            period: Period for calculation (default 20)
        """
        super().__init__(name=self.INDICATOR_NAME, parameters={})
        self.period = period
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate CCI.
        
        Args:
            data: DataFrame with 'high', 'low', 'close' columns
            
        Returns:
            DataFrame with CCI column added
        """
        df = data.copy()
        
        # Typical Price
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        
        # SMA of Typical Price
        df['tp_sma'] = df['typical_price'].rolling(window=self.period).mean()
        
        # Mean Deviation
        df['tp_dev'] = abs(df['typical_price'] - df['tp_sma'])
        df['mean_dev'] = df['tp_dev'].rolling(window=self.period).mean()
        
        # CCI
        df['cci'] = (df['typical_price'] - df['tp_sma']) / (0.015 * df['mean_dev'])
        
        self.last_calculated = df
        return df
    
    def is_overbought(self, data: pd.DataFrame, threshold: float = 100) -> bool:
        """Check if overbought."""
        last_row = data.iloc[-1]
        return last_row['cci'] > threshold
    
    def is_oversold(self, data: pd.DataFrame, threshold: float = -100) -> bool:
        """Check if oversold."""
        last_row = data.iloc[-1]
        return last_row['cci'] < threshold
    def reset(self):
        """Reset indicator state."""
        self.last_calculated = None
