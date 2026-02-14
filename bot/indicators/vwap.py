"""VWAP (Volume Weighted Average Price) indicator."""

import pandas as pd
import numpy as np
from typing import Optional

from bot.core.interfaces import Indicator


class VWAP(Indicator):
    """Volume Weighted Average Price indicator."""
    
    INDICATOR_NAME = "vwap"
    
    def __init__(self):
        """Initialize VWAP indicator."""
        super().__init__(name=self.INDICATOR_NAME, parameters={})
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate VWAP.
        
        Note: This is a session-based VWAP. For intraday, typically
        resets at start of trading session. Here we calculate cumulative VWAP.
        
        Args:
            data: DataFrame with 'high', 'low', 'close', 'volume' columns
            
        Returns:
            DataFrame with VWAP column added
        """
        df = data.copy()
        
        # Typical price
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        
        # VWAP calculation
        df['vwap'] = (df['typical_price'] * df['volume']).cumsum() / df['volume'].cumsum()
        
        self.last_calculated = df
        return df
    
    def get_signal(self, data: pd.DataFrame) -> str:
        """
        Get trading signal based on VWAP.
        
        Args:
            data: DataFrame with VWAP data
            
        Returns:
            'BUY' if price below VWAP, 'SELL' if above, 'HOLD' otherwise
        """
        last_row = data.iloc[-1]
        
        if last_row['close'] < last_row['vwap']:
            return 'BUY'
        elif last_row['close'] > last_row['vwap']:
            return 'SELL'
        
        return 'HOLD'
    def reset(self):
        """Reset indicator state."""
        self.last_calculated = None
