"""Keltner Channels indicator."""

import pandas as pd
import numpy as np
from typing import Optional

from bot.core.interfaces import Indicator


class KeltnerChannels(Indicator):
    """Keltner Channels for volatility and trend following."""
    
    INDICATOR_NAME = "keltner_channels"
    
    def __init__(self, period: int = 20, atr_period: int = 10, mult: float = 2.0):
        """
        Initialize Keltner Channels indicator.
        
        Args:
            period: Period for EMA (default 20)
            atr_period: Period for ATR (default 10)
            mult: ATR multiplier (default 2.0)
        """
        super().__init__(name=self.INDICATOR_NAME, parameters={})
        self.period = period
        self.atr_period = atr_period
        self.mult = mult
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Keltner Channels.
        
        Args:
            data: DataFrame with 'high', 'low', 'close' columns
            
        Returns:
            DataFrame with Keltner Channels columns added
        """
        df = data.copy()
        
        # EMA (middle line)
        df['kc_middle'] = df['close'].ewm(span=self.period, adjust=False).mean()
        
        # ATR
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift(1))
        low_close = abs(df['low'] - df['close'].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['kc_atr'] = tr.ewm(span=self.atr_period, adjust=False).mean()
        
        # Upper and lower channels
        df['kc_upper'] = df['kc_middle'] + (self.mult * df['kc_atr'])
        df['kc_lower'] = df['kc_middle'] - (self.mult * df['kc_atr'])
        
        self.last_calculated = df
        return df
    
    def is_squeeze(self, data: pd.DataFrame, threshold: float = 0.01) -> bool:
        """Check if channels are squeezing."""
        last_row = data.iloc[-1]
        bandwidth = (last_row['kc_upper'] - last_row['kc_lower']) / last_row['kc_middle']
        return bandwidth < threshold
    def reset(self):
        """Reset indicator state."""
        self.last_calculated = None
