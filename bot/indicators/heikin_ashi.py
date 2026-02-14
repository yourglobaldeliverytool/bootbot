"""Heikin Ashi candles."""

import pandas as pd
import numpy as np
from typing import Optional

from bot.core.interfaces import Indicator


class HeikinAshi(Indicator):
    """Heikin Ashi candles for trend identification."""
    
    INDICATOR_NAME = "heikin_ashi"
    
    def __init__(self):
        """Initialize Heikin Ashi indicator."""
        super().__init__(name=self.INDICATOR_NAME, parameters={})
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Heikin Ashi candles.
        
        Args:
            data: DataFrame with 'open', 'high', 'low', 'close' columns
            
        Returns:
            DataFrame with Heikin Ashi columns added
        """
        df = data.copy()
        
        # Calculate Heikin Ashi candles
        df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
        
        ha_open = [(df.iloc[0]['open'] + df.iloc[0]['close']) / 2]
        for i in range(1, len(df)):
            ha_open.append((ha_open[i-1] + df.iloc[i-1]['ha_close']) / 2)
        
        df['ha_open'] = ha_open
        
        df['ha_high'] = df[['high', 'ha_open', 'ha_close']].max(axis=1)
        df['ha_low'] = df[['low', 'ha_open', 'ha_close']].min(axis=1)
        
        self.last_calculated = df
        return df
    
    def get_trend(self, data: pd.DataFrame) -> str:
        """
        Get trend from Heikin Ashi candles.
        
        Args:
            data: DataFrame with Heikin Ashi data
            
        Returns:
            'BULLISH' if HA candles are green, 'BEARISH' if red
        """
        last_row = data.iloc[-1]
        if last_row['ha_close'] > last_row['ha_open']:
            return 'BULLISH'
        else:
            return 'BEARISH'
    def reset(self):
        """Reset indicator state."""
        self.last_calculated = None
