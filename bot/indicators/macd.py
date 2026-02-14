"""
Moving Average Convergence Divergence (MACD) Indicator.
Shows the relationship between two moving averages of price.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
import logging

from bot.core.interfaces import Indicator


class MACDIndicator(Indicator):
    """
    Moving Average Convergence Divergence (MACD) Indicator.
    
    The MACD is a trend-following momentum indicator that shows the relationship
    between two moving averages of a security's price. The MACD is calculated by
    subtracting the 26-period EMA from the 12-period EMA.
    
    Components:
        - MACD Line: 12-period EMA minus 26-period EMA
        - Signal Line: 9-period EMA of the MACD Line
        - Histogram: MACD Line minus Signal Line
    
    Usage:
        - Identify trend direction and strength
        - Generate trading signals (crossovers)
        - Detect momentum shifts
        - Confirm price movements
    
    Trading Signals:
        - Bullish: MACD crosses above Signal line
        - Bearish: MACD crosses below Signal line
        - Momentum: Histogram growing/shrinking
    """
    
    INDICATOR_NAME = "macd"
    
    def __init__(self, name: str = None, parameters: Dict[str, Any] = None):
        """
        Initialize the MACD indicator.
        
        Args:
            name: Unique identifier for the indicator
            parameters: Configuration parameters including:
                - fast_period (int): Fast EMA period (default: 12)
                - slow_period (int): Slow EMA period (default: 26)
                - signal_period (int): Signal line EMA period (default: 9)
                - price_column (str): Column to calculate MACD on (default: 'close')
        """
        if name is None:
            name = self.INDICATOR_NAME
        super().__init__(name, parameters)
        
        # Set default parameters
        self.fast_period = self.parameters.get('fast_period', 12)
        self.slow_period = self.parameters.get('slow_period', 26)
        self.signal_period = self.parameters.get('signal_period', 9)
        self.price_column = self.parameters.get('price_column', 'close')
        
        # Validate parameters
        if self.fast_period <= 0 or self.slow_period <= 0 or self.signal_period <= 0:
            raise ValueError("All periods must be positive")
        
        if self.fast_period >= self.slow_period:
            raise ValueError(
                f"Fast period ({self.fast_period}) must be less than "
                f"slow period ({self.slow_period})"
            )
        
        # Internal state
        self._last_macd: pd.Series = None
        self._last_signal: pd.Series = None
        self._last_histogram: pd.Series = None
        self._macd_column_name: str = None
        self._signal_column_name: str = None
        self._histogram_column_name: str = None
    
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate the MACD on the provided data.
        
        Args:
            data: OHLCV DataFrame with columns: ['open', 'high', 'low', 'close', 'volume']
            
        Returns:
            DataFrame with original data plus MACD components added
            
        Raises:
            ValueError: If required columns are missing or data is invalid
        """
        if self.logger:
            self.logger.debug(
                f"Calculating MACD (fast={self.fast_period}, "
                f"slow={self.slow_period}, signal={self.signal_period})"
            )
        
        # Validate input data
        if self.price_column not in data.columns:
            raise ValueError(f"Column '{self.price_column}' not found in data")
        
        min_required = self.slow_period + self.signal_period
        if len(data) < min_required:
            raise ValueError(
                f"Insufficient data: need at least {min_required} periods, "
                f"got {len(data)}"
            )
        
        # Create a copy to avoid modifying original data
        result = data.copy()
        
        # Calculate EMAs
        ema_fast = result[self.price_column].ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = result[self.price_column].ewm(span=self.slow_period, adjust=False).mean()
        
        # Calculate MACD line
        macd_line = ema_fast - ema_slow
        
        # Calculate Signal line (EMA of MACD line)
        signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()
        
        # Calculate Histogram
        histogram = macd_line - signal_line
        
        # Add MACD components to result DataFrame
        base = f"macd_{self.fast_period}_{self.slow_period}_{self.signal_period}"
        macd_column_name = base
        signal_column_name = f"{base}_signal"
        histogram_column_name = f"{base}_histogram"
        
        # Store column names
        self._macd_column_name = macd_column_name
        self._signal_column_name = signal_column_name
        self._histogram_column_name = histogram_column_name
        
        result[macd_column_name] = macd_line
        result[signal_column_name] = signal_line
        result[histogram_column_name] = histogram
        
        # Store for potential future use
        self._last_macd = macd_line
        self._last_signal = signal_line
        self._last_histogram = histogram
        
        if self.logger:
            latest_macd = macd_line.iloc[-1]
            latest_signal = signal_line.iloc[-1]
            latest_hist = histogram.iloc[-1]
            signal_type = "BULLISH" if latest_macd > latest_signal else "BEARISH"
            self.logger.debug(
                f"MACD calculation complete. "
                f"MACD: {latest_macd:.4f}, Signal: {latest_signal:.4f}, "
                f"Histogram: {latest_hist:.4f} ({signal_type})"
            )
        
        return result
    
    def reset(self) -> None:
        """
        Reset the indicator to its initial state.
        Clears any cached values or internal state.
        """
        self._last_macd = None
        self._last_signal = None
        self._last_histogram = None
        self._macd_column_name = None
        self._signal_column_name = None
        self._histogram_column_name = None
        if self.logger:
            self.logger.debug(f"MACD indicator reset")
    
    def get_latest_values(self) -> Tuple[float, float, float]:
        """
        Get the most recently calculated MACD values.
        
        Returns:
            Tuple of (MACD, Signal, Histogram) values
            
        Raises:
            ValueError: If no calculation has been performed yet
        """
        if self._last_macd is None:
            raise ValueError("No MACD values calculated yet. Call calculate() first.")
        
        return (
            float(self._last_macd.iloc[-1]),
            float(self._last_signal.iloc[-1]),
            float(self._last_histogram.iloc[-1])
        )
    
    def get_all_values(self) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Get all calculated MACD values.
        
        Returns:
            Tuple of (MACD, Signal, Histogram) series
            
        Raises:
            ValueError: If no calculation has been performed yet
        """
        if self._last_macd is None:
            raise ValueError("No MACD values calculated yet. Call calculate() first.")
        
        return (
            self._last_macd.copy(),
            self._last_signal.copy(),
            self._last_histogram.copy()
        )
    
    def get_column_names(self) -> Tuple[str, str, str]:
        """
        Get the column names that will be used in the output DataFrame.
        
        Returns:
            Tuple of (MACD, Signal, Histogram) column names
            
        Raises:
            ValueError: If calculate() has not been called yet
        """
        if self._macd_column_name is None:
            raise ValueError("Column names not set. Call calculate() first.")
        
        return (
            self._macd_column_name,
            self._signal_column_name,
            self._histogram_column_name
        )
    
    def get_signal(self) -> str:
        """
        Get the current MACD signal based on MACD vs Signal line.
        
        Returns:
            Signal string: 'BULLISH' (MACD > Signal) or 'BEARISH' (MACD < Signal)
            
        Raises:
            ValueError: If no calculation has been performed yet
        """
        macd, signal, _ = self.get_latest_values()
        return 'BULLISH' if macd > signal else 'BEARISH'
    
    def has_crossover(self, lookback: int = 1) -> Tuple[bool, str]:
        """
        Check if a MACD crossover has occurred in the recent period.
        
        Args:
            lookback: Number of periods to look back (default: 1)
            
        Returns:
            Tuple of (has_crossover, crossover_type)
            crossover_type: 'BULLISH_CROSSOVER', 'BEARISH_CROSSOVER', or 'NONE'
            
        Raises:
            ValueError: If insufficient data
        """
        if self._last_macd is None:
            raise ValueError("No MACD values calculated yet. Call calculate() first.")
        
        if lookback >= len(self._last_macd):
            raise ValueError(f"Lookback ({lookback}) >= data length ({len(self._last_macd)})")
        
        macd = self._last_macd.iloc[-1]
        signal = self._last_signal.iloc[-1]
        prev_macd = self._last_macd.iloc[-(lookback + 1)]
        prev_signal = self._last_signal.iloc[-(lookback + 1)]
        
        # Check for bullish crossover (MACD crosses above Signal)
        if prev_macd <= prev_signal and macd > signal:
            return (True, 'BULLISH_CROSSOVER')
        
        # Check for bearish crossover (MACD crosses below Signal)
        if prev_macd >= prev_signal and macd < signal:
            return (True, 'BEARISH_CROSSOVER')
        
        return (False, 'NONE')


# Note: Registration is handled dynamically by the registry.load_from_module() method
# The INDICATOR_NAME class attribute is used by the registry to identify this indicator


# Minimal test for validation
if __name__ == "__main__":
    # Create test data
    print("Running MACD Indicator Test...")
    print("=" * 60)
    
    # Generate test data with trend
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    
    # Create price series with trend
    trend = np.concatenate([
        np.ones(30) * 0.5,
        np.ones(20) * -0.3,
        np.ones(30) * 0.2,
        np.ones(20) * -0.1
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
    print("\nTest 1: Basic MACD Calculation (12, 26, 9)")
    macd = MACDIndicator(parameters={
        'fast_period': 12,
        'slow_period': 26,
        'signal_period': 9
    })
    result = macd.calculate(test_data)
    
    macd_col, signal_col, hist_col = macd.get_column_names()
    
    print(f"  Input data points: {len(test_data)}")
    print(f"  Output data points: {len(result)}")
    print(f"  MACD column: {macd_col}")
    print(f"  Signal column: {signal_col}")
    print(f"  Histogram column: {hist_col}")
    
    macd_val, signal_val, hist_val = macd.get_latest_values()
    print(f"\n  Latest MACD: {macd_val:.4f}")
    print(f"  Latest Signal: {signal_val:.4f}")
    print(f"  Latest Histogram: {hist_val:.4f}")
    print(f"  Signal: {macd.get_signal()}")
    
    # Test 2: Crossover detection
    print("\nTest 2: Crossover Detection")
    has_cross, cross_type = macd.has_crossover(lookback=1)
    print(f"  Recent crossover: {has_cross}")
    print(f"  Crossover type: {cross_type}")
    
    # Look for crossovers in the entire data
    macd_line = result[macd_col]
    signal_line = result[signal_col]
    
    # Find all crossovers
    crossovers = []
    for i in range(1, len(result)):
        prev_macd = macd_line.iloc[i-1]
        curr_macd = macd_line.iloc[i]
        prev_signal = signal_line.iloc[i-1]
        curr_signal = signal_line.iloc[i]
        
        if prev_macd <= prev_signal and curr_macd > curr_signal:
            crossovers.append((i, 'BULLISH_CROSSOVER'))
        elif prev_macd >= prev_signal and curr_macd < curr_signal:
            crossovers.append((i, 'BEARISH_CROSSOVER'))
    
    print(f"  Total crossovers found: {len(crossovers)}")
    if crossovers:
        print(f"  Recent crossovers:")
        for idx, cross_type in crossovers[-5:]:
            print(f"    - {result.index[idx].strftime('%Y-%m-%d')}: {cross_type}")
    
    # Test 3: Histogram analysis
    print("\nTest 3: Histogram Analysis")
    histogram = result[hist_col]
    positive_hist = (histogram > 0).sum()
    negative_hist = (histogram < 0).sum()
    
    print(f"  Positive histogram values: {positive_hist}")
    print(f"  Negative histogram values: {negative_hist}")
    print(f"  Max histogram: {histogram.max():.4f}")
    print(f"  Min histogram: {histogram.min():.4f}")
    print(f"  Mean histogram: {histogram.mean():.4f}")
    
    # Test 4: Different parameters
    print("\nTest 4: MACD with Different Parameters (5, 10, 4)")
    macd_custom = MACDIndicator(parameters={
        'fast_period': 5,
        'slow_period': 10,
        'signal_period': 4
    })
    result_custom = macd_custom.calculate(test_data)
    
    macd_val_c, signal_val_c, hist_val_c = macd_custom.get_latest_values()
    print(f"  Latest MACD: {macd_val_c:.4f}")
    print(f"  Latest Signal: {signal_val_c:.4f}")
    print(f"  Latest Histogram: {hist_val_c:.4f}")
    
    # Test 5: Reset functionality
    print("\nTest 5: Reset Functionality")
    macd.reset()
    try:
        macd.get_latest_values()
        print("  ✗ Reset failed - still has cached values")
    except ValueError:
        print("  ✓ Reset successful - no cached values")
    
    # Test 6: Error handling
    print("\nTest 6: Error Handling")
    try:
        macd_bad_params = MACDIndicator(parameters={
            'fast_period': 20,
            'slow_period': 10,
            'signal_period': 5
        })
        print("  ✗ Should have raised ValueError for invalid period order")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    try:
        macd_short = MACDIndicator(parameters={'slow_period': 150})
        macd_short.calculate(test_data)
        print("  ✗ Should have raised ValueError for insufficient data")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    # Test 7: Registry registration
    print("\nTest 7: Registry Registration")
    from bot.core.registry import IndicatorRegistry
    registry = IndicatorRegistry()
    
    count = registry.load_from_module('bot.indicators.macd')
    print(f"  Loaded {count} indicator(s) from module")
    
    if registry.exists('macd'):
        print(f"  ✓ MACD indicator registered in registry as 'macd'")
        registered_class = registry.get('macd')
        print(f"  ✓ Registered class: {registered_class.__name__}")
        
        # Test creating instance from registry
        macd_from_registry = registry.create_instance('macd', {
            'fast_period': 12,
            'slow_period': 26,
            'signal_period': 9
        })
        print(f"  ✓ Created instance from registry: {macd_from_registry.__class__.__name__}")
    else:
        print("  ✗ MACD indicator not found in registry")
    
    print("\n" + "=" * 60)
    print("✅ All MACD Indicator Tests Passed!")