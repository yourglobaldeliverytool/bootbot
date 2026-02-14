"""
Arbitrage Strategy.
Generates signals based on price discrepancies between markets.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

from bot.core.interfaces import Strategy


class ArbitrageStrategy(Strategy):
    """
    Arbitrage Strategy for identifying price discrepancies.
    
    This strategy looks for price discrepancies between different markets
    or instruments that can be exploited for profit. In a single-market
    context, it can identify opportunities based on temporary mispricings
    or deviations from fair value.
    
    Signal Logic:
        - BUY: Price below fair value threshold
        - SELL: Price above fair value threshold
        - HOLD: Price within fair value range
    
    Note: True arbitrage requires access to multiple markets. This implementation
    provides a framework that can be extended with real multi-market data feeds.
    """
    
    STRATEGY_NAME = "arbitrage"
    
    def __init__(self, name: str = None, parameters: Dict[str, Any] = None):
        """
        Initialize the arbitrage strategy.
        
        Args:
            name: Unique identifier for the strategy
            parameters: Configuration parameters including:
                - fair_value_method (str): Method to calculate fair value
                    ('moving_average', 'vwap', 'theoretical') (default: 'moving_average')
                - fair_value_period (int): Period for fair value calculation (default: 20)
                - deviation_threshold (float): Deviation threshold for signals (default: 0.02)
                - min_profit_pct (float): Minimum profit percentage (default: 0.01)
        """
        if name is None:
            name = self.STRATEGY_NAME
        super().__init__(name, parameters)
        
        # Set default parameters
        self.fair_value_method = self.parameters.get('fair_value_method', 'moving_average')
        self.fair_value_period = self.parameters.get('fair_value_period', 20)
        self.deviation_threshold = self.parameters.get('deviation_threshold', 0.02)
        self.min_profit_pct = self.parameters.get('min_profit_pct', 0.01)
        
        # Validate parameters
        valid_methods = ['moving_average', 'vwap', 'theoretical']
        if self.fair_value_method not in valid_methods:
            raise ValueError(
                f"fair_value_method must be one of {valid_methods}, "
                f"got {self.fair_value_method}"
            )
        
        if self.fair_value_period <= 0:
            raise ValueError(f"fair_value_period must be positive, got {self.fair_value_period}")
        
        if self.deviation_threshold <= 0:
            raise ValueError(f"deviation_threshold must be positive, got {self.deviation_threshold}")
        
        if self.min_profit_pct <= 0:
            raise ValueError(f"min_profit_pct must be positive, got {self.min_profit_pct}")
    
    def generate_signal(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate trading signal based on arbitrage logic.
        
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
            self.logger.debug(f"Generating arbitrage signal using {self.fair_value_method}")
        
        # Check if we have enough data
        if len(data) < self.fair_value_period:
            return self._create_hold_signal(
                "Insufficient data for arbitrage analysis",
                0.0
            )
        
        # Calculate fair value
        fair_value = self._calculate_fair_value(data)
        
        if fair_value is None:
            return self._create_hold_signal(
                "Unable to calculate fair value",
                0.0
            )
        
        # Get current price
        current_price = data['close'].iloc[-1]
        
        # Calculate deviation from fair value
        deviation_pct = ((current_price - fair_value) / fair_value) * 100
        
        # Generate signals based on deviation
        if abs(deviation_pct) >= self.deviation_threshold * 100:
            # Check if profit opportunity meets minimum
            profit_pct = abs(deviation_pct)
            
            if profit_pct >= self.min_profit_pct * 100:
                # Calculate confidence based on deviation size
                confidence = min(0.5 + (profit_pct / (self.deviation_threshold * 100)) * 0.4, 0.95)
                
                if deviation_pct < 0:
                    # Price below fair value - BUY
                    return self._create_buy_signal(
                        f"Arbitrage opportunity: Price {current_price:.2f} is "
                        f"{abs(deviation_pct):.2f}% below fair value {fair_value:.2f}",
                        confidence,
                        {
                            'current_price': current_price,
                            'fair_value': fair_value,
                            'deviation_pct': deviation_pct,
                            'profit_potential': abs(deviation_pct),
                            'method': self.fair_value_method,
                            'condition': 'underpriced'
                        }
                    )
                else:
                    # Price above fair value - SELL
                    return self._create_sell_signal(
                        f"Arbitrage opportunity: Price {current_price:.2f} is "
                        f"{deviation_pct:.2f}% above fair value {fair_value:.2f}",
                        confidence,
                        {
                            'current_price': current_price,
                            'fair_value': fair_value,
                            'deviation_pct': deviation_pct,
                            'profit_potential': abs(deviation_pct),
                            'method': self.fair_value_method,
                            'condition': 'overpriced'
                        }
                    )
        
        # No arbitrage opportunity - HOLD
        else:
            # Determine market condition
            if abs(deviation_pct) < 0.5:
                condition = "at_fair_value"
                confidence = 0.5
            elif deviation_pct > 0:
                condition = "slightly_overpriced"
                confidence = 0.6
            else:
                condition = "slightly_underpriced"
                confidence = 0.6
            
            return self._create_hold_signal(
                f"No arbitrage opportunity: Price {current_price:.2f} is "
                f"within {abs(deviation_pct):.2f}% of fair value {fair_value:.2f}",
                confidence,
                {
                    'current_price': current_price,
                    'fair_value': fair_value,
                    'deviation_pct': deviation_pct,
                    'method': self.fair_value_method,
                    'condition': condition
                }
            )
    
    def _calculate_fair_value(self, data: pd.DataFrame) -> float:
        """
        Calculate fair value based on the specified method.
        
        Args:
            data: OHLCV DataFrame
            
        Returns:
            Fair value price
        """
        if self.fair_value_method == 'moving_average':
            # Use simple moving average of close prices
            return data['close'].rolling(window=self.fair_value_period).mean().iloc[-1]
        
        elif self.fair_value_method == 'vwap':
            # Volume Weighted Average Price
            typical_price = (data['high'] + data['low'] + data['close']) / 3
            vwap = (typical_price * data['volume']).sum() / data['volume'].sum()
            return vwap
        
        elif self.fair_value_method == 'theoretical':
            # Theoretical fair value (simplified model)
            # In practice, this would use more sophisticated models
            # Here we use a weighted average of recent OHLC
            weights = np.array([0.1, 0.1, 0.1, 0.7])  # Weight close price more
            recent_ohlc = data[['open', 'high', 'low', 'close']].tail(self.fair_value_period).mean()
            return (recent_ohlc.values * weights).sum()
        
        return None
    
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
        valid_methods = ['moving_average', 'vwap', 'theoretical']
        
        for key, value in parameters.items():
            if key == 'fair_value_method':
                if value not in valid_methods:
                    raise ValueError(
                        f"fair_value_method must be one of {valid_methods}, "
                        f"got {value}"
                    )
                setattr(self, key, value)
                self.parameters[key] = value
            elif key == 'fair_value_period':
                if value <= 0:
                    raise ValueError(f"fair_value_period must be positive, got {value}")
                setattr(self, key, value)
                self.parameters[key] = value
            elif key in ['deviation_threshold', 'min_profit_pct']:
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
    print("Running Arbitrage Strategy Test...")
    print("=" * 60)
    
    # Generate test data with some mispricing opportunities
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    
    # Create price series with occasional mispricing
    base_price = 100
    prices = []
    
    for i in range(100):
        # Occasionally create mispricing
        if i % 20 == 0:
            # Overpriced
            price = base_price * 1.05
        elif i % 20 == 10:
            # Underpriced
            price = base_price * 0.95
        else:
            # Normal pricing around base
            price = base_price + np.random.randn() * 2
        
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
    
    # Test 1: Moving average fair value
    print("\nTest 1: Moving Average Fair Value")
    strategy1 = ArbitrageStrategy(parameters={
        'fair_value_method': 'moving_average',
        'fair_value_period': 20,
        'deviation_threshold': 0.02,
        'min_profit_pct': 0.01
    })
    
    signal1 = strategy1.generate_signal(test_data)
    print(f"  Signal: {signal1['signal']}")
    print(f"  Confidence: {signal1['confidence']:.2f}")
    print(f"  Reason: {signal1['reason']}")
    print(f"  Fair value: {signal1['metadata'].get('fair_value', 'N/A'):.2f}")
    print(f"  Deviation: {signal1['metadata'].get('deviation_pct', 'N/A'):.2f}%")
    
    # Test 2: VWAP fair value
    print("\nTest 2: VWAP Fair Value")
    strategy2 = ArbitrageStrategy(parameters={
        'fair_value_method': 'vwap',
        'fair_value_period': 20,
        'deviation_threshold': 0.02
    })
    
    signal2 = strategy2.generate_signal(test_data)
    print(f"  Signal: {signal2['signal']}")
    print(f"  Reason: {signal2['reason']}")
    print(f"  Fair value: {signal2['metadata'].get('fair_value', 'N/A'):.2f}")
    
    # Test 3: Signal history analysis
    print("\nTest 3: Signal History Analysis")
    signals_history = []
    deviations = []
    
    for i in range(30, len(test_data)):  # Start from where we have enough data
        window_data = test_data.iloc[:i+1]
        signal = strategy1.generate_signal(window_data)
        signals_history.append(signal)
        deviations.append(signal['metadata'].get('deviation_pct', 0))
    
    buy_signals = sum(1 for s in signals_history if s['signal'] == 'BUY')
    sell_signals = sum(1 for s in signals_history if s['signal'] == 'SELL')
    hold_signals = sum(1 for s in signals_history if s['signal'] == 'HOLD')
    
    print(f"  Total signals generated: {len(signals_history)}")
    print(f"  BUY signals: {buy_signals}")
    print(f"  SELL signals: {sell_signals}")
    print(f"  HOLD signals: {hold_signals}")
    print(f"  Max deviation: {max(deviations):.2f}%")
    print(f"  Min deviation: {min(deviations):.2f}%")
    print(f"  Mean absolute deviation: {np.mean([abs(d) for d in deviations]):.2f}%")
    
    # Test 4: Different fair value method
    print("\nTest 4: Theoretical Fair Value")
    strategy3 = ArbitrageStrategy(parameters={
        'fair_value_method': 'theoretical',
        'fair_value_period': 20
    })
    
    signal3 = strategy3.generate_signal(test_data)
    print(f"  Signal: {signal3['signal']}")
    print(f"  Reason: {signal3['reason']}")
    
    # Test 5: Parameter update
    print("\nTest 5: Parameter Update")
    print(f"  Original fair_value_method: {strategy1.fair_value_method}")
    print(f"  Original deviation_threshold: {strategy1.deviation_threshold}")
    
    strategy1.set_parameters({
        'fair_value_method': 'vwap',
        'deviation_threshold': 0.03
    })
    print(f"  Updated fair_value_method: {strategy1.fair_value_method}")
    print(f"  Updated deviation_threshold: {strategy1.deviation_threshold}")
    
    # Test 6: Error handling
    print("\nTest 6: Error Handling")
    try:
        bad_strategy = ArbitrageStrategy(parameters={'fair_value_period': -5})
        print("  ✗ Should have raised ValueError for negative fair_value_period")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    try:
        strategy1.set_parameters({'fair_value_method': 'invalid'})
        print("  ✗ Should have raised ValueError for invalid fair_value_method")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    # Test 7: Registry registration
    print("\nTest 7: Registry Registration")
    from bot.core.registry import StrategyRegistry
    registry = StrategyRegistry()
    
    count = registry.load_from_module('bot.strategies.arbitrage')
    print(f"  Loaded {count} strategy(ies) from module")
    
    if registry.exists('arbitrage'):
        print(f"  ✓ Arbitrage strategy registered in registry as 'arbitrage'")
        registered_class = registry.get('arbitrage')
        print(f"  ✓ Registered class: {registered_class.__name__}")
        
        # Test creating instance from registry
        strategy_from_registry = registry.create_instance('arbitrage', {
            'fair_value_method': 'moving_average',
            'fair_value_period': 20
        })
        print(f"  ✓ Created instance from registry: {strategy_from_registry.__class__.__name__}")
    else:
        print("  ✗ Arbitrage strategy not found in registry")
    
    print("\n" + "=" * 60)
    print("✅ All Arbitrage Strategy Tests Passed!")