"""Fibonacci Confluence strategy."""

from bot.core.interfaces import Strategy


class FibonacciConfluenceStrategy(Strategy):
    """Strategy using Fibonacci retracement levels for support/resistance."""
    
    STRATEGY_NAME = "fibonacci_confluence"
    
    def __init__(self):
        super().__init__()
        self.required_indicators = []
    
    def generate_signal(self, data, indicators):
        """
        Generate signal based on Fibonacci retracement levels.
        Note: Simplified stub implementation.
        """
        if len(data) < 50:
            return self.create_signal('HOLD', 0, 'Insufficient data')
        
        # Find swing high and low
        lookback = 20
        recent = data.tail(lookback)
        swing_high = recent['high'].max()
        swing_low = recent['low'].min()
        
        close = data['close'].iloc[-1]
        
        # Fibonacci levels
        fib_382 = swing_low + (swing_high - swing_low) * 0.382
        fib_500 = swing_low + (swing_high - swing_low) * 0.500
        fib_618 = swing_low + (swing_high - swing_low) * 0.618
        
        # Check if price at fib levels
        tolerance = 0.005  # 0.5%
        
        if abs(close - fib_618) / fib_618 < tolerance:
            return self.create_signal('BUY', 65, 'Price at 61.8% Fibonacci support')
        
        if abs(close - fib_382) / fib_382 < tolerance:
            return self.create_signal('SELL', 65, 'Price at 38.2% Fibonacci resistance')
        
        return self.create_signal('HOLD', 50, 'Price not at key Fibonacci levels')