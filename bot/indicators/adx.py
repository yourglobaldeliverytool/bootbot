"""ADX (Average Directional Index) indicator."""

import pandas as pd
import numpy as np
from typing import Optional

from bot.core.interfaces import Indicator


class ADX(Indicator):
    """Average Directional Index for trend strength."""
    
    INDICATOR_NAME = "adx"
    
    def __init__(self, period: int = 14):
        """
        Initialize ADX indicator.
        
        Args:
            period: Period for calculation (default 14)
        """
        super().__init__(name=self.INDICATOR_NAME, parameters={})
        self.period = period
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate ADX.
        
        Args:
            data: DataFrame with 'high', 'low', 'close' columns
            
        Returns:
            DataFrame with ADX, +DI, -DI columns added
        """
        df = data.copy()
        
        # True Range
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        
        # Directional movements
        df['+dm'] = np.where(
            (df['high'] - df['high'].shift(1)) > (df['low'].shift(1) - df['low']),
            np.maximum(df['high'] - df['high'].shift(1), 0),
            0
        )
        df['-dm'] = np.where(
            (df['low'].shift(1) - df['low']) > (df['high'] - df['high'].shift(1)),
            np.maximum(df['low'].shift(1) - df['low'], 0),
            0
        )
        
        # Smoothed TR, +DM, -DM
        df['tr_smooth'] = df['tr'].rolling(window=self.period).mean()
        df['+dm_smooth'] = df['+dm'].rolling(window=self.period).mean()
        df['-dm_smooth'] = df['-dm'].rolling(window=self.period).mean()
        
        # Directional indices
        df['+di'] = 100 * (df['+dm_smooth'] / df['tr_smooth'])
        df['-di'] = 100 * (df['-dm_smooth'] / df['tr_smooth'])
        
        # ADX
        df['dx'] = 100 * (abs(df['+di'] - df['-di']) / (df['+di'] + df['-di']))
        df['adx'] = df['dx'].rolling(window=self.period).mean()
        
        self.last_calculated = df
        return df
    
    def is_trending(self, data: pd.DataFrame, threshold: float = 25) -> bool:
        """
        Check if market is trending.
        
        Args:
            data: DataFrame with ADX data
            threshold: ADX threshold for trend (default 25)
            
        Returns:
            True if trending
        """
        last_row = data.iloc[-1]
        return last_row['adx'] > threshold
    
    def get_trend_direction(self, data: pd.DataFrame) -> str:
        """
        Get trend direction.
        
        Args:
            data: DataFrame with ADX data
            
        Returns:
            'BULLISH' if +DI > -DI, 'BEARISH' otherwise
        """
        last_row = data.iloc[-1]
        if last_row['+di'] > last_row['-di']:
            return 'BULLISH'
        return 'BEARISH'
    def reset(self):
        """Reset indicator state."""
        self.last_calculated = None
