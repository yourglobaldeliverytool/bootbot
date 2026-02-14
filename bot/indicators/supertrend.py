"""SuperTrend indicator."""

import pandas as pd
import numpy as np
from typing import Optional

from bot.core.interfaces import Indicator


class SuperTrend(Indicator):
    """SuperTrend for trend following."""
    
    INDICATOR_NAME = "supertrend"
    
    def __init__(self, period: int = 10, multiplier: float = 3.0):
        """
        Initialize SuperTrend indicator.
        
        Args:
            period: Period for ATR (default 10)
            multiplier: ATR multiplier (default 3.0)
        """
        super().__init__(name=self.INDICATOR_NAME, parameters={})
        self.period = period
        self.multiplier = multiplier
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate SuperTrend.
        
        Args:
            data: DataFrame with 'high', 'low', 'close' columns
            
        Returns:
            DataFrame with SuperTrend columns added
        """
        df = data.copy()
        
        # ATR
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift(1))
        low_close = abs(df['low'] - df['close'].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=self.period).mean()
        
        # SuperTrend calculation
        hl2 = (df['high'] + df['low']) / 2
        upper_band = hl2 + (self.multiplier * atr)
        lower_band = hl2 - (self.multiplier * atr)
        
        supertrend = [np.nan]
        direction = [1]
        
        for i in range(1, len(df)):
            if df['close'].iloc[i] > upper_band.iloc[i - 1]:
                direction.append(1)
            elif df['close'].iloc[i] < lower_band.iloc[i - 1]:
                direction.append(-1)
            else:
                direction.append(direction[-1])
            
            if direction[-1] == 1:
                supertrend.append(lower_band.iloc[i])
            else:
                supertrend.append(upper_band.iloc[i])
        
        df['supertrend'] = supertrend
        df['supertrend_direction'] = direction
        
        self.last_calculated = df
        return df
    
    def get_signal(self, data: pd.DataFrame) -> Optional[str]:
        """
        Get SuperTrend signal.
        
        Args:
            data: DataFrame with SuperTrend data
            
        Returns:
            'BUY' if price above SuperTrend, 'SELL' if below, None otherwise
        """
        if len(data) < 1:
            return None
        
        last_row = data.iloc[-1]
        if pd.isna(last_row['supertrend']):
            return None
        
        if last_row['supertrend_direction'] == 1:
            return 'BUY'
        else:
            return 'SELL'
    def reset(self):
        """Reset indicator state."""
        self.last_calculated = None
