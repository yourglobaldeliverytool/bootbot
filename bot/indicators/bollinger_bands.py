"""Bollinger Bands indicator."""

import pandas as pd
import numpy as np
from typing import Optional

from bot.core.interfaces import Indicator


class BollingerBands(Indicator):
    """Bollinger Bands indicator for volatility and mean reversion."""
    
    INDICATOR_NAME = "bollinger_bands"
    
    def __init__(self, period: int = 20, std_dev: float = 2.0):
        """
        Initialize Bollinger Bands indicator.
        
        Args:
            period: Period for the moving average (default 20)
            std_dev: Number of standard deviations for bands (default 2.0)
        """
        super().__init__(name=self.INDICATOR_NAME, parameters={})
        self.period = period
        self.std_dev = std_dev
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Bollinger Bands.
        
        Args:
            data: DataFrame with 'close' column
            
        Returns:
            DataFrame with BB columns added
        """
        df = data.copy()
        
        # Middle band (SMA)
        df[f'bb_middle_{self.period}'] = df['close'].rolling(window=self.period).mean()
        
        # Standard deviation
        std = df['close'].rolling(window=self.period).std()
        
        # Upper and lower bands
        df[f'bb_upper_{self.period}'] = df[f'bb_middle_{self.period}'] + (std * self.std_dev)
        df[f'bb_lower_{self.period}'] = df[f'bb_middle_{self.period}'] - (std * self.std_dev)
        
        # Bandwidth (measure of volatility)
        df[f'bb_bandwidth_{self.period}'] = (
            (df[f'bb_upper_{self.period}'] - df[f'bb_lower_{self.period}']) / 
            df[f'bb_middle_{self.period}']
        )
        
        # %B (position within bands)
        df[f'bb_percent_b_{self.period}'] = (
            (df['close'] - df[f'bb_lower_{self.period}']) / 
            (df[f'bb_upper_{self.period}'] - df[f'bb_lower_{self.period}'])
        )
        
        self.last_calculated = df
        return df
    
    def is_squeeze(self, data: pd.DataFrame, threshold: float = 0.02) -> bool:
        """
        Check if bands are squeezing (low volatility).
        
        Args:
            data: DataFrame with BB data
            threshold: Bandwidth threshold for squeeze
            
        Returns:
            True if squeezing
        """
        last_row = data.iloc[-1]
        bandwidth_col = f'bb_bandwidth_{self.period}'
        if bandwidth_col in last_row:
            return last_row[bandwidth_col] < threshold
        return False
    
    def get_signal(self, data: pd.DataFrame) -> str:
        """
        Get trading signal based on BB position.
        
        Args:
            data: DataFrame with BB data
            
        Returns:
            'BUY' if price near lower band, 'SELL' if near upper band, 'HOLD' otherwise
        """
        last_row = data.iloc[-1]
        percent_b_col = f'bb_percent_b_{self.period}'
        
        if percent_b_col in last_row:
            percent_b = last_row[percent_b_col]
            if percent_b < 0.1:  # Near lower band
                return 'BUY'
            elif percent_b > 0.9:  # Near upper band
                return 'SELL'
        
        return 'HOLD'
    def reset(self):
        """Reset indicator state."""
        self.last_calculated = None
