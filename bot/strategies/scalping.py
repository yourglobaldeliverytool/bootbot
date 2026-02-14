"""
Scalping Strategy.
Generates signals for short-term trades based on quick price movements.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

from bot.core.interfaces import Strategy


class ScalpingStrategy(Strategy):
    """
    Scalping Strategy for high-frequency short-term trades.
    
    This strategy identifies short-term price movements and generates
    quick entry/exit signals. It uses fast-moving averages and momentum
    indicators to capture small price movements.
    
    Signal Logic:
        - BUY: Fast momentum upward with price above fast MA
        - SELL: Fast momentum downward with price below fast MA
        - HOLD: No clear short-term momentum
    
    Usage:
        - Capture small price movements
        - High-frequency trading
        - Quick entry and exit
        - Trade market microstructure
    """
    
    STRATEGY_NAME = "scalping"
    
    def __init__(self, name: str = None, parameters: Dict[str, Any] = None):
        """
        Initialize the scalping strategy.
        
        Args:
            name: Unique identifier for the strategy
            parameters: Configuration parameters including:
                - fast_period (int): Very fast MA period (default: 5)
                - momentum_period (int): Momentum calculation period (default: 3)
                - min_profit_pct (float): Minimum profit percentage (default: 0.01)
                - max_loss_pct (float): Maximum loss percentage (default: 0.005)
        """
        if name is None:
            name = self.STRATEGY_NAME
        super().__init__(name, parameters)
        
        # Set default parameters
        self.fast_period = self.parameters.get('fast_period', 5)
        self.momentum_period = self.parameters.get('momentum_period', 3)
        self.min_profit_pct = self.parameters.get('min_profit_pct', 0.01)
        self.max_loss_pct = self.parameters.get('max_loss_pct', 0.005)
        
        # Validate parameters
        if self.fast_period <= 0:
            raise ValueError(f"fast_period must be positive, got {self.fast_period}")
        
        if self.momentum_period <= 0:
            raise ValueError(f"momentum_period must be positive, got {self.momentum_period}")
        
        if self.min_profit_pct <= 0:
            raise ValueError(f"min_profit_pct must be positive, got {self.min_profit_pct}")
        
        if self.max_loss_pct <= 0:
            raise ValueError(f"max_loss_pct must be positive, got {self.max_loss_pct}")
    
    def generate_signal(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate trading signal based on scalping logic.
        
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
            self.logger.debug(f"Generating scalping signal with fast_period {self.fast_period}")
        
        # Check if we have enough data
        required_period = max(self.fast_period, self.momentum_period) + 1
        if len(data) < required_period:
            return self._create_hold_signal(
                "Insufficient data for scalping analysis",
                0.0
            )
        
        # Get prices
        close_prices = data['close']
        high_prices = data['high']
        low_prices = data['low']
        
        # Calculate fast MA
        fast_ma = close_prices.rolling(window=self.fast_period).mean()
        
        # Calculate momentum
        momentum = close_prices.diff(self.momentum_period)
        
        # Get latest values
        latest_close = close_prices.iloc[-1]
        latest_high = high_prices.iloc[-1]
        latest_low = low_prices.iloc[-1]
        latest_fast_ma = fast_ma.iloc[-1]
        latest_momentum = momentum.iloc[-1]
        
        # Get previous values for momentum change detection
        prev_momentum = momentum.iloc[-2] if len(data) > 1 else latest_momentum
        prev_close = close_prices.iloc[-2] if len(data) > 1 else latest_close
        
        # Calculate momentum acceleration
        momentum_acceleration = latest_momentum - prev_momentum
        
        # Calculate price position relative to MA
        ma_diff_pct = ((latest_close - latest_fast_ma) / latest_fast_ma) * 100
        
        # Calculate recent volatility (using high-low range)
        recent_high_low_range = ((latest_high - latest_low) / latest_close) * 100
        
        # Generate signals
        
        # Check for strong upward momentum with price above MA
        if latest_momentum > 0 and momentum_acceleration > 0 and latest_close > latest_fast_ma:
            # Calculate confidence based on momentum strength
            momentum_strength = abs(latest_momentum) / latest_close * 100
            ma_adjustment = max(0, ma_diff_pct) * 2
            confidence = min(0.5 + momentum_strength * 5 + ma_adjustment, 0.9)
            
            # Check if potential profit meets minimum
            if momentum_strength >= self.min_profit_pct:
                return self._create_buy_signal(
                    f"Strong upward momentum: Price {latest_close:.2f} above "
                    f"{self.fast_period}-period MA ({latest_fast_ma:.2f}), "
                    f"momentum {latest_momentum:.2f}",
                    confidence,
                    {
                        'price': latest_close,
                        'fast_ma': latest_fast_ma,
                        'momentum': latest_momentum,
                        'momentum_pct': momentum_strength,
                        'ma_diff_pct': ma_diff_pct,
                        'acceleration': momentum_acceleration,
                        'volatility': recent_high_low_range,
                        'condition': 'bullish_momentum'
                    }
                )
        
        # Check for strong downward momentum with price below MA
        elif latest_momentum < 0 and momentum_acceleration < 0 and latest_close < latest_fast_ma:
            # Calculate confidence based on momentum strength
            momentum_strength = abs(latest_momentum) / latest_close * 100
            ma_adjustment = max(0, -ma_diff_pct) * 2
            confidence = min(0.5 + momentum_strength * 5 + ma_adjustment, 0.9)
            
            # Check if potential profit meets minimum
            if momentum_strength >= self.min_profit_pct:
                return self._create_sell_signal(
                    f"Strong downward momentum: Price {latest_close:.2f} below "
                    f"{self.fast_period}-period MA ({latest_fast_ma:.2f}), "
                    f"momentum {latest_momentum:.2f}",
                    confidence,
                    {
                        'price': latest_close,
                        'fast_ma': latest_fast_ma,
                        'momentum': latest_momentum,
                        'momentum_pct': momentum_strength,
                        'ma_diff_pct': ma_diff_pct,
                        'acceleration': momentum_acceleration,
                        'volatility': recent_high_low_range,
                        'condition': 'bearish_momentum'
                    }
                )
        
        # Check for quick reversal signals
        elif prev_momentum > 0 and latest_momentum < 0:
            # Bearish reversal
            momentum_change = abs(latest_momentum) / latest_close * 100
            confidence = min(0.5 + momentum_change * 5, 0.85)
            
            return self._create_sell_signal(
                f"Bearish reversal: Momentum changed from {prev_momentum:.2f} "
                f"to {latest_momentum:.2f}",
                confidence,
                {
                    'price': latest_close,
                    'prev_momentum': prev_momentum,
                    'momentum': latest_momentum,
                    'momentum_change': momentum_change,
                    'fast_ma': latest_fast_ma,
                    'condition': 'bearish_reversal'
                }
            )
        
        elif prev_momentum < 0 and latest_momentum > 0:
            # Bullish reversal
            momentum_change = abs(latest_momentum) / latest_close * 100
            confidence = min(0.5 + momentum_change * 5, 0.85)
            
            return self._create_buy_signal(
                f"Bullish reversal: Momentum changed from {prev_momentum:.2f} "
                f"to {latest_momentum:.2f}",
                confidence,
                {
                    'price': latest_close,
                    'prev_momentum': prev_momentum,
                    'momentum': latest_momentum,
                    'momentum_change': momentum_change,
                    'fast_ma': latest_fast_ma,
                    'condition': 'bullish_reversal'
                }
            )
        
        # No clear signal - HOLD
        else:
            # Determine market condition
            if abs(momentum_acceleration) > 0.01:
                condition = "accelerating"
                confidence = 0.6
            elif latest_momentum > 0:
                condition = "slow_bullish"
                confidence = 0.55
            elif latest_momentum < 0:
                condition = "slow_bearish"
                confidence = 0.55
            else:
                condition = "flat"
                confidence = 0.5
            
            return self._create_hold_signal(
                f"No clear scalping signal: Momentum {latest_momentum:.2f}, "
                f"price {latest_close:.2f} vs {self.fast_period}-period MA {latest_fast_ma:.2f}",
                confidence,
                {
                    'price': latest_close,
                    'fast_ma': latest_fast_ma,
                    'momentum': latest_momentum,
                    'acceleration': momentum_acceleration,
                    'volatility': recent_high_low_range,
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
            if key in ['fast_period', 'momentum_period']:
                if value <= 0:
                    raise ValueError(f"{key} must be positive, got {value}")
                setattr(self, key, value)
                self.parameters[key] = value
            elif key in ['min_profit_pct', 'max_loss_pct']:
                if value <= 0:
                    raise ValueError(f"{key} must be positive, got {value}")
                setattr(self, key, value)
                self.parameters[key] = value
        
        if self.logger:
            self.logger.info(f"Updated parameters: {self.parameters}")


# Note: Registration is handled dynamically by the registry.load_from_module() method
# The STRATEGY_NAME class attribute is used by the registry to identify this strategy


# Minimal test for validation
if __name__ == "__main__":
    # Create test data
    print("Running Scalping Strategy Test...")
    print("=" * 60)
    
    # Generate test data with quick movements
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    
    # Create price series with quick movements for scalping
    base_price = 100
    volatility = 0.02  # 2% daily volatility
    
    prices = []
    for i in range(100):
        # Add some directional changes
        if i % 10 == 0:
            direction = 1
        elif i % 10 == 5:
            direction = -1
        else:
            direction = 0
        
        noise = np.random.randn() * volatility * base_price
        if i == 0:
            price = base_price + noise
        else:
            price = prices[-1] + (direction * volatility * base_price * 0.5) + noise
        
        prices.append(price)
    
    prices = np.array(prices)
    
    test_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices * 0.99,
        'high': prices * 1.01,
        'low': prices * 0.99,
        'close': prices,
        'volume': np.random.randint(100000, 1000000, 100)
    })
    test_data.set_index('timestamp', inplace=True)
    
    # Test 1: Basic signal generation
    print("\nTest 1: Basic Signal Generation")
    strategy1 = ScalpingStrategy(parameters={
        'fast_period': 5,
        'momentum_period': 3,
        'min_profit_pct': 0.01
    })
    
    signal1 = strategy1.generate_signal(test_data)
    print(f"  Signal: {signal1['signal']}")
    print(f"  Confidence: {signal1['confidence']:.2f}")
    print(f"  Reason: {signal1['reason']}")
    print(f"  Condition: {signal1['metadata'].get('condition', 'N/A')}")
    print(f"  Momentum: {signal1['metadata'].get('momentum', 'N/A'):.2f}")
    
    # Test 2: Signal history analysis
    print("\nTest 2: Signal History Analysis")
    signals_history = []
    
    for i in range(10, len(test_data)):  # Start from where we have enough data
        window_data = test_data.iloc[:i+1]
        signal = strategy1.generate_signal(window_data)
        signals_history.append(signal)
    
    buy_signals = sum(1 for s in signals_history if s['signal'] == 'BUY')
    sell_signals = sum(1 for s in signals_history if s['signal'] == 'SELL')
    hold_signals = sum(1 for s in signals_history if s['signal'] == 'HOLD')
    reversal_signals = sum(1 for s in signals_history if 'reversal' in s['metadata'].get('condition', ''))
    
    print(f"  Total signals generated: {len(signals_history)}")
    print(f"  BUY signals: {buy_signals}")
    print(f"  SELL signals: {sell_signals}")
    print(f"  HOLD signals: {hold_signals}")
    print(f"  Reversal signals: {reversal_signals}")
    
    # Test 3: Different parameters
    print("\nTest 3: Different Parameters (faster scalping)")
    strategy2 = ScalpingStrategy(parameters={
        'fast_period': 3,
        'momentum_period': 2,
        'min_profit_pct': 0.02
    })
    
    signal2 = strategy2.generate_signal(test_data)
    print(f"  Signal: {signal2['signal']}")
    print(f"  Reason: {signal2['reason']}")
    
    # Test 4: Parameter update
    print("\nTest 4: Parameter Update")
    print(f"  Original fast_period: {strategy1.fast_period}")
    print(f"  Original min_profit_pct: {strategy1.min_profit_pct}")
    
    strategy1.set_parameters({'fast_period': 7, 'min_profit_pct': 0.015})
    print(f"  Updated fast_period: {strategy1.fast_period}")
    print(f"  Updated min_profit_pct: {strategy1.min_profit_pct}")
    
    # Test 5: Error handling
    print("\nTest 5: Error Handling")
    try:
        bad_strategy = ScalpingStrategy(parameters={'fast_period': -5})
        print("  ✗ Should have raised ValueError for negative fast_period")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    try:
        strategy1.set_parameters({'min_profit_pct': 0})
        print("  ✗ Should have raised ValueError for zero min_profit_pct")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    # Test 6: Registry registration
    print("\nTest 6: Registry Registration")
    from bot.core.registry import StrategyRegistry
    registry = StrategyRegistry()
    
    count = registry.load_from_module('bot.strategies.scalping')
    print(f"  Loaded {count} strategy(ies) from module")
    
    if registry.exists('scalping'):
        print(f"  ✓ Scalping strategy registered in registry as 'scalping'")
        registered_class = registry.get('scalping')
        print(f"  ✓ Registered class: {registered_class.__name__}")
        
        # Test creating instance from registry
        strategy_from_registry = registry.create_instance('scalping', {
            'fast_period': 5,
            'momentum_period': 3
        })
        print(f"  ✓ Created instance from registry: {strategy_from_registry.__class__.__name__}")
    else:
        print("  ✗ Scalping strategy not found in registry")
    
    print("\n" + "=" * 60)
    print("✅ All Scalping Strategy Tests Passed!")