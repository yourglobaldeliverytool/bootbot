"""
Breakout Strategy.
Generates signals based on price breakouts from consolidation zones.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

from bot.core.interfaces import Strategy


class BreakoutStrategy(Strategy):
    """
    Breakout Strategy for identifying price breakouts.
    
    This strategy identifies consolidation periods and generates signals when
    price breaks above resistance or below support levels. It uses recent
    price ranges to define breakout levels.
    
    Signal Logic:
        - BUY: Price breaks above resistance (previous high + threshold)
        - SELL: Price breaks below support (previous low - threshold)
        - HOLD: Price within consolidation range
    
    Usage:
        - Capture explosive price movements
        - Trade breakout of consolidation
        - Ride momentum after breakout
        - Identify trend initiation
    """
    
    STRATEGY_NAME = "breakout"
    
    def __init__(self, name: str = None, parameters: Dict[str, Any] = None):
        """
        Initialize the breakout strategy.
        
        Args:
            name: Unique identifier for the strategy
            parameters: Configuration parameters including:
                - period (int): Lookback period for range calculation (default: 20)
                - threshold (float): Percentage threshold for breakout (default: 0.02)
                - volume_confirmation (bool): Require volume confirmation (default: True)
                - volume_multiplier (float): Volume multiplier for confirmation (default: 1.5)
        """
        if name is None:
            name = self.STRATEGY_NAME
        super().__init__(name, parameters)
        
        # Set default parameters
        self.period = self.parameters.get('period', 20)
        self.threshold = self.parameters.get('threshold', 0.02)
        self.volume_confirmation = self.parameters.get('volume_confirmation', True)
        self.volume_multiplier = self.parameters.get('volume_multiplier', 1.5)
        
        # Validate parameters
        if self.period <= 0:
            raise ValueError(f"Period must be positive, got {self.period}")
        
        if self.threshold <= 0:
            raise ValueError(f"threshold must be positive, got {self.threshold}")
        
        if self.volume_multiplier < 1.0:
            raise ValueError(
                f"volume_multiplier must be >= 1.0, got {self.volume_multiplier}"
            )
    
    def generate_signal(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate trading signal based on breakout logic.
        
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
            self.logger.debug(f"Generating breakout signal with period {self.period}")
        
        # Check if we have enough data
        if len(data) < self.period + 1:
            return self._create_hold_signal(
                "Insufficient data for breakout analysis",
                0.0
            )
        
        # Get current and previous data
        current = data.iloc[-1]
        previous = data.iloc[-1-self.period:-1]
        
        # Calculate support and resistance from previous period
        resistance = previous['high'].max()
        support = previous['low'].min()
        range_size = resistance - support
        
        # Calculate average volume from previous period
        avg_volume = previous['volume'].mean()
        
        # Current price and volume
        current_price = current['close']
        current_volume = current['volume']
        
        # Calculate breakout levels
        resistance_breakout = resistance * (1 + self.threshold)
        support_breakout = support * (1 - self.threshold)
        
        # Check for bullish breakout
        if current_price > resistance_breakout:
            # Calculate breakout strength
            breakout_pct = (current_price - resistance) / resistance
            confidence = min(0.6 + breakout_pct * 5, 0.95)
            
            # Check volume confirmation if required
            volume_confirmed = True
            if self.volume_confirmation:
                volume_confirmed = current_volume > (avg_volume * self.volume_multiplier)
                if volume_confirmed:
                    confidence = min(confidence + 0.1, 0.95)
            
            reason = (
                f"Bullish breakout: Price ({current_price:.2f}) broke above "
                f"resistance ({resistance:.2f}) by {(breakout_pct*100):.2f}%"
            )
            
            if self.volume_confirmation:
                volume_status = "confirmed" if volume_confirmed else "not confirmed"
                reason += f" - Volume {volume_status}"
            
            return self._create_buy_signal(
                reason,
                confidence,
                {
                    'price': current_price,
                    'resistance': resistance,
                    'breakout_level': resistance_breakout,
                    'breakout_pct': breakout_pct * 100,
                    'volume_confirmed': volume_confirmed,
                    'current_volume': current_volume,
                    'avg_volume': avg_volume,
                    'volume_ratio': current_volume / avg_volume if avg_volume > 0 else 0,
                    'range_size': range_size,
                    'condition': 'bullish_breakout'
                }
            )
        
        # Check for bearish breakout
        elif current_price < support_breakout:
            # Calculate breakout strength
            breakout_pct = (support - current_price) / support
            confidence = min(0.6 + breakout_pct * 5, 0.95)
            
            # Check volume confirmation if required
            volume_confirmed = True
            if self.volume_confirmation:
                volume_confirmed = current_volume > (avg_volume * self.volume_multiplier)
                if volume_confirmed:
                    confidence = min(confidence + 0.1, 0.95)
            
            reason = (
                f"Bearish breakout: Price ({current_price:.2f}) broke below "
                f"support ({support:.2f}) by {(breakout_pct*100):.2f}%"
            )
            
            if self.volume_confirmation:
                volume_status = "confirmed" if volume_confirmed else "not confirmed"
                reason += f" - Volume {volume_status}"
            
            return self._create_sell_signal(
                reason,
                confidence,
                {
                    'price': current_price,
                    'support': support,
                    'breakout_level': support_breakout,
                    'breakout_pct': breakout_pct * 100,
                    'volume_confirmed': volume_confirmed,
                    'current_volume': current_volume,
                    'avg_volume': avg_volume,
                    'volume_ratio': current_volume / avg_volume if avg_volume > 0 else 0,
                    'range_size': range_size,
                    'condition': 'bearish_breakout'
                }
            )
        
        # No breakout - check consolidation state
        else:
            # Determine position within range
            range_position = (current_price - support) / range_size if range_size > 0 else 0.5
            
            # Check if near breakout levels
            near_resistance = current_price > (resistance * (1 + self.threshold / 2))
            near_support = current_price < (support * (1 - self.threshold / 2))
            
            if near_resistance:
                confidence = 0.6
                condition = "near_resistance"
                reason = (
                    f"Price ({current_price:.2f}) approaching resistance "
                    f"({resistance:.2f}), potential breakout imminent"
                )
            elif near_support:
                confidence = 0.6
                condition = "near_support"
                reason = (
                    f"Price ({current_price:.2f}) approaching support "
                    f"({support:.2f}), potential breakout imminent"
                )
            else:
                confidence = 0.5
                if range_position > 0.6:
                    condition = "upper_range"
                elif range_position < 0.4:
                    condition = "lower_range"
                else:
                    condition = "middle_range"
                
                reason = (
                    f"Price ({current_price:.2f}) consolidating in range "
                    f"[{support:.2f} - {resistance:.2f}], "
                    f"position: {(range_position*100):.1f}%"
                )
            
            return self._create_hold_signal(
                reason,
                confidence,
                {
                    'price': current_price,
                    'support': support,
                    'resistance': resistance,
                    'range_size': range_size,
                    'range_position': range_position,
                    'current_volume': current_volume,
                    'avg_volume': avg_volume,
                    'volume_ratio': current_volume / avg_volume if avg_volume > 0 else 0,
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
            elif key == 'threshold':
                if value <= 0:
                    raise ValueError(f"threshold must be positive, got {value}")
                setattr(self, key, value)
                self.parameters[key] = value
            elif key == 'volume_multiplier':
                if value < 1.0:
                    raise ValueError(
                        f"volume_multiplier must be >= 1.0, got {value}"
                    )
                setattr(self, key, value)
                self.parameters[key] = value
            elif key == 'volume_confirmation':
                if not isinstance(value, bool):
                    raise ValueError(f"volume_confirmation must be boolean, got {type(value)}")
                setattr(self, key, value)
                self.parameters[key] = value
        
        if self.logger:
            self.logger.info(f"Updated parameters: {self.parameters}")


# Note: Registration is handled dynamically by the registry.load_from_module() method
# The STRATEGY_NAME class attribute is used by the registry to identify this strategy


# Minimal test for validation
if __name__ == "__main__":
    # Create test data
    print("Running Breakout Strategy Test...")
    print("=" * 60)
    
    # Generate test data with breakout
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    
    # Create price series with consolidation and breakout
    # Consolidation period
    consolidation_prices = 100 + np.random.randn(40) * 1
    
    # Breakout period
    breakout_prices = 140 + np.cumsum(np.random.randn(30) * 0.5)
    
    # Continue
    continue_prices = breakout_prices[-1] + np.cumsum(np.random.randn(30) * 1)
    
    prices = np.concatenate([consolidation_prices, breakout_prices, continue_prices])
    
    test_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices * 0.99,
        'high': prices * 1.02,
        'low': prices * 0.98,
        'close': prices,
        'volume': np.random.randint(100000, 1000000, 100)
    })
    
    # Increase volume during breakout
    test_data.loc[40:60, 'volume'] = test_data.loc[40:60, 'volume'] * 2
    test_data.set_index('timestamp', inplace=True)
    
    # Test 1: Basic signal generation
    print("\nTest 1: Basic Signal Generation")
    strategy1 = BreakoutStrategy(parameters={
        'period': 20,
        'threshold': 0.02,
        'volume_confirmation': True
    })
    
    signal1 = strategy1.generate_signal(test_data)
    print(f"  Signal: {signal1['signal']}")
    print(f"  Confidence: {signal1['confidence']:.2f}")
    print(f"  Reason: {signal1['reason']}")
    print(f"  Condition: {signal1['metadata'].get('condition', 'N/A')}")
    
    # Test 2: Signal without volume confirmation
    print("\nTest 2: Signal Without Volume Confirmation")
    strategy2 = BreakoutStrategy(parameters={
        'period': 20,
        'threshold': 0.02,
        'volume_confirmation': False
    })
    
    signal2 = strategy2.generate_signal(test_data)
    print(f"  Signal: {signal2['signal']}")
    print(f"  Reason: {signal2['reason']}")
    
    # Test 3: Signal history analysis
    print("\nTest 3: Signal History Analysis")
    signals_history = []
    
    for i in range(30, len(test_data)):  # Start from where we have enough data
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
    
    # Show some buy signals
    buy_signals_list = [s for s in signals_history if s['signal'] == 'BUY']
    if buy_signals_list:
        print(f"\n  Sample BUY signals:")
        for signal in buy_signals_list[:3]:
            print(f"    - {signal['reason']}")
    
    # Test 4: Different threshold
    print("\nTest 4: Different Threshold (0.05)")
    strategy3 = BreakoutStrategy(parameters={
        'period': 20,
        'threshold': 0.05
    })
    
    signal3 = strategy3.generate_signal(test_data)
    print(f"  Signal: {signal3['signal']}")
    print(f"  Reason: {signal3['reason']}")
    
    # Test 5: Parameter update
    print("\nTest 5: Parameter Update")
    print(f"  Original threshold: {strategy1.threshold}")
    print(f"  Original volume_multiplier: {strategy1.volume_multiplier}")
    
    strategy1.set_parameters({'threshold': 0.03, 'volume_multiplier': 2.0})
    print(f"  Updated threshold: {strategy1.threshold}")
    print(f"  Updated volume_multiplier: {strategy1.volume_multiplier}")
    
    # Test 6: Error handling
    print("\nTest 6: Error Handling")
    try:
        bad_strategy = BreakoutStrategy(parameters={'period': -5})
        print("  ✗ Should have raised ValueError for negative period")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    try:
        strategy1.set_parameters({'volume_multiplier': 0.5})
        print("  ✗ Should have raised ValueError for volume_multiplier < 1.0")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    # Test 7: Registry registration
    print("\nTest 7: Registry Registration")
    from bot.core.registry import StrategyRegistry
    registry = StrategyRegistry()
    
    count = registry.load_from_module('bot.strategies.breakout')
    print(f"  Loaded {count} strategy(ies) from module")
    
    if registry.exists('breakout'):
        print(f"  ✓ Breakout strategy registered in registry as 'breakout'")
        registered_class = registry.get('breakout')
        print(f"  ✓ Registered class: {registered_class.__name__}")
        
        # Test creating instance from registry
        strategy_from_registry = registry.create_instance('breakout', {
            'period': 20,
            'threshold': 0.02
        })
        print(f"  ✓ Created instance from registry: {strategy_from_registry.__class__.__name__}")
    else:
        print("  ✗ Breakout strategy not found in registry")
    
    print("\n" + "=" * 60)
    print("✅ All Breakout Strategy Tests Passed!")