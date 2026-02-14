"""OBV (On Balance Volume) indicator."""

import pandas as pd
import numpy as np
from typing import Optional

from bot.core.interfaces import Indicator


class OBV(Indicator):
    """On Balance Volume for measuring buying/selling pressure."""
    
    INDICATOR_NAME = "obv"
    
    def __init__(self):
        """Initialize OBV indicator."""
        super().__init__(name=self.INDICATOR_NAME, parameters={})
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate OBV.
        
        Args:
            data: DataFrame with 'close' and 'volume' columns
            
        Returns:
            DataFrame with OBV column added
        """
        df = data.copy()
        
        # Price direction
        df['price_change'] = df['close'].diff()
        
        # OBV calculation
        obv = [0]
        for i in range(1, len(df)):
            if df['price_change'].iloc[i] > 0:
                obv.append(obv[-1] + df['volume'].iloc[i])
            elif df['price_change'].iloc[i] < 0:
                obv.append(obv[-1] - df['volume'].iloc[i])
            else:
                obv.append(obv[-1])
        
        df['obv'] = obv
        self.last_calculated = df
        return df
    
    def get_bullish_divergence(self, data: pd.DataFrame, lookback: int = 5) -> bool:
        """
        Check for bullish divergence (price makes lower low, OBV makes higher low).
        
        Args:
            data: DataFrame with OBV data
            lookback: Number of periods to look back
            
        Returns:
            True if bullish divergence detected
        """
        if len(data) < lookback + 1:
            return False
        
        recent = data.tail(lookback + 1)
        price_low_idx = recent['close'].idxmin()
        obv_low_idx = recent['obv'].idxmin()
        
        # Price made lower low, OBV made higher low
        return price_low_idx == recent.index[-1] and obv_low_idx != recent.index[-1]
    
    def get_bearish_divergence(self, data: pd.DataFrame, lookback: int = 5) -> bool:
        """
        Check for bearish divergence (price makes higher high, OBV makes lower high).
        
        Args:
            data: DataFrame with OBV data
            lookback: Number of periods to look back
            
        Returns:
            True if bearish divergence detected
        """
        if len(data) < lookback + 1:
            return False
        
        recent = data.tail(lookback + 1)
        price_high_idx = recent['close'].idxmax()
        obv_high_idx = recent['obv'].idxmax()
        
        # Price made higher high, OBV made lower high
        return price_high_idx == recent.index[-1] and obv_high_idx != recent.index[-1]
    def reset(self):
        """Reset indicator state."""
        self.last_calculated = None
