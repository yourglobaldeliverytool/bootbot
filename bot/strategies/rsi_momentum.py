"""RSI Momentum Shift strategy."""

from bot.core.interfaces import Strategy


class RSIMomentumStrategy(Strategy):
    """Strategy detecting momentum shifts using RSI divergence and levels."""
    
    STRATEGY_NAME = "rsi_momentum_shift"
    
    def __init__(self, oversold: float = 30, overbought: float = 70):
        super().__init__()
        self.oversold = oversold
        self.overbought = overbought
        self.required_indicators = ['rsi']
    
    def generate_signal(self, data, indicators):
        """Generate signal based on RSI momentum shifts."""
        if len(data) < 15:
            return self.create_signal('HOLD', 0, 'Insufficient data')
        
        rsi = indicators.get('rsi').iloc[-1] if 'rsi' in indicators else None
        if rsi is None:
            return self.create_signal('HOLD', 0, 'RSI not available')
        
        # Oversold bounce
        if rsi < self.oversold:
            score = 70 + (self.oversold - rsi)
            return self.create_signal('BUY', score, 
                f'RSI oversold at {rsi:.1f}, bounce expected')
        
        # Overbought reversal
        if rsi > self.overbought:
            score = 70 + (rsi - self.overbought)
            return self.create_signal('SELL', score,
                f'RSI overbought at {rsi:.1f}, reversal expected')
        
        # Neutral zone
        if rsi > 50:
            return self.create_signal('BUY', 55, f'RSI bullish at {rsi:.1f}')
        else:
            return self.create_signal('SELL', 55, f'RSI bearish at {rsi:.1f}')