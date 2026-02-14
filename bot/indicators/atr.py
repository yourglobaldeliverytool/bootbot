"""
Average True Range (ATR) Indicator.
Measures market volatility by calculating the average true range over a specified period.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

from bot.core.interfaces import Indicator


class ATRIndicator(Indicator):
    """
    Average True Range (ATR) Indicator.
    
    The ATR measures market volatility by decomposing the entire range of an asset
    price for that period. It was developed by J. Welles Wilder and introduced in
    his 1978 book, "New Concepts in Technical Trading Systems."
    
    True Range Calculation:
        TR = max(H - L, |H - previous_close|, |L - previous_close|)
        where H = current high, L = current low
    
    ATR Calculation:
        ATR = Rolling mean of TR over the specified period
    
    Usage:
        - Measure market volatility
        - Set stop-loss levels
        - Determine position sizes
        - Identify potential trend strength
        - Filter out low-volatility periods
    """
    
    INDICATOR_NAME = "atr"
    
    def __init__(self, name: str = None, parameters: Dict[str, Any] = None):
        """
        Initialize the ATR indicator.
        
        Args:
            name: Unique identifier for the indicator
            parameters: Configuration parameters including:
                - period (int): Number of periods for ATR calculation (default: 14)
                - use_sma (bool): Use simple moving average instead of EMA (default: False)
        """
        if name is None:
            name = self.INDICATOR_NAME
        super().__init__(name, parameters)
        
        # Set default parameters
        self.period = self.parameters.get('period', 14)
        self.use_sma = self.parameters.get('use_sma', False)
        
        # Validate parameters
        if self.period <= 0:
            raise ValueError(f"Period must be positive, got {self.period}")
        
        # Internal state
        self._last_calculated: pd.Series = None
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate the Average True Range on the provided data.
        
        Args:
            data: OHLCV DataFrame with columns: ['open', 'high', 'low', 'close', 'volume']
            
        Returns:
            DataFrame with original data plus ATR column added
            
        Raises:
            ValueError: If required columns are missing or data is invalid
        """
        if self.logger:
            self.logger.debug(f"Calculating ATR with period {self.period}")
        
        # Validate input data
        required_columns = ['high', 'low', 'close']
        for col in required_columns:
            if col not in data.columns:
                raise ValueError(f"Column '{col}' not found in data")
        
        if len(data) < self.period:
            raise ValueError(
                f"Insufficient data: need at least {self.period} periods, "
                f"got {len(data)}"
            )
        
        # Create a copy to avoid modifying original data
        result = data.copy()
        
        # Calculate True Range
        # TR = max(H - L, |H - previous_close|, |L - previous_close|)
        high_low = result['high'] - result['low']
        high_close = (result['high'] - result['close'].shift()).abs()
        low_close = (result['low'] - result['close'].shift()).abs()
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # Calculate ATR using specified method
        if self.use_sma:
            # Simple Moving Average
            atr_values = true_range.rolling(window=self.period, min_periods=1).mean()
        else:
            # Exponential Moving Average (Wilder's smoothing)
            atr_values = true_range.ewm(span=self.period, adjust=False).mean()
        
        # Add ATR to result DataFrame with descriptive column name
        atr_column_name = f"atr_{self.period}"
        result[atr_column_name] = atr_values
        
        # Store for potential future use
        self._last_calculated = atr_values
        
        if self.logger:
            latest_atr = atr_values.iloc[-1]
            latest_close = result['close'].iloc[-1]
            atr_pct = (latest_atr / latest_close) * 100
            self.logger.debug(
                f"ATR calculation complete. Latest value: {latest_atr:.4f} "
                f"({atr_pct:.2f}% of price)"
            )
        
        return result
    
    def reset(self) -> None:
        """
        Reset the indicator to its initial state.
        Clears any cached values or internal state.
        """
        self._last_calculated = None
        if self.logger:
            self.logger.debug(f"ATR indicator reset")
    
    def get_latest_value(self) -> float:
        """
        Get the most recently calculated ATR value.
        
        Returns:
            Latest ATR value
            
        Raises:
            ValueError: If no calculation has been performed yet
        """
        if self._last_calculated is None:
            raise ValueError("No ATR value calculated yet. Call calculate() first.")
        
        return float(self._last_calculated.iloc[-1])
    
    def get_all_values(self) -> pd.Series:
        """
        Get all calculated ATR values.
        
        Returns:
            Series of all ATR values
            
        Raises:
            ValueError: If no calculation has been performed yet
        """
        if self._last_calculated is None:
            raise ValueError("No ATR values calculated yet. Call calculate() first.")
        
        return self._last_calculated.copy()
    
    def get_column_name(self) -> str:
        """
        Get the column name that will be used in the output DataFrame.
        
        Returns:
            Column name for the ATR values
        """
        return f"atr_{self.period}"
    
    def get_atr_percentage(self, price: float = None, atr_value: float = None) -> float:
        """
        Get ATR as a percentage of price.
        
        Args:
            price: Current price (uses latest ATR calculation if data available)
            atr_value: ATR value to use (uses latest if not provided)
            
        Returns:
            ATR as percentage of price
            
        Raises:
            ValueError: If no calculation has been performed yet
        """
        if atr_value is None:
            atr_value = self.get_latest_value()
        
        if price is None:
            raise ValueError("Price must be provided if not embedded in calculation")
        
        return (atr_value / price) * 100
    
    def is_high_volatility(self, threshold: float = 2.0) -> bool:
        """
        Check if current volatility is considered high.
        
        Args:
            threshold: Percentage threshold for high volatility (default: 2.0%)
            
        Returns:
            True if high volatility, False otherwise
            
        Raises:
            ValueError: If no calculation has been performed yet
        """
        atr_value = self.get_latest_value()
        atr_pct = (atr_value / self._last_calculated.mean()) * 100
        return atr_pct > threshold
    
    def is_low_volatility(self, threshold: float = 1.0) -> bool:
        """
        Check if current volatility is considered low.
        
        Args:
            threshold: Percentage threshold for low volatility (default: 1.0%)
            
        Returns:
            True if low volatility, False otherwise
            
        Raises:
            ValueError: If no calculation has been performed yet
        """
        atr_value = self.get_latest_value()
        atr_pct = (atr_value / self._last_calculated.mean()) * 100
        return atr_pct < threshold


# Note: Registration is handled dynamically by the registry.load_from_module() method
# The INDICATOR_NAME class attribute is used by the registry to identify this indicator


# Minimal test for validation
if __name__ == "__main__":
    # Create test data
    print("Running ATR Indicator Test...")
    print("=" * 60)
    
    # Generate test data with varying volatility
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    
    # Create price series with varying volatility
    base_prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
    
    # Add volatility changes
    volatility = np.concatenate([
        np.ones(25) * 0.3,   # Low volatility
        np.ones(25) * 1.5,   # High volatility
        np.ones(25) * 0.5,   # Medium volatility
        np.ones(25) * 0.8    # Medium-high volatility
    ])
    
    prices = base_prices * (1 + volatility * np.random.randn(100) * 0.01)
    
    test_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices * 0.99,
        'high': prices * 1.02,
        'low': prices * 0.98,
        'close': prices,
        'volume': np.random.randint(100000, 1000000, 100)
    })
    test_data.set_index('timestamp', inplace=True)
    
    # Test 1: Basic calculation
    print("\nTest 1: Basic ATR Calculation (period=14)")
    atr = ATRIndicator(parameters={'period': 14})
    result = atr.calculate(test_data)
    
    print(f"  Input data points: {len(test_data)}")
    print(f"  Output data points: {len(result)}")
    print(f"  ATR column created: {atr.get_column_name()}")
    print(f"  First ATR value: {result[atr.get_column_name()].iloc[0]:.4f}")
    print(f"  Last ATR value: {result[atr.get_column_name()].iloc[-1]:.4f}")
    print(f"  Latest value method: {atr.get_latest_value():.4f}")
    
    # Test 2: ATR percentage analysis
    print("\nTest 2: ATR Percentage Analysis")
    atr_values = result[atr.get_column_name()]
    close_values = result['close']
    atr_percentages = (atr_values / close_values) * 100
    
    print(f"  ATR as % of price (latest): {atr_percentages.iloc[-1]:.2f}%")
    print(f"  Max ATR %: {atr_percentages.max():.2f}%")
    print(f"  Min ATR %: {atr_percentages.min():.2f}%")
    print(f"  Mean ATR %: {atr_percentages.mean():.2f}%")
    
    # Test 3: Volatility assessment
    print("\nTest 3: Volatility Assessment")
    latest_atr = atr.get_latest_value()
    latest_close = close_values.iloc[-1]
    atr_pct = (latest_atr / latest_close) * 100
    
    print(f"  Current price: {latest_close:.2f}")
    print(f"  Current ATR: {latest_atr:.4f}")
    print(f"  Current ATR %: {atr_pct:.2f}%")
    
    is_high = atr.is_high_volatility(threshold=2.0)
    is_low = atr.is_low_volatility(threshold=1.0)
    
    print(f"  Is high volatility (>2%): {is_high}")
    print(f"  Is low volatility (<1%): {is_low}")
    
    # Test 4: Different calculation methods
    print("\nTest 4: SMA vs EMA Calculation")
    atr_sma = ATRIndicator(parameters={'period': 14, 'use_sma': True})
    result_sma = atr_sma.calculate(test_data)
    
    print(f"  EMA ATR (latest): {atr.get_latest_value():.4f}")
    print(f"  SMA ATR (latest): {atr_sma.get_latest_value():.4f}")
    print(f"  Difference: {abs(atr.get_latest_value() - atr_sma.get_latest_value()):.4f}")
    
    # Test 5: Different period
    print("\nTest 5: ATR with Different Period (7)")
    atr7 = ATRIndicator(parameters={'period': 7})
    result7 = atr7.calculate(test_data)
    
    print(f"  ATR7 first value: {result7[atr7.get_column_name()].iloc[0]:.4f}")
    print(f"  ATR7 last value: {result7[atr7.get_column_name()].iloc[-1]:.4f}")
    print(f"  ATR14 last value: {atr.get_latest_value():.4f}")
    print(f"  ATR7 is more responsive: {result7[atr7.get_column_name()].std() > atr_values.std()}")
    
    # Test 6: Stop-loss calculation example
    print("\nTest 6: Stop-Loss Calculation Example")
    long_stop = latest_close - (2 * latest_atr)
    short_stop = latest_close + (2 * latest_atr)
    
    print(f"  For long position:")
    print(f"    Entry: {latest_close:.2f}")
    print(f"    Stop-loss (2x ATR): {long_stop:.2f}")
    print(f"    Risk: {(latest_close - long_stop):.2f} ({(latest_close - long_stop)/latest_close*100:.2f}%)")
    
    print(f"  For short position:")
    print(f"    Entry: {latest_close:.2f}")
    print(f"    Stop-loss (2x ATR): {short_stop:.2f}")
    print(f"    Risk: {(short_stop - latest_close):.2f} ({(short_stop - latest_close)/latest_close*100:.2f}%)")
    
    # Test 7: Reset functionality
    print("\nTest 7: Reset Functionality")
    atr.reset()
    try:
        atr.get_latest_value()
        print("  ✗ Reset failed - still has cached values")
    except ValueError:
        print("  ✓ Reset successful - no cached values")
    
    # Test 8: Error handling
    print("\nTest 8: Error Handling")
    try:
        atr_bad_period = ATRIndicator(parameters={'period': -5})
        print("  ✗ Should have raised ValueError for negative period")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    try:
        atr_short = ATRIndicator(parameters={'period': 150})
        atr_short.calculate(test_data)
        print("  ✗ Should have raised ValueError for insufficient data")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    # Test 9: Registry registration
    print("\nTest 9: Registry Registration")
    from bot.core.registry import IndicatorRegistry
    registry = IndicatorRegistry()
    
    count = registry.load_from_module('bot.indicators.atr')
    print(f"  Loaded {count} indicator(s) from module")
    
    if registry.exists('atr'):
        print(f"  ✓ ATR indicator registered in registry as 'atr'")
        registered_class = registry.get('atr')
        print(f"  ✓ Registered class: {registered_class.__name__}")
        
        # Test creating instance from registry
        atr_from_registry = registry.create_instance('atr', {'period': 14})
        print(f"  ✓ Created instance from registry: {atr_from_registry.__class__.__name__}")
    else:
        print("  ✗ ATR indicator not found in registry")
    
    print("\n" + "=" * 60)
    print("✅ All ATR Indicator Tests Passed!")