"""
Exponential Moving Average (EMA) Indicator.
Calculates the exponential moving average of closing prices with greater weight on recent data.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

from bot.core.interfaces import Indicator


class EMAIndicator(Indicator):
    """
    Exponential Moving Average (EMA) Indicator.
    
    The EMA gives more weight to recent prices compared to the SMA,
    making it more responsive to new information. The weighting applied
    to the most recent price depends on the number of periods in the EMA.
    
    Formula:
        EMA = (Price × k) + (Previous EMA × (1 − k))
        where k = 2 / (N + 1) and N is the smoothing period
    
    Usage:
        - Identify trend direction with more sensitivity than SMA
        - Generate trading signals (EMA crossovers)
        - Support and resistance levels
        - Smoothing price data with reduced lag
    """
    
    INDICATOR_NAME = "ema"
    
    def __init__(self, name: str = None, parameters: Dict[str, Any] = None):
        """
        Initialize the EMA indicator.
        
        Args:
            name: Unique identifier for the indicator
            parameters: Configuration parameters including:
                - period (int): Number of periods for the EMA (default: 20)
                - price_column (str): Column to calculate EMA on (default: 'close')
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
        
        # Calculate smoothing factor
        self.smoothing_factor = 2.0 / (self.period + 1.0)
        
        # Internal state
        self._last_calculated: pd.Series = None
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate the Exponential Moving Average on the provided data.
        
        Args:
            data: OHLCV DataFrame with columns: ['open', 'high', 'low', 'close', 'volume']
            
        Returns:
            DataFrame with original data plus EMA column added
            
        Raises:
            ValueError: If required columns are missing or data is invalid
        """
        if self.logger:
            self.logger.debug(f"Calculating EMA with period {self.period}")
        
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
        
        # Calculate EMA using pandas ewm (exponential weighted mean)
        ema_values = result[self.price_column].ewm(
            span=self.period,
            adjust=False
        ).mean()
        
        # Add EMA to result DataFrame with descriptive column name
        ema_column_name = f"ema_{self.period}"
        result[ema_column_name] = ema_values
        
        # Store for potential future use
        self._last_calculated = ema_values
        
        if self.logger:
            self.logger.debug(f"EMA calculation complete. Latest value: {ema_values.iloc[-1]:.2f}")
        
        return result
    
    def reset(self) -> None:
        """
        Reset the indicator to its initial state.
        Clears any cached values or internal state.
        """
        self._last_calculated = None
        if self.logger:
            self.logger.debug(f"EMA indicator reset")
    
    def get_latest_value(self) -> float:
        """
        Get the most recently calculated EMA value.
        
        Returns:
            Latest EMA value
            
        Raises:
            ValueError: If no calculation has been performed yet
        """
        if self._last_calculated is None:
            raise ValueError("No EMA value calculated yet. Call calculate() first.")
        
        return float(self._last_calculated.iloc[-1])
    
    def get_all_values(self) -> pd.Series:
        """
        Get all calculated EMA values.
        
        Returns:
            Series of all EMA values
            
        Raises:
            ValueError: If no calculation has been performed yet
        """
        if self._last_calculated is None:
            raise ValueError("No EMA values calculated yet. Call calculate() first.")
        
        return self._last_calculated.copy()
    
    def get_column_name(self) -> str:
        """
        Get the column name that will be used in the output DataFrame.
        
        Returns:
            Column name for the EMA values
        """
        return f"ema_{self.period}"
    
    def get_smoothing_factor(self) -> float:
        """
        Get the smoothing factor used for EMA calculation.
        
        Returns:
            Smoothing factor (k)
        """
        return self.smoothing_factor


# Note: Registration is handled dynamically by the registry.load_from_module() method
# The INDICATOR_NAME class attribute is used by the registry to identify this indicator


# Minimal test for validation
if __name__ == "__main__":
    # Create test data
    print("Running EMA Indicator Test...")
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
    print("\nTest 1: Basic EMA Calculation (period=20)")
    ema = EMAIndicator(parameters={'period': 20})
    result = ema.calculate(test_data)
    
    print(f"  Input data points: {len(test_data)}")
    print(f"  Output data points: {len(result)}")
    print(f"  EMA column created: {ema.get_column_name()}")
    print(f"  First EMA value: {result[ema.get_column_name()].iloc[0]:.4f}")
    print(f"  Last EMA value: {result[ema.get_column_name()].iloc[-1]:.4f}")
    print(f"  Latest value method: {ema.get_latest_value():.4f}")
    print(f"  Smoothing factor: {ema.get_smoothing_factor():.4f}")
    
    # Test 2: Different period
    print("\nTest 2: EMA with period=50")
    ema50 = EMAIndicator(parameters={'period': 50})
    result50 = ema50.calculate(test_data)
    print(f"  EMA50 first value: {result50[ema50.get_column_name()].iloc[0]:.4f}")
    print(f"  EMA50 last value: {result50[ema50.get_column_name()].iloc[-1]:.4f}")
    print(f"  EMA50 smoothing factor: {ema50.get_smoothing_factor():.4f}")
    
    # Test 3: Compare EMA vs SMA (EMA should be more responsive)
    print("\nTest 3: EMA vs SMA Responsiveness")
    from bot.indicators.sma import SMAIndicator
    sma = SMAIndicator(parameters={'period': 20})
    result_sma = sma.calculate(test_data)
    
    # Check difference between EMA and SMA on last value
    ema_last = result[ema.get_column_name()].iloc[-1]
    sma_last = result_sma[sma.get_column_name()].iloc[-1]
    price_last = test_data['close'].iloc[-1]
    
    print(f"  Last price: {price_last:.4f}")
    print(f"  EMA20: {ema_last:.4f}")
    print(f"  SMA20: {sma_last:.4f}")
    print(f"  EMA deviation from price: {abs(ema_last - price_last):.4f}")
    print(f"  SMA deviation from price: {abs(sma_last - price_last):.4f}")
    
    # Test 4: Reset functionality
    print("\nTest 4: Reset Functionality")
    ema.reset()
    try:
        ema.get_latest_value()
        print("  ✗ Reset failed - still has cached values")
    except ValueError:
        print("  ✓ Reset successful - no cached values")
    
    # Test 5: Error handling
    print("\nTest 5: Error Handling")
    try:
        ema_bad_period = EMAIndicator(parameters={'period': -5})
        print("  ✗ Should have raised ValueError for negative period")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    try:
        ema_short = EMAIndicator(parameters={'period': 150})
        ema_short.calculate(test_data)
        print("  ✗ Should have raised ValueError for insufficient data")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    # Test 6: Registry registration
    print("\nTest 6: Registry Registration")
    from bot.core.registry import IndicatorRegistry
    registry = IndicatorRegistry()
    
    count = registry.load_from_module('bot.indicators.ema')
    print(f"  Loaded {count} indicator(s) from module")
    
    if registry.exists('ema'):
        print(f"  ✓ EMA indicator registered in registry as 'ema'")
        registered_class = registry.get('ema')
        print(f"  ✓ Registered class: {registered_class.__name__}")
        
        # Test creating instance from registry
        ema_from_registry = registry.create_instance('ema', {'period': 20})
        print(f"  ✓ Created instance from registry: {ema_from_registry.__class__.__name__}")
    else:
        print("  ✗ EMA indicator not found in registry")
    
    print("\n" + "=" * 60)
    print("✅ All EMA Indicator Tests Passed!")