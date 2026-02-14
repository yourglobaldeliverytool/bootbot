"""Parabolic SAR indicator."""

import pandas as pd
import numpy as np
from typing import Optional

from bot.core.interfaces import Indicator


class ParabolicSAR(Indicator):
    """Parabolic SAR for trend following and stop loss."""
    
    INDICATOR_NAME = "parabolic_sar"
    
    def __init__(self, step: float = 0.02, max_step: float = 0.2):
        """
        Initialize Parabolic SAR indicator.
        
        Args:
            step: Initial AF step (default 0.02)
            max_step: Maximum AF step (default 0.2)
        """
        super().__init__(name=self.INDICATOR_NAME, parameters={})
        self.step = step
        self.max_step = max_step
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Parabolic SAR.
        
        Args:
            data: DataFrame with 'high', 'low', 'close' columns
            
        Returns:
            DataFrame with Parabolic SAR column added
        """
        df = data.copy()
        
        # Initialize SAR calculation
        length = len(df)
        sar = np.zeros(length)
        ep = np.zeros(length)
        af = np.zeros(length)
        direction = np.zeros(length)
        
        # Start with first uptrend
        sar[0] = df['low'].iloc[0]
        ep[0] = df['high'].iloc[0]
        af[0] = self.step
        direction[0] = 1  # 1 = uptrend, -1 = downtrend
        
        for i in range(1, length):
            # Update SAR
            sar[i] = sar[i-1] + af[i-1] * (ep[i-1] - sar[i-1])
            
            # Check for trend reversal
            if direction[i-1] == 1:  # Uptrend
                if df['low'].iloc[i] <= sar[i]:
                    # Reversal to downtrend
                    direction[i] = -1
                    sar[i] = ep[i-1]
                    ep[i] = df['low'].iloc[i]
                    af[i] = self.step
                else:
                    direction[i] = 1
                    ep[i] = max(ep[i-1], df['high'].iloc[i])
                    af[i] = min(self.max_step, af[i-1] + self.step)
                    sar[i] = max(sar[i], df['low'].iloc[i-1], df['low'].iloc[i-2])
            else:  # Downtrend
                if df['high'].iloc[i] >= sar[i]:
                    # Reversal to uptrend
                    direction[i] = 1
                    sar[i] = ep[i-1]
                    ep[i] = df['high'].iloc[i]
                    af[i] = self.step
                else:
                    direction[i] = -1
                    ep[i] = min(ep[i-1], df['low'].iloc[i])
                    af[i] = min(self.max_step, af[i-1] + self.step)
                    sar[i] = min(sar[i], df['high'].iloc[i-1], df['high'].iloc[i-2])
        
        df['parabolic_sar'] = sar
        df['parabolic_sar_direction'] = direction
        
        self.last_calculated = df
        return df
    
    def get_signal(self, data: pd.DataFrame) -> Optional[str]:
        """
        Get Parabolic SAR signal.
        
        Args:
            data: DataFrame with Parabolic SAR data
            
        Returns:
            'BUY' if price above SAR (uptrend), 'SELL' if below (downtrend), None otherwise
        """
        if len(data) < 1:
            return None
        
        last_row = data.iloc[-1]
        if pd.isna(last_row['parabolic_sar']):
            return None
        
        if last_row['parabolic_sar_direction'] == 1:
            return 'BUY'
        else:
            return 'SELL'
    def reset(self):
        """Reset indicator state."""
        self.last_calculated = None
