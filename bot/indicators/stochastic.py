"""Stochastic Oscillator indicator."""

import pandas as pd
import numpy as np
from typing import Optional

from bot.core.interfaces import Indicator


class Stochastic(Indicator):
    """Stochastic Oscillator for momentum and overbought/oversold conditions."""
    
    INDICATOR_NAME = "stochastic"
    
    def __init__(self, k_period: int = 14, d_period: int = 3):
        """
        Initialize Stochastic indicator.
        
        Args:
            k_period: Period for %K (default 14)
            d_period: Period for %D smoothing (default 3)
        """
        super().__init__(name=self.INDICATOR_NAME, parameters={})
        self.k_period = k_period
        self.d_period = d_period
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Stochastic Oscillator.
        
        Args:
            data: DataFrame with 'high', 'low', 'close' columns
            
        Returns:
            DataFrame with %K and %D columns added
        """
        df = data.copy()
        
        # Lowest low and highest high over k_period
        df['low_min'] = df['low'].rolling(window=self.k_period).min()
        df['high_max'] = df['high'].rolling(window=self.k_period).max()
        
        # %K
        df['stoch_k'] = 100 * (
            (df['close'] - df['low_min']) / (df['high_max'] - df['low_min'])
        )
        
        # %D (smoothed %K)
        df['stoch_d'] = df['stoch_k'].rolling(window=self.d_period).mean()
        
        self.last_calculated = df
        return df
    
    def is_overbought(self, data: pd.DataFrame, threshold: float = 80) -> bool:
        """Check if overbought."""
        last_row = data.iloc[-1]
        return last_row['stoch_k'] > threshold
    
    def is_oversold(self, data: pd.DataFrame, threshold: float = 20) -> bool:
        """Check if oversold."""
        last_row = data.iloc[-1]
        return last_row['stoch_k'] < threshold
    
    def has_crossover(self, data: pd.DataFrame) -> Optional[str]:
        """
        Check for %K/%D crossover.
        
        Args:
            data: DataFrame with Stochastic data
            
        Returns:
            'BULLISH' if %K crosses above %D, 'BEARISH' if below, None otherwise
        """
        if len(data) < 2:
            return None
        
        prev_row = data.iloc[-2]
        curr_row = data.iloc[-1]
        
        if prev_row['stoch_k'] <= prev_row['stoch_d'] and curr_row['stoch_k'] > curr_row['stoch_d']:
            return 'BULLISH'
        elif prev_row['stoch_k'] >= prev_row['stoch_d'] and curr_row['stoch_k'] < curr_row['stoch_d']:
            return 'BEARISH'
        
        return None
    def reset(self):
        """Reset indicator state."""
        self.last_calculated = None
