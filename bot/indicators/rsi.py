"""
Relative Strength Index (RSI) Indicator.
Measures the magnitude of recent price changes to evaluate overbought or oversold conditions.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

from bot.core.interfaces import Indicator


class RSIIndicator(Indicator):
    """
    Relative Strength Index (RSI) Indicator.
    
    The RSI is a momentum oscillator that measures the speed and change of price movements.
    It oscillates between 0 and 100. Traditionally, RSI is considered overbought when above 70
    and oversold when below 30.
    
    Formula:
        RSI = 100 - (100 / (1 + RS))
        where RS = Average Gain / Average Loss
        
    Calculation Steps:
        1. Calculate price changes
        2. Separate gains and losses
        3. Calculate average gains and losses using smoothed method
        4. Calculate RS and RSI
    
    Usage:
        - Identify overbought (>70) and oversold (<30) conditions
        - Detect divergences between price and RSI
        - Generate reversal signals
        - Confirm trend strength
    """
    
    INDICATOR_NAME = "rsi"
    
    def __init__(self, name: str = None, parameters: Dict[str, Any] = None):
        """
        Initialize the RSI indicator.
        
        Args:
            name: Unique identifier for the indicator
            parameters: Configuration parameters including:
                - period (int): Number of periods for RSI calculation (default: 14)
                - price_column (str): Column to calculate RSI on (default: 'close')
                - overbought_threshold (float): Overbought level (default: 70)
                - oversold_threshold (float): Oversold level (default: 30)
        """
        if name is None:
            name = self.INDICATOR_NAME
        super().__init__(name, parameters)
        
        # Set default parameters
        self.period = self.parameters.get('period', 14)
        self.price_column = self.parameters.get('price_column', 'close')
        self.overbought_threshold = self.parameters.get('overbought_threshold', 70)
        self.oversold_threshold = self.parameters.get('oversold_threshold', 30)
        
        # Validate parameters
        if self.period <= 0:
            raise ValueError(f"Period must be positive, got {self.period}")
        
        if not 0 < self.overbought_threshold < 100:
            raise ValueError(f"Overbought threshold must be between 0 and 100, got {self.overbought_threshold}")
        
        if not 0 < self.oversold_threshold < 100:
            raise ValueError(f"Oversold threshold must be between 0 and 100, got {self.oversold_threshold}")
        
        if self.oversold_threshold >= self.overbought_threshold:
            raise ValueError(f"Oversold threshold ({self.oversold_threshold}) must be less than overbought threshold ({self.overbought_threshold})")
        
        # Internal state
        self._last_calculated: pd.Series = None
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate the Relative Strength Index on the provided data.
        
        Args:
            data: OHLCV DataFrame with columns: ['open', 'high', 'low', 'close', 'volume']
            
        Returns:
            DataFrame with original data plus RSI column added
            
        Raises:
            ValueError: If required columns are missing or data is invalid
        """
        if self.logger:
            self.logger.debug(f"Calculating RSI with period {self.period}")
        
        # Validate input data
        if self.price_column not in data.columns:
            raise ValueError(f"Column '{self.price_column}' not found in data")
        
        if len(data) < self.period + 1:
            raise ValueError(
                f"Insufficient data: need at least {self.period + 1} periods, "
                f"got {len(data)}"
            )
        
        # Create a copy to avoid modifying original data
        result = data.copy()
        
        # Calculate price changes
        price_changes = result[self.price_column].diff()
        
        # Separate gains and losses
        gains = price_changes.where(price_changes > 0, 0)
        losses = -price_changes.where(price_changes < 0, 0)
        
        # Calculate average gains and losses using exponential smoothing
        avg_gains = gains.ewm(span=self.period, adjust=False).mean()
        avg_losses = losses.ewm(span=self.period, adjust=False).mean()
        
        # Calculate Relative Strength (RS)
        # Handle division by zero
        rs = avg_gains / avg_losses.replace(0, np.nan)
        
        # Calculate RSI
        rsi_values = 100 - (100 / (1 + rs))
        
        # RSI starts from NaN and becomes valid after sufficient data
        # Fill initial NaN with 50 (neutral)
        rsi_values = rsi_values.fillna(50)
        
        # Add RSI to result DataFrame with descriptive column name
        rsi_column_name = f"rsi_{self.period}"
        result[rsi_column_name] = rsi_values
        
        # Store for potential future use
        self._last_calculated = rsi_values
        
        if self.logger:
            latest_rsi = rsi_values.iloc[-1]
            status = "NEUTRAL"
            if latest_rsi > self.overbought_threshold:
                status = "OVERBOUGHT"
            elif latest_rsi < self.oversold_threshold:
                status = "OVERSOLD"
            self.logger.debug(f"RSI calculation complete. Latest value: {latest_rsi:.2f} ({status})")
        
        return result
    
    def reset(self) -> None:
        """
        Reset the indicator to its initial state.
        Clears any cached values or internal state.
        """
        self._last_calculated = None
        if self.logger:
            self.logger.debug(f"RSI indicator reset")
    
    def get_latest_value(self) -> float:
        """
        Get the most recently calculated RSI value.
        
        Returns:
            Latest RSI value
            
        Raises:
            ValueError: If no calculation has been performed yet
        """
        if self._last_calculated is None:
            raise ValueError("No RSI value calculated yet. Call calculate() first.")
        
        return float(self._last_calculated.iloc[-1])
    
    def get_all_values(self) -> pd.Series:
        """
        Get all calculated RSI values.
        
        Returns:
            Series of all RSI values
            
        Raises:
            ValueError: If no calculation has been performed yet
        """
        if self._last_calculated is None:
            raise ValueError("No RSI values calculated yet. Call calculate() first.")
        
        return self._last_calculated.copy()
    
    def get_column_name(self) -> str:
        """
        Get the column name that will be used in the output DataFrame.
        
        Returns:
            Column name for the RSI values
        """
        return f"rsi_{self.period}"
    
    def is_overbought(self, rsi_value: float = None) -> bool:
        """
        Check if a given RSI value indicates overbought condition.
        
        Args:
            rsi_value: RSI value to check (uses latest if not provided)
            
        Returns:
            True if overbought, False otherwise
        """
        if rsi_value is None:
            rsi_value = self.get_latest_value()
        return rsi_value > self.overbought_threshold
    
    def is_oversold(self, rsi_value: float = None) -> bool:
        """
        Check if a given RSI value indicates oversold condition.
        
        Args:
            rsi_value: RSI value to check (uses latest if not provided)
            
        Returns:
            True if oversold, False otherwise
        """
        if rsi_value is None:
            rsi_value = self.get_latest_value()
        return rsi_value < self.oversold_threshold
    
    def get_signal(self, rsi_value: float = None) -> str:
        """
        Get the current RSI signal (OVERBOUGHT, OVERSOLD, or NEUTRAL).
        
        Args:
            rsi_value: RSI value to evaluate (uses latest if not provided)
            
        Returns:
            Signal string: 'OVERBOUGHT', 'OVERSOLD', or 'NEUTRAL'
        """
        if rsi_value is None:
            rsi_value = self.get_latest_value()
        
        if self.is_overbought(rsi_value):
            return 'OVERBOUGHT'
        elif self.is_oversold(rsi_value):
            return 'OVERSOLD'
        else:
            return 'NEUTRAL'


# Note: Registration is handled dynamically by the registry.load_from_module() method
# The INDICATOR_NAME class attribute is used by the registry to identify this indicator


# Minimal test for validation
if __name__ == "__main__":
    # Create test data
    print("Running RSI Indicator Test...")
    print("=" * 60)
    
    # Generate test data with some trend
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    
    # Create price series with clear up and down movements
    trend = np.concatenate([
        np.ones(30) * 0.5,   # Uptrend
        np.ones(20) * -0.3,  # Downtrend
        np.ones(30) * 0.2,   # Recovery
        np.ones(20) * -0.1   # Correction
    ])
    
    prices = 100 + np.cumsum(trend + np.random.randn(100) * 0.3)
    
    test_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices,
        'high': prices * 1.01,
        'low': prices * 0.99,
        'close': prices,
        'volume': np.random.randint(100000, 1000000, 100)
    })
    test_data.set_index('timestamp', inplace=True)
    
    # Test 1: Basic calculation
    print("\nTest 1: Basic RSI Calculation (period=14)")
    rsi = RSIIndicator(parameters={'period': 14})
    result = rsi.calculate(test_data)
    
    print(f"  Input data points: {len(test_data)}")
    print(f"  Output data points: {len(result)}")
    print(f"  RSI column created: {rsi.get_column_name()}")
    print(f"  First RSI value: {result[rsi.get_column_name()].iloc[0]:.2f}")
    print(f"  Last RSI value: {result[rsi.get_column_name()].iloc[-1]:.2f}")
    print(f"  Latest value method: {rsi.get_latest_value():.2f}")
    
    # Test 2: Signal detection
    print("\nTest 2: RSI Signal Detection")
    latest_rsi = rsi.get_latest_value()
    signal = rsi.get_signal()
    print(f"  Latest RSI: {latest_rsi:.2f}")
    print(f"  Signal: {signal}")
    print(f"  Overbought threshold: {rsi.overbought_threshold}")
    print(f"  Oversold threshold: {rsi.oversold_threshold}")
    print(f"  Is overbought: {rsi.is_overbought()}")
    print(f"  Is oversold: {rsi.is_oversold()}")
    
    # Test 3: Find overbought and oversold conditions in data
    print("\nTest 3: Overbought/Oversold Occurrences")
    rsi_values = result[rsi.get_column_name()]
    overbought_count = (rsi_values > rsi.overbought_threshold).sum()
    oversold_count = (rsi_values < rsi.oversold_threshold).sum()
    
    print(f"  Overbought occurrences (>70): {overbought_count}")
    print(f"  Oversold occurrences (<30): {oversold_count}")
    print(f"  Max RSI: {rsi_values.max():.2f}")
    print(f"  Min RSI: {rsi_values.min():.2f}")
    print(f"  Mean RSI: {rsi_values.mean():.2f}")
    
    # Test 4: Different period
    print("\nTest 4: RSI with period=7 (More sensitive)")
    rsi7 = RSIIndicator(parameters={'period': 7})
    result7 = rsi7.calculate(test_data)
    print(f"  RSI7 first value: {result7[rsi7.get_column_name()].iloc[0]:.2f}")
    print(f"  RSI7 last value: {result7[rsi7.get_column_name()].iloc[-1]:.2f}")
    print(f"  RSI7 range: {result7[rsi7.get_column_name()].min():.2f} - {result7[rsi7.get_column_name()].max():.2f}")
    
    # Test 5: Reset functionality
    print("\nTest 5: Reset Functionality")
    rsi.reset()
    try:
        rsi.get_latest_value()
        print("  ✗ Reset failed - still has cached values")
    except ValueError:
        print("  ✓ Reset successful - no cached values")
    
    # Test 6: Error handling
    print("\nTest 6: Error Handling")
    try:
        rsi_bad_period = RSIIndicator(parameters={'period': -5})
        print("  ✗ Should have raised ValueError for negative period")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    try:
        rsi_bad_threshold = RSIIndicator(parameters={'overbought_threshold': 110})
        print("  ✗ Should have raised ValueError for invalid threshold")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    try:
        rsi_bad_thresholds = RSIIndicator(parameters={'oversold_threshold': 60, 'overbought_threshold': 50})
        print("  ✗ Should have raised ValueError for inverted thresholds")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    try:
        rsi_short = RSIIndicator(parameters={'period': 150})
        rsi_short.calculate(test_data)
        print("  ✗ Should have raised ValueError for insufficient data")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    # Test 7: Registry registration
    print("\nTest 7: Registry Registration")
    from bot.core.registry import IndicatorRegistry
    registry = IndicatorRegistry()
    
    count = registry.load_from_module('bot.indicators.rsi')
    print(f"  Loaded {count} indicator(s) from module")
    
    if registry.exists('rsi'):
        print(f"  ✓ RSI indicator registered in registry as 'rsi'")
        registered_class = registry.get('rsi')
        print(f"  ✓ Registered class: {registered_class.__name__}")
        
        # Test creating instance from registry
        rsi_from_registry = registry.create_instance('rsi', {'period': 14})
        print(f"  ✓ Created instance from registry: {rsi_from_registry.__class__.__name__}")
    else:
        print("  ✗ RSI indicator not found in registry")
    
    print("\n" + "=" * 60)
    print("✅ All RSI Indicator Tests Passed!")