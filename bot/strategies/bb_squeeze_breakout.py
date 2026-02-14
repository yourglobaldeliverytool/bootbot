"""Bollinger Band Squeeze/Breakout strategy."""

from bot.core.interfaces import Strategy


class BBSqueezeBreakoutStrategy(Strategy):
    """Strategy detecting Bollinger Band squeezes and breakouts."""
    
    STRATEGY_NAME = "bb_squeeze_breakout"
    
    def __init__(self, squeeze_threshold: float = 0.02):
        super().__init__()
        self.squeeze_threshold = squeeze_threshold
        self.required_indicators = ['bollinger_bands']
    
    def generate_signal(self, data, indicators):
        """Generate signal based on BB squeeze and breakout."""
        if len(data) < 25:
            return self.create_signal('HOLD', 0, 'Insufficient data')
        
        # Get BB data
        period = 20
        upper = indicators.get(f'bb_upper_{period}').iloc[-1] if f'bb_upper_{period}' in indicators else None
        lower = indicators.get(f'bb_lower_{period}').iloc[-1] if f'bb_lower_{period}' in indicators else None
        bandwidth = indicators.get(f'bb_bandwidth_{period}').iloc[-1] if f'bb_bandwidth_{period}' in indicators else None
        
        if not all([upper, lower, bandwidth]):
            return self.create_signal('HOLD', 0, 'BB indicators not available')
        
        close = data['close'].iloc[-1]
        
        # Check for squeeze
        if bandwidth < self.squeeze_threshold:
            # Squeeze detected, wait for breakout
            if close > upper:
                return self.create_signal('BUY', 80, 'BB breakout after squeeze')
            if close < lower:
                return self.create_signal('SELL', 80, 'BB breakdown after squeeze')
            return self.create_signal('HOLD', 60, 'BB squeeze detected, awaiting breakout')
        
        # Regular BB signals
        if close > upper:
            return self.create_signal('SELL', 60, 'Price above BB upper band')
        if close < lower:
            return self.create_signal('BUY', 60, 'Price below BB lower band')
        
        return self.create_signal('HOLD', 50, 'Price within BB bands')