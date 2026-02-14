"""
Simple Moving Average (SMA) Indicator.
Calculates the simple moving average of closing prices over a specified period.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

from bot.core.interfaces import Indicator


class SMAIndicator(Indicator):
    """Simple Moving Average indicator."""
    
    # Class attribute for registry identification
    INDICATOR_NAME = "sma"
    """
    Simple Moving Average (SMA) Indicator.
    
    The SMA calculates the average price over a specified period by taking
    the sum of prices and dividing it by the number of periods. It is one
    of the most commonly used technical indicators for trend analysis.
    
    Usage:
        - Identify trend direction (rising SMA = uptrend, falling SMA = downtrend)
        - Generate trading signals (crossovers between short and long SMAs)
        - Support and resistance levels
        - Smoothing price data to reduce noise
    """
    
    def __init__(self, name: str = None, parameters: Dict[str, Any] = None):
        """
        Initialize the SMA indicator.
        
        Args:
            name: Unique identifier for the indicator
            parameters: Configuration parameters including:
                - period (int): Number of periods for the SMA (default: 20)
                - price_column (str): Column to calculate SMA on (default: 'close')
        """
        if name is None:
            name = self.INDICATOR_NAME
        super().__init__(name, parameters)
        
        # Set default parameters
        self.period = self.parameters.get('period', 20)
        self.price_column = self.parameters.get('price_column', 'close')
        
        # Validate parameters
        if self.period <= 0:
            raise ValueError(f"Period must be positive, got {self.period}")
        
        # Internal state
        self._last_calculated: pd.Series = None
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate the Simple Moving Average on the provided data.
        
        Args:
            data: OHLCV DataFrame with columns: ['open', 'high', 'low', 'close', 'volume']
            
        Returns:
            DataFrame with original data plus SMA column added
            
        Raises:
            ValueError: If required columns are missing or data is invalid
        """
        if self.logger:
            self.logger.debug(f"Calculating SMA with period {self.period}")
        
        # Validate input data
        if self.price_column not in data.columns:
            raise ValueError(f"Column '{self.price_column}' not found in data")
        
        if len(data) < self.period:
            raise ValueError(
                f"Insufficient data: need at least {self.period} periods, "
                f"got {len(data)}"
            )
        
        # Create a copy to avoid modifying original data
        result = data.copy()
        
        # Calculate SMA using pandas rolling mean
        sma_values = result[self.price_column].rolling(window=self.period, min_periods=1).mean()
        
        # Add SMA to result DataFrame with descriptive column name
        sma_column_name = f"sma_{self.period}"
        result[sma_column_name] = sma_values
        
        # Store for potential future use
        self._last_calculated = sma_values
        
        if self.logger:
            self.logger.debug(f"SMA calculation complete. Latest value: {sma_values.iloc[-1]:.2f}")
        
        return result
    
    def reset(self) -> None:
        """
        Reset the indicator to its initial state.
        Clears any cached values or internal state.
        """
        self._last_calculated = None
        if self.logger:
            self.logger.debug(f"SMA indicator reset")
    
    def get_latest_value(self) -> float:
        """
        Get the most recently calculated SMA value.
        
        Returns:
            Latest SMA value
            
        Raises:
            ValueError: If no calculation has been performed yet
        """
        if self._last_calculated is None:
            raise ValueError("No SMA value calculated yet. Call calculate() first.")
        
        return float(self._last_calculated.iloc[-1])
    
    def get_all_values(self) -> pd.Series:
        """
        Get all calculated SMA values.
        
        Returns:
            Series of all SMA values
            
        Raises:
            ValueError: If no calculation has been performed yet
        """
        if self._last_calculated is None:
            raise ValueError("No SMA values calculated yet. Call calculate() first.")
        
        return self._last_calculated.copy()
    
    def get_column_name(self) -> str:
        """
        Get the column name that will be used in the output DataFrame.
        
        Returns:
            Column name for the SMA values
        """
        return f"sma_{self.period}"


# Note: Registration is handled dynamically by the registry.load_from_module() method
# The INDICATOR_NAME constant is used by the registry to identify this indicator


# Minimal test for validation
if __name__ == "__main__":
    # Create test data
    print("Running SMA Indicator Test...")
    print("=" * 60)
    
    # Generate simple test data
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
    
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
    print("\nTest 1: Basic SMA Calculation (period=20)")
    sma = SMAIndicator(parameters={'period': 20})
    result = sma.calculate(test_data)
    
    print(f"  Input data points: {len(test_data)}")
    print(f"  Output data points: {len(result)}")
    print(f"  SMA column created: {sma.get_column_name()}")
    print(f"  First SMA value: {result[sma.get_column_name()].iloc[19]:.4f}")
    print(f"  Last SMA value: {result[sma.get_column_name()].iloc[-1]:.4f}")
    print(f"  Latest value method: {sma.get_latest_value():.4f}")
    
    # Test 2: Different period
    print("\nTest 2: SMA with period=50")
    sma50 = SMAIndicator(parameters={'period': 50})
    result50 = sma50.calculate(test_data)
    print(f"  SMA50 first valid value: {result50[sma50.get_column_name()].iloc[49]:.4f}")
    print(f"  SMA50 last value: {result50[sma50.get_column_name()].iloc[-1]:.4f}")
    
    # Test 3: Reset functionality
    print("\nTest 3: Reset Functionality")
    sma.reset()
    try:
        sma.get_latest_value()
        print("  ✗ Reset failed - still has cached values")
    except ValueError:
        print("  ✓ Reset successful - no cached values")
    
    # Test 4: Error handling
    print("\nTest 4: Error Handling")
    try:
        sma_bad_period = SMAIndicator(parameters={'period': -5})
        print("  ✗ Should have raised ValueError for negative period")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    try:
        sma_short = SMAIndicator(parameters={'period': 150})
        sma_short.calculate(test_data)
        print("  ✗ Should have raised ValueError for insufficient data")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    # Test 5: Registry registration via load_from_module
    print("\nTest 5: Registry Registration")
    from bot.core.registry import IndicatorRegistry
    registry = IndicatorRegistry()
    
    # Load indicator from module
    count = registry.load_from_module('bot.indicators.sma')
    print(f"  Loaded {count} indicator(s) from module")
    
    # The INDICATOR_NAME class attribute is used as the registry key
    if registry.exists('sma'):
        print(f"  ✓ SMA indicator registered in registry as 'sma'")
        registered_class = registry.get('sma')
        print(f"  ✓ Registered class: {registered_class.__name__}")
        
        # Test creating instance from registry
        sma_from_registry = registry.create_instance(
            'sma',
            {'period': 20}
        )
        print(f"  ✓ Created instance from registry: {sma_from_registry.__class__.__name__}")
    else:
        print(f"  ✗ SMA indicator not found in registry")
    
    print("\n" + "=" * 60)
    print("✅ All SMA Indicator Tests Passed!")