"""MACD Expansion strategy."""

from bot.core.interfaces import Strategy


class MACDExpansionStrategy(Strategy):
    """Strategy based on MACD histogram expansion for momentum confirmation."""
    
    STRATEGY_NAME = "macd_expansion"
    
    def __init__(self):
        super().__init__()
        self.required_indicators = ['macd']
    
    def generate_signal(self, data, indicators):
        """Generate signal based on MACD expansion."""
        if len(data) < 30:
            return self.create_signal('HOLD', 0, 'Insufficient data')
        
        # Get MACD components
        macd_key = 'macd_12_26_9'
        macd_line = indicators.get(f'{macd_key}').iloc[-1] if f'{macd_key}' in indicators else None
        signal_line = indicators.get(f'{macd_key}_signal').iloc[-1] if f'{macd_key}_signal' in indicators else None
        histogram = indicators.get(f'{macd_key}_histogram').iloc[-1] if f'{macd_key}_histogram' in indicators else None
        prev_histogram = indicators.get(f'{macd_key}_histogram').iloc[-2] if f'{macd_key}_histogram' in indicators else None
        
        if not all([macd_line, signal_line, histogram]):
            return self.create_signal('HOLD', 0, 'MACD indicators not available')
        
        # Bullish: MACD above signal and histogram expanding
        if macd_line > signal_line and histogram > 0:
            if prev_histogram and histogram > prev_histogram:
                score = 65 + min(35, (histogram / macd_line) * 100)
                return self.create_signal('BUY', score, 
                    'MACD bullish with expanding histogram')
        
        # Bearish: MACD below signal and histogram expanding (negative)
        if macd_line < signal_line and histogram < 0:
            if prev_histogram and histogram < prev_histogram:
                score = 65 + min(35, abs(histogram / macd_line) * 100)
                return self.create_signal('SELL', score,
                    'MACD bearish with expanding histogram')
        
        # Crossover signals
        if macd_line > signal_line and prev_histogram <= 0:
            return self.create_signal('BUY', 75, 'MACD bullish crossover')
        
        if macd_line < signal_line and prev_histogram >= 0:
            return self.create_signal('SELL', 75, 'MACD bearish crossover')
        
        return self.create_signal('HOLD', 50, 'MACD showing no clear signal')