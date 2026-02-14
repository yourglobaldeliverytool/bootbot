"""Donchian Channels indicator."""

import pandas as pd
import numpy as np
from typing import Optional

from bot.core.interfaces import Indicator


class DonchianChannels(Indicator):
    """Donchian Channels for breakout trading."""
    
    INDICATOR_NAME = "donchian_channels"
    
    def __init__(self, period: int = 20):
        """
        Initialize Donchian Channels indicator.
        
        Args:
            period: Period for high/low lookback (default 20)
        """
        super().__init__(name=self.INDICATOR_NAME, parameters={})
        self.period = period
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Donchian Channels.
        
        Args:
            data: DataFrame with 'high', 'low' columns
            
        Returns:
            DataFrame with Donchian Channels columns added
        """
        df = data.copy()
        
        # Upper channel (highest high)
        df['dc_upper'] = df['high'].rolling(window=self.period).max()
        
        # Lower channel (lowest low)
        df['dc_lower'] = df['low'].rolling(window=self.period).min()
        
        # Middle channel
        df['dc_middle'] = (df['dc_upper'] + df['dc_lower']) / 2
        
        self.last_calculated = df
        return df
    
    def has_breakout(self, data: pd.DataFrame) -> Optional[str]:
        """
        Check for breakout.
        
        Args:
            data: DataFrame with Donchian data
            
        Returns:
            'BULLISH' if price breaks above upper, 'BEARISH' if below lower, None otherwise
        """
        if len(data) < 2:
            return None
        
        prev_row = data.iloc[-2]
        curr_row = data.iloc[-1]
        
        # Bullish breakout: price closes above upper channel
        if prev_row['close'] <= prev_row['dc_upper'] and curr_row['close'] > curr_row['dc_upper']:
            return 'BULLISH'
        
        # Bearish breakout: price closes below lower channel
        if prev_row['close'] >= prev_row['dc_lower'] and curr_row['close'] < curr_row['dc_lower']:
            return 'BEARISH'
        
        return None
    def reset(self):
        """Reset indicator state."""
        self.last_calculated = None
