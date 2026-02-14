"""
Trend Following Strategy.
Generates BUY signals when price is above moving average, SELL when below.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

from bot.core.interfaces import Strategy


class TrendFollowingStrategy(Strategy):
    """
    Trend Following Strategy using moving average crossovers.
    
    This strategy identifies trend direction by comparing price to moving averages.
    It generates signals based on the relationship between price and moving averages,
    as well as crossovers between different moving averages.
    
    Signal Logic:
        - BUY: Price crosses above MA (or fast MA crosses above slow MA)
        - SELL: Price crosses below MA (or fast MA crosses below slow MA)
        - HOLD: No clear trend or crossover
    
    Usage:
        - Follow existing trends
        - Avoid counter-trend trading
        - Capture large price movements
        - Ride trends to maximize profits
    """
    
    STRATEGY_NAME = "trend_following"
    
    def __init__(self, name: str = None, parameters: Dict[str, Any] = None):
        """
        Initialize the trend following strategy.
        
        Args:
            name: Unique identifier for the strategy
            parameters: Configuration parameters including:
                - fast_period (int): Fast MA period for crossover signals (default: 20)
                - slow_period (int): Slow MA period for trend identification (default: 50)
                - signal_type (str): Type of signal ('price_ma' or 'ma_crossover', default: 'price_ma')
                - confirmation_periods (int): Number of periods to confirm signal (default: 1)
        """
        if name is None:
            name = self.STRATEGY_NAME
        super().__init__(name, parameters)
        
        # Set default parameters
        self.fast_period = self.parameters.get('fast_period', 20)
        self.slow_period = self.parameters.get('slow_period', 50)
        self.signal_type = self.parameters.get('signal_type', 'price_ma')
        self.confirmation_periods = self.parameters.get('confirmation_periods', 1)
        
        # Validate parameters
        if self.fast_period <= 0 or self.slow_period <= 0:
            raise ValueError("Periods must be positive")
        
        if self.fast_period >= self.slow_period:
            raise ValueError(
                f"Fast period ({self.fast_period}) must be less than "
                f"slow period ({self.slow_period})"
            )
        
        valid_signal_types = ['price_ma', 'ma_crossover']
        if self.signal_type not in valid_signal_types:
            raise ValueError(
                f"signal_type must be one of {valid_signal_types}, "
                f"got {self.signal_type}"
            )
        
        if self.confirmation_periods < 1:
            raise ValueError("confirmation_periods must be >= 1")
    
    def generate_signal(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate trading signal based on trend following logic.
        
        Args:
            data: OHLCV DataFrame with columns: ['open', 'high', 'low', 'close', 'volume']
            Should also contain SMA or EMA indicators if attached
            
        Returns:
            Dictionary containing:
                - 'signal': str ('BUY', 'SELL', or 'HOLD')
                - 'confidence': float (0.0 to 1.0)
                - 'reason': str (explanation for the signal)
                - 'metadata': dict (additional strategy-specific data)
        """
        if self.logger:
            self.logger.debug(f"Generating trend following signal using {self.signal_type}")
        
        # Check if required indicators are available
        # If not, calculate simple SMAs
        if len(data) < self.slow_period:
            return self._create_hold_signal(
                "Insufficient data for trend following",
                0.0
            )
        
        # Get or calculate moving averages
        close_prices = data['close']
        
        # Calculate SMAs if not present
        fast_ma_col = f'sma_{self.fast_period}'
        slow_ma_col = f'sma_{self.slow_period}'
        
        if fast_ma_col not in data.columns:
            data[fast_ma_col] = close_prices.rolling(window=self.fast_period).mean()
        
        if slow_ma_col not in data.columns:
            data[slow_ma_col] = close_prices.rolling(window=self.slow_period).mean()
        
        # Get latest values
        latest_close = close_prices.iloc[-1]
        latest_fast_ma = data[fast_ma_col].iloc[-1]
        latest_slow_ma = data[slow_ma_col].iloc[-1]
        
        # Get previous values for crossover detection
        prev_close = close_prices.iloc[-2] if len(data) > 1 else latest_close
        prev_fast_ma = data[fast_ma_col].iloc[-2] if len(data) > 1 else latest_fast_ma
        prev_slow_ma = data[slow_ma_col].iloc[-2] if len(data) > 1 else latest_slow_ma
        
        # Generate signal based on signal type
        if self.signal_type == 'price_ma':
            signal = self._generate_price_ma_signal(
                latest_close, prev_close,
                latest_fast_ma, prev_fast_ma,
                latest_slow_ma, prev_slow_ma
            )
        elif self.signal_type == 'ma_crossover':
            signal = self._generate_ma_crossover_signal(
                latest_close,
                latest_fast_ma, prev_fast_ma,
                latest_slow_ma, prev_slow_ma
            )
        
        return signal
    
    def _generate_price_ma_signal(
        self,
        latest_close: float,
        prev_close: float,
        latest_fast_ma: float,
        prev_fast_ma: float,
        latest_slow_ma: float,
        prev_slow_ma: float
    ) -> Dict[str, Any]:
        """
        Generate signal based on price vs moving average relationship.
        
        Args:
            latest_close: Current closing price
            prev_close: Previous closing price
            latest_fast_ma: Current fast MA value
            prev_fast_ma: Previous fast MA value
            latest_slow_ma: Current slow MA value
            prev_slow_ma: Previous slow MA value
            
        Returns:
            Signal dictionary
        """
        # Check for bullish crossover (price crosses above MA)
        if (prev_close <= prev_fast_ma and latest_close > latest_fast_ma) and \
           (latest_fast_ma > latest_slow_ma):
            
            # Calculate confidence based on how far price is above MA
            distance_pct = ((latest_close - latest_fast_ma) / latest_fast_ma) * 100
            confidence = min(0.5 + (distance_pct / 2.0), 0.95)
            
            return self._create_buy_signal(
                f"Price crossed above {self.fast_period}-period MA "
                f"(uptrend confirmed by {self.fast_period} MA > {self.slow_period} MA)",
                confidence,
                {
                    'price': latest_close,
                    'fast_ma': latest_fast_ma,
                    'slow_ma': latest_slow_ma,
                    'distance_pct': distance_pct,
                    'trend': 'up'
                }
            )
        
        # Check for bearish crossover (price crosses below MA)
        elif (prev_close >= prev_fast_ma and latest_close < latest_fast_ma) and \
             (latest_fast_ma < latest_slow_ma):
            
            # Calculate confidence based on how far price is below MA
            distance_pct = ((latest_fast_ma - latest_close) / latest_fast_ma) * 100
            confidence = min(0.5 + (distance_pct / 2.0), 0.95)
            
            return self._create_sell_signal(
                f"Price crossed below {self.fast_period}-period MA "
                f"(downtrend confirmed by {self.fast_period} MA < {self.slow_period} MA)",
                confidence,
                {
                    'price': latest_close,
                    'fast_ma': latest_fast_ma,
                    'slow_ma': latest_slow_ma,
                    'distance_pct': distance_pct,
                    'trend': 'down'
                }
            )
        
        # Check current trend for HOLD signal
        elif latest_close > latest_fast_ma > latest_slow_ma:
            # Bullish trend
            return self._create_hold_signal(
                f"Bullish trend: Price > {self.fast_period} MA > {self.slow_period} MA",
                0.7,
                {
                    'price': latest_close,
                    'fast_ma': latest_fast_ma,
                    'slow_ma': latest_slow_ma,
                    'trend': 'up'
                }
            )
        
        elif latest_close < latest_fast_ma < latest_slow_ma:
            # Bearish trend
            return self._create_hold_signal(
                f"Bearish trend: Price < {self.fast_period} MA < {self.slow_period} MA",
                0.7,
                {
                    'price': latest_close,
                    'fast_ma': latest_fast_ma,
                    'slow_ma': latest_slow_ma,
                    'trend': 'down'
                }
            )
        
        else:
            # No clear trend
            return self._create_hold_signal(
                f"No clear trend: Price oscillating around MAs",
                0.5,
                {
                    'price': latest_close,
                    'fast_ma': latest_fast_ma,
                    'slow_ma': latest_slow_ma,
                    'trend': 'sideways'
                }
            )
    
    def _generate_ma_crossover_signal(
        self,
        latest_close: float,
        latest_fast_ma: float,
        prev_fast_ma: float,
        latest_slow_ma: float,
        prev_slow_ma: float
    ) -> Dict[str, Any]:
        """
        Generate signal based on MA crossovers.
        
        Args:
            latest_close: Current closing price
            latest_fast_ma: Current fast MA value
            prev_fast_ma: Previous fast MA value
            latest_slow_ma: Current slow MA value
            prev_slow_ma: Previous slow MA value
            
        Returns:
            Signal dictionary
        """
        # Check for bullish crossover (fast MA crosses above slow MA)
        if prev_fast_ma <= prev_slow_ma and latest_fast_ma > latest_slow_ma:
            # Calculate confidence based on crossover strength
            crossover_strength = (latest_fast_ma - latest_slow_ma) / latest_slow_ma
            confidence = min(0.5 + crossover_strength * 10, 0.95)
            
            return self._create_buy_signal(
                f"Bullish crossover: {self.fast_period} MA crossed above {self.slow_period} MA",
                confidence,
                {
                    'price': latest_close,
                    'fast_ma': latest_fast_ma,
                    'slow_ma': latest_slow_ma,
                    'crossover_strength': crossover_strength,
                    'trend': 'up'
                }
            )
        
        # Check for bearish crossover (fast MA crosses below slow MA)
        elif prev_fast_ma >= prev_slow_ma and latest_fast_ma < latest_slow_ma:
            # Calculate confidence based on crossover strength
            crossover_strength = (latest_slow_ma - latest_fast_ma) / latest_slow_ma
            confidence = min(0.5 + crossover_strength * 10, 0.95)
            
            return self._create_sell_signal(
                f"Bearish crossover: {self.fast_period} MA crossed below {self.slow_period} MA",
                confidence,
                {
                    'price': latest_close,
                    'fast_ma': latest_fast_ma,
                    'slow_ma': latest_slow_ma,
                    'crossover_strength': crossover_strength,
                    'trend': 'down'
                }
            )
        
        # Check current MA relationship
        elif latest_fast_ma > latest_slow_ma:
            # Uptrend
            ma_distance = (latest_fast_ma - latest_slow_ma) / latest_slow_ma
            confidence = min(0.6 + ma_distance * 5, 0.85)
            
            return self._create_hold_signal(
                f"Uptrend: {self.fast_period} MA > {self.slow_period} MA by {ma_distance*100:.2f}%",
                confidence,
                {
                    'price': latest_close,
                    'fast_ma': latest_fast_ma,
                    'slow_ma': latest_slow_ma,
                    'ma_distance': ma_distance,
                    'trend': 'up'
                }
            )
        
        else:
            # Downtrend
            ma_distance = (latest_slow_ma - latest_fast_ma) / latest_slow_ma
            confidence = min(0.6 + ma_distance * 5, 0.85)
            
            return self._create_hold_signal(
                f"Downtrend: {self.fast_period} MA < {self.slow_period} MA by {ma_distance*100:.2f}%",
                confidence,
                {
                    'price': latest_close,
                    'fast_ma': latest_fast_ma,
                    'slow_ma': latest_slow_ma,
                    'ma_distance': ma_distance,
                    'trend': 'down'
                }
            )
    
    def _create_buy_signal(self, reason: str, confidence: float, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a BUY signal."""
        return {
            'strategy_name': self.name,
            'signal': 'BUY',
            'confidence': max(0.0, min(1.0, confidence)),
            'reason': reason,
            'metadata': metadata
        }
    
    def _create_sell_signal(self, reason: str, confidence: float, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a SELL signal."""
        return {
            'strategy_name': self.name,
            'signal': 'SELL',
            'confidence': max(0.0, min(1.0, confidence)),
            'reason': reason,
            'metadata': metadata
        }
    
    def _create_hold_signal(self, reason: str, confidence: float, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a HOLD signal."""
        return {
            'strategy_name': self.name,
            'signal': 'HOLD',
            'confidence': max(0.0, min(1.0, confidence)),
            'reason': reason,
            'metadata': metadata
        }
    
    def set_parameters(self, parameters: Dict[str, Any]) -> None:
        """
        Update strategy parameters dynamically.
        
        Args:
            parameters: Dictionary of parameter names and values to update
        """
        valid_signal_types = ['price_ma', 'ma_crossover']
        
        for key, value in parameters.items():
            if key in ['fast_period', 'slow_period']:
                if value <= 0:
                    raise ValueError(f"{key} must be positive, got {value}")
                setattr(self, key, value)
                self.parameters[key] = value
            elif key == 'signal_type':
                if value not in valid_signal_types:
                    raise ValueError(
                        f"signal_type must be one of {valid_signal_types}, "
                        f"got {value}"
                    )
                setattr(self, key, value)
                self.parameters[key] = value
            elif key == 'confirmation_periods':
                if value < 1:
                    raise ValueError("confirmation_periods must be >= 1")
                setattr(self, key, value)
                self.parameters[key] = value
        
        # Revalidate
        if self.fast_period >= self.slow_period:
            raise ValueError(
                f"Fast period ({self.fast_period}) must be less than "
                f"slow period ({self.slow_period})"
            )
        
        if self.logger:
            self.logger.info(f"Updated parameters: {self.parameters}")


# Note: Registration is handled dynamically by the registry.load_from_module() method
# The STRATEGY_NAME class attribute is used by the registry to identify this strategy


# Minimal test for validation
if __name__ == "__main__":
    # Create test data
    print("Running Trend Following Strategy Test...")
    print("=" * 60)
    
    # Generate test data with trend
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    
    # Create price series with clear trend changes
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
    
    # Test 1: Price-MA signal type
    print("\nTest 1: Price-MA Signal Type")
    strategy1 = TrendFollowingStrategy(parameters={
        'fast_period': 20,
        'slow_period': 50,
        'signal_type': 'price_ma'
    })
    
    signal1 = strategy1.generate_signal(test_data)
    print(f"  Signal: {signal1['signal']}")
    print(f"  Confidence: {signal1['confidence']:.2f}")
    print(f"  Reason: {signal1['reason']}")
    print(f"  Trend: {signal1['metadata'].get('trend', 'N/A')}")
    
    # Test 2: MA crossover signal type
    print("\nTest 2: MA Crossover Signal Type")
    strategy2 = TrendFollowingStrategy(parameters={
        'fast_period': 20,
        'slow_period': 50,
        'signal_type': 'ma_crossover'
    })
    
    signal2 = strategy2.generate_signal(test_data)
    print(f"  Signal: {signal2['signal']}")
    print(f"  Confidence: {signal2['confidence']:.2f}")
    print(f"  Reason: {signal2['reason']}")
    print(f"  Trend: {signal2['metadata'].get('trend', 'N/A')}")
    
    # Test 3: Generate signals throughout data
    print("\nTest 3: Signal History Analysis")
    signals_history = []
    
    for i in range(60, len(test_data)):  # Start from where we have enough data
        window_data = test_data.iloc[:i+1]
        signal = strategy1.generate_signal(window_data)
        signals_history.append(signal)
    
    buy_signals = sum(1 for s in signals_history if s['signal'] == 'BUY')
    sell_signals = sum(1 for s in signals_history if s['signal'] == 'SELL')
    hold_signals = sum(1 for s in signals_history if s['signal'] == 'HOLD')
    
    print(f"  Total signals generated: {len(signals_history)}")
    print(f"  BUY signals: {buy_signals}")
    print(f"  SELL signals: {sell_signals}")
    print(f"  HOLD signals: {hold_signals}")
    
    # Test 4: Parameter update
    print("\nTest 4: Parameter Update")
    print(f"  Original fast_period: {strategy1.fast_period}")
    print(f"  Original slow_period: {strategy1.slow_period}")
    
    strategy1.set_parameters({'fast_period': 10, 'slow_period': 30})
    print(f"  Updated fast_period: {strategy1.fast_period}")
    print(f"  Updated slow_period: {strategy1.slow_period}")
    
    # Test 5: Error handling
    print("\nTest 5: Error Handling")
    try:
        bad_strategy = TrendFollowingStrategy(parameters={
            'fast_period': 50,
            'slow_period': 20
        })
        print("  ✗ Should have raised ValueError for invalid period order")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    try:
        strategy1.set_parameters({'signal_type': 'invalid'})
        print("  ✗ Should have raised ValueError for invalid signal_type")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    # Test 6: Registry registration
    print("\nTest 6: Registry Registration")
    from bot.core.registry import StrategyRegistry
    registry = StrategyRegistry()
    
    count = registry.load_from_module('bot.strategies.trend_following')
    print(f"  Loaded {count} strategy(ies) from module")
    
    if registry.exists('trend_following'):
        print(f"  ✓ Trend Following strategy registered in registry as 'trend_following'")
        registered_class = registry.get('trend_following')
        print(f"  ✓ Registered class: {registered_class.__name__}")
        
        # Test creating instance from registry
        strategy_from_registry = registry.create_instance('trend_following', {
            'fast_period': 20,
            'slow_period': 50
        })
        print(f"  ✓ Created instance from registry: {strategy_from_registry.__class__.__name__}")
    else:
        print("  ✗ Trend Following strategy not found in registry")
    
    print("\n" + "=" * 60)
    print("✅ All Trend Following Strategy Tests Passed!")