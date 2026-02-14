"""Ichimoku Cloud indicator."""

import pandas as pd
import numpy as np
from typing import Optional

from bot.core.interfaces import Indicator


class IchimokuCloud(Indicator):
    """Ichimoku Cloud for trend identification and support/resistance."""
    
    INDICATOR_NAME = "ichimoku"
    
    def __init__(self, tenkan_period: int = 9, kijun_period: int = 26, 
                 senkou_period: int = 52):
        """
        Initialize Ichimoku Cloud indicator.
        
        Args:
            tenkan_period: Tenkan-sen (conversion line) period (default 9)
            kijun_period: Kijun-sen (base line) period (default 26)
            senkou_period: Senkou Span B period (default 52)
        """
        super().__init__(name=self.INDICATOR_NAME, parameters={})
        self.tenkan_period = tenkan_period
        self.kijun_period = kijun_period
        self.senkou_period = senkou_period
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Ichimoku Cloud components.
        
        Args:
            data: DataFrame with 'high', 'low', 'close' columns
            
        Returns:
            DataFrame with Ichimoku columns added
        """
        df = data.copy()
        
        # Tenkan-sen (Conversion Line)
        df['ichimoku_tenkan'] = (
            df['high'].rolling(window=self.tenkan_period).max() +
            df['low'].rolling(window=self.tenkan_period).min()
        ) / 2
        
        # Kijun-sen (Base Line)
        df['ichimoku_kijun'] = (
            df['high'].rolling(window=self.kijun_period).max() +
            df['low'].rolling(window=self.kijun_period).min()
        ) / 2
        
        # Senkou Span A (Leading Span A)
        df['ichimoku_senkou_a'] = (
            df['ichimoku_tenkan'] + df['ichimoku_kijun']
        ) / 2
        
        # Senkou Span B (Leading Span B)
        df['ichimoku_senkou_b'] = (
            df['high'].rolling(window=self.senkou_period).max() +
            df['low'].rolling(window=self.senkou_period).min()
        ) / 2
        
        # Shift spans forward
        df['ichimoku_senkou_a'] = df['ichimoku_senkou_a'].shift(self.kijun_period)
        df['ichimoku_senkou_b'] = df['ichimoku_senkou_b'].shift(self.kijun_period)
        
        # Chikou Span (Lagging Span) - shifted back
        df['ichimoku_chikou'] = df['close'].shift(-self.kijun_period)
        
        self.last_calculated = df
        return df
    
    def get_cloud_bias(self, data: pd.DataFrame) -> str:
        """
        Get cloud bias direction.
        
        Args:
            data: DataFrame with Ichimoku data
            
        Returns:
            'BULLISH' if price above cloud, 'BEARISH' if below, 'NEUTRAL' if in cloud
        """
        last_row = data.iloc[-1]
        
        if pd.isna(last_row['ichimoku_senkou_a']) or pd.isna(last_row['ichimoku_senkou_b']):
            return 'NEUTRAL'
        
        cloud_top = max(last_row['ichimoku_senkou_a'], last_row['ichimoku_senkou_b'])
        cloud_bottom = min(last_row['ichimoku_senkou_a'], last_row['ichimoku_senkou_b'])
        
        if last_row['close'] > cloud_top:
            return 'BULLISH'
        elif last_row['close'] < cloud_bottom:
            return 'BEARISH'
        
        return 'NEUTRAL'
    
    def get_tk_cross(self, data: pd.DataFrame) -> Optional[str]:
        """
        Get Tenkan/Kijun crossover signal.
        
        Args:
            data: DataFrame with Ichimoku data
            
        Returns:
            'BULLISH' if Tenkan crosses above Kijun, 'BEARISH' if below, None otherwise
        """
        if len(data) < 2:
            return None
        
        prev_row = data.iloc[-2]
        curr_row = data.iloc[-1]
        
        if (prev_row['ichimoku_tenkan'] <= prev_row['ichimoku_kijun'] and 
            curr_row['ichimoku_tenkan'] > curr_row['ichimoku_kijun']):
            return 'BULLISH'
        elif (prev_row['ichimoku_tenkan'] >= prev_row['ichimoku_kijun'] and 
              curr_row['ichimoku_tenkan'] < curr_row['ichimoku_kijun']):
            return 'BEARISH'
        
        return None
    def reset(self):
        """Reset indicator state."""
        self.last_calculated = None
