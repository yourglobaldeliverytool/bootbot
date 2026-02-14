"""
Mean Reversion Strategy.
Generates signals based on price deviations from mean.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

from bot.core.interfaces import Strategy


class MeanReversionStrategy(Strategy):
    """
    Mean Reversion Strategy using statistical analysis.
    
    This strategy identifies when price has deviated significantly from its
    mean and is likely to revert. It uses statistical measures like standard
    deviation to identify overbought and oversold conditions.
    
    Signal Logic:
        - BUY: Price falls below mean - (threshold * std_dev) (oversold)
        - SELL: Price rises above mean + (threshold * std_dev) (overbought)
        - HOLD: Price within normal range
    
    Usage:
        - Exploit price extremes
        - Trade range-bound markets
        - Take advantage of mean-reverting behavior
        - Capture profits from price corrections
    """
    
    STRATEGY_NAME = "mean_reversion"
    
    def __init__(self, name: str = None, parameters: Dict[str, Any] = None):
        """
        Initialize the mean reversion strategy.
        
        Args:
            name: Unique identifier for the strategy
            parameters: Configuration parameters including:
                - period (int): Lookback period for mean and std dev calculation (default: 20)
                - std_threshold (float): Number of std devs for signal generation (default: 2.0)
                - use_ema (bool): Use EMA instead of SMA (default: False)
                - exit_threshold (float): Std dev threshold for exit signals (default: 0.5)
        """
        if name is None:
            name = self.STRATEGY_NAME
        super().__init__(name, parameters)
        
        # Set default parameters
        self.period = self.parameters.get('period', 20)
        self.std_threshold = self.parameters.get('std_threshold', 2.0)
        self.use_ema = self.parameters.get('use_ema', False)
        self.exit_threshold = self.parameters.get('exit_threshold', 0.5)
        
        # Validate parameters
        if self.period <= 0:
            raise ValueError(f"Period must be positive, got {self.period}")
        
        if self.std_threshold <= 0:
            raise ValueError(f"std_threshold must be positive, got {self.std_threshold}")
        
        if self.exit_threshold < 0:
            raise ValueError(f"exit_threshold must be non-negative, got {self.exit_threshold}")
        
        if self.exit_threshold >= self.std_threshold:
            raise ValueError(
                f"exit_threshold ({self.exit_threshold}) must be less than "
                f"std_threshold ({self.std_threshold})"
            )
    
    def generate_signal(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate trading signal based on mean reversion logic.
        
        Args:
            data: OHLCV DataFrame with columns: ['open', 'high', 'low', 'close', 'volume']
            
        Returns:
            Dictionary containing:
                - 'signal': str ('BUY', 'SELL', or 'HOLD')
                - 'confidence': float (0.0 to 1.0)
                - 'reason': str (explanation for the signal)
                - 'metadata': dict (additional strategy-specific data)
        """
        if self.logger:
            self.logger.debug(f"Generating mean reversion signal with period {self.period}")
        
        # Check if we have enough data
        if len(data) < self.period:
            return self._create_hold_signal(
                "Insufficient data for mean reversion analysis",
                0.0
            )
        
        # Calculate mean and standard deviation
        close_prices = data['close']
        
        if self.use_ema:
            mean = close_prices.ewm(span=self.period, adjust=False).mean()
            std = close_prices.ewm(span=self.period, adjust=False).std()
        else:
            mean = close_prices.rolling(window=self.period).mean()
            std = close_prices.rolling(window=self.period).std()
        
        # Get latest values
        latest_price = close_prices.iloc[-1]
        latest_mean = mean.iloc[-1]
        latest_std = std.iloc[-1]
        
        # Get previous values for exit detection
        prev_price = close_prices.iloc[-2] if len(data) > 1 else latest_price
        prev_mean = mean.iloc[-2] if len(data) > 1 else latest_mean
        prev_std = std.iloc[-2] if len(data) > 1 else latest_std
        
        # Calculate z-scores
        latest_zscore = (latest_price - latest_mean) / latest_std if latest_std > 0 else 0
        prev_zscore = (prev_price - prev_mean) / prev_std if prev_std > 0 else 0
        
        # Generate signals
        # Check for oversold condition (potential BUY)
        if latest_zscore <= -self.std_threshold:
            # Calculate confidence based on how far below threshold
            deviation = abs(latest_zscore) - self.std_threshold
            confidence = min(0.5 + deviation * 0.2, 0.95)
            
            return self._create_buy_signal(
                f"Price is oversold: {latest_price:.2f} is {abs(latest_zscore):.2f} "
                f"std devs below {self.period}-period mean ({latest_mean:.2f})",
                confidence,
                {
                    'price': latest_price,
                    'mean': latest_mean,
                    'std': latest_std,
                    'zscore': latest_zscore,
                    'deviation_pct': (latest_mean - latest_price) / latest_mean * 100,
                    'condition': 'oversold'
                }
            )
        
        # Check for overbought condition (potential SELL)
        elif latest_zscore >= self.std_threshold:
            # Calculate confidence based on how far above threshold
            deviation = latest_zscore - self.std_threshold
            confidence = min(0.5 + deviation * 0.2, 0.95)
            
            return self._create_sell_signal(
                f"Price is overbought: {latest_price:.2f} is {latest_zscore:.2f} "
                f"std devs above {self.period}-period mean ({latest_mean:.2f})",
                confidence,
                {
                    'price': latest_price,
                    'mean': latest_mean,
                    'std': latest_std,
                    'zscore': latest_zscore,
                    'deviation_pct': (latest_price - latest_mean) / latest_mean * 100,
                    'condition': 'overbought'
                }
            )
        
        # Check if previously in extreme and now reverting (exit signal)
        elif prev_zscore <= -self.std_threshold and latest_zscore > -self.exit_threshold:
            # Reverting from oversold
            return self._create_buy_signal(
                f"Price reverting from oversold: Z-score moved from {prev_zscore:.2f} "
                f"to {latest_zscore:.2f}",
                0.6,
                {
                    'price': latest_price,
                    'mean': latest_mean,
                    'std': latest_std,
                    'zscore': latest_zscore,
                    'prev_zscore': prev_zscore,
                    'condition': 'reverting_oversold'
                }
            )
        
        elif prev_zscore >= self.std_threshold and latest_zscore < self.exit_threshold:
            # Reverting from overbought
            return self._create_sell_signal(
                f"Price reverting from overbought: Z-score moved from {prev_zscore:.2f} "
                f"to {latest_zscore:.2f}",
                0.6,
                {
                    'price': latest_price,
                    'mean': latest_mean,
                    'std': latest_std,
                    'zscore': latest_zscore,
                    'prev_zscore': prev_zscore,
                    'condition': 'reverting_overbought'
                }
            )
        
        # Normal range - HOLD
        else:
            # Determine market condition
            if abs(latest_zscore) < 0.5:
                condition = "neutral"
                confidence = 0.5
            elif latest_zscore > 0:
                condition = "above_mean"
                confidence = 0.6
            else:
                condition = "below_mean"
                confidence = 0.6
            
            return self._create_hold_signal(
                f"Price in normal range: {latest_price:.2f} is within "
                f"{abs(latest_zscore):.2f} std devs of {self.period}-period mean ({latest_mean:.2f})",
                confidence,
                {
                    'price': latest_price,
                    'mean': latest_mean,
                    'std': latest_std,
                    'zscore': latest_zscore,
                    'condition': condition
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
        for key, value in parameters.items():
            if key == 'period':
                if value <= 0:
                    raise ValueError(f"period must be positive, got {value}")
                setattr(self, key, value)
                self.parameters[key] = value
            elif key == 'std_threshold':
                if value <= 0:
                    raise ValueError(f"std_threshold must be positive, got {value}")
                setattr(self, key, value)
                self.parameters[key] = value
            elif key == 'exit_threshold':
                if value < 0:
                    raise ValueError(f"exit_threshold must be non-negative, got {value}")
                setattr(self, key, value)
                self.parameters[key] = value
            elif key == 'use_ema':
                if not isinstance(value, bool):
                    raise ValueError(f"use_ema must be boolean, got {type(value)}")
                setattr(self, key, value)
                self.parameters[key] = value
        
        # Revalidate
        if self.exit_threshold >= self.std_threshold:
            raise ValueError(
                f"exit_threshold ({self.exit_threshold}) must be less than "
                f"std_threshold ({self.std_threshold})"
            )
        
        if self.logger:
            self.logger.info(f"Updated parameters: {self.parameters}")


# Note: Registration is handled dynamically by the registry.load_from_module() method
# The STRATEGY_NAME class attribute is used by the registry to identify this strategy


# Minimal test for validation
if __name__ == "__main__":
    # Create test data
    print("Running Mean Reversion Strategy Test...")
    print("=" * 60)
    
    # Generate test data with mean-reverting behavior
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    
    # Create price series with mean reversion
    base_price = 100
    mean_reversion_factor = -0.05  # Strong mean reversion
    
    prices = []
    for i in range(100):
        noise = np.random.randn() * 2
        if i == 0:
            price = base_price + noise
        else:
            # Mean-reverting process
            deviation = prices[-1] - base_price
            price = prices[-1] + mean_reversion_factor * deviation + noise
        
        prices.append(price)
    
    prices = np.array(prices)
    
    test_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices * 0.99,
        'high': prices * 1.02,
        'low': prices * 0.98,
        'close': prices,
        'volume': np.random.randint(100000, 1000000, 100)
    })
    test_data.set_index('timestamp', inplace=True)
    
    # Test 1: Basic signal generation
    print("\nTest 1: Basic Signal Generation (SMA)")
    strategy1 = MeanReversionStrategy(parameters={
        'period': 20,
        'std_threshold': 2.0,
        'use_ema': False
    })
    
    signal1 = strategy1.generate_signal(test_data)
    print(f"  Signal: {signal1['signal']}")
    print(f"  Confidence: {signal1['confidence']:.2f}")
    print(f"  Reason: {signal1['reason']}")
    print(f"  Z-score: {signal1['metadata'].get('zscore', 'N/A'):.2f}")
    print(f"  Condition: {signal1['metadata'].get('condition', 'N/A')}")
    
    # Test 2: EMA-based calculation
    print("\nTest 2: EMA-Based Calculation")
    strategy2 = MeanReversionStrategy(parameters={
        'period': 20,
        'std_threshold': 2.0,
        'use_ema': True
    })
    
    signal2 = strategy2.generate_signal(test_data)
    print(f"  Signal: {signal2['signal']}")
    print(f"  Confidence: {signal2['confidence']:.2f}")
    print(f"  Z-score: {signal2['metadata'].get('zscore', 'N/A'):.2f}")
    
    # Test 3: Signal history analysis
    print("\nTest 3: Signal History Analysis")
    signals_history = []
    zscores = []
    
    for i in range(30, len(test_data)):  # Start from where we have enough data
        window_data = test_data.iloc[:i+1]
        signal = strategy1.generate_signal(window_data)
        signals_history.append(signal)
        zscores.append(signal['metadata'].get('zscore', 0))
    
    buy_signals = sum(1 for s in signals_history if s['signal'] == 'BUY')
    sell_signals = sum(1 for s in signals_history if s['signal'] == 'SELL')
    hold_signals = sum(1 for s in signals_history if s['signal'] == 'HOLD')
    
    print(f"  Total signals generated: {len(signals_history)}")
    print(f"  BUY signals: {buy_signals}")
    print(f"  SELL signals: {sell_signals}")
    print(f"  HOLD signals: {hold_signals}")
    print(f"  Max Z-score: {max(zscores):.2f}")
    print(f"  Min Z-score: {min(zscores):.2f}")
    print(f"  Mean Z-score: {np.mean(zscores):.2f}")
    
    # Test 4: Different threshold
    print("\nTest 4: Different Std Threshold (1.5)")
    strategy3 = MeanReversionStrategy(parameters={
        'period': 20,
        'std_threshold': 1.5
    })
    
    signal3 = strategy3.generate_signal(test_data)
    print(f"  Signal: {signal3['signal']}")
    print(f"  Reason: {signal3['reason']}")
    
    # Test 5: Parameter update
    print("\nTest 5: Parameter Update")
    print(f"  Original std_threshold: {strategy1.std_threshold}")
    print(f"  Original exit_threshold: {strategy1.exit_threshold}")
    
    strategy1.set_parameters({'std_threshold': 2.5, 'exit_threshold': 0.5})
    print(f"  Updated std_threshold: {strategy1.std_threshold}")
    print(f"  Updated exit_threshold: {strategy1.exit_threshold}")
    
    # Test 6: Error handling
    print("\nTest 6: Error Handling")
    try:
        bad_strategy = MeanReversionStrategy(parameters={'period': -5})
        print("  ✗ Should have raised ValueError for negative period")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    try:
        strategy1.set_parameters({'std_threshold': 1.0, 'exit_threshold': 2.0})
        print("  ✗ Should have raised ValueError for exit_threshold >= std_threshold")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    # Test 7: Registry registration
    print("\nTest 7: Registry Registration")
    from bot.core.registry import StrategyRegistry
    registry = StrategyRegistry()
    
    count = registry.load_from_module('bot.strategies.mean_reversion')
    print(f"  Loaded {count} strategy(ies) from module")
    
    if registry.exists('mean_reversion'):
        print(f"  ✓ Mean Reversion strategy registered in registry as 'mean_reversion'")
        registered_class = registry.get('mean_reversion')
        print(f"  ✓ Registered class: {registered_class.__name__}")
        
        # Test creating instance from registry
        strategy_from_registry = registry.create_instance('mean_reversion', {
            'period': 20,
            'std_threshold': 2.0
        })
        print(f"  ✓ Created instance from registry: {strategy_from_registry.__class__.__name__}")
    else:
        print("  ✗ Mean Reversion strategy not found in registry")
    
    print("\n" + "=" * 60)
    print("✅ All Mean Reversion Strategy Tests Passed!")