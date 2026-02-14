"""ATR Volatility Breakout strategy."""

from bot.core.interfaces import Strategy


class ATRVolatilityBreakoutStrategy(Strategy):
    """Strategy using ATR to detect volatility-based breakouts."""
    
    STRATEGY_NAME = "atr_volatility_breakout"
    
    def __init__(self, atr_period: int = 14, multiplier: float = 2.0):
        super().__init__()
        self.atr_period = atr_period
        self.multiplier = multiplier
        self.required_indicators = ['atr']
    
    def generate_signal(self, data, indicators):
        """Generate signal based on ATR volatility breakout."""
        if len(data) < self.atr_period + 5:
            return self.create_signal('HOLD', 0, 'Insufficient data')
        
        atr = indicators.get(f'atr_{self.atr_period}').iloc[-1] if f'atr_{self.atr_period}' in indicators else None
        if atr is None:
            return self.create_signal('HOLD', 0, 'ATR not available')
        
        close = data['close'].iloc[-1]
        prev_close = data['close'].iloc[-2]
        
        # Calculate change in ATR
        atr_prev = indicators.get(f'atr_{self.atr_period}').iloc[-2] if f'atr_{self.atr_period}' in indicators else None
        
        # Volatility spike detection
        if atr_prev and atr > atr_prev * 1.2:
            # High volatility breakout
            if close > prev_close:
                score = 70 + (atr / close * 1000)
                return self.create_signal('BUY', score, 
                    f'High volatility breakout, ATR: {atr:.2f}')
            elif close < prev_close:
                score = 70 + (atr / close * 1000)
                return self.create_signal('SELL', score,
                    f'High volatility breakdown, ATR: {atr:.2f}')
        
        # Range expansion beyond ATR
        if abs(close - prev_close) > atr * self.multiplier:
            if close > prev_close:
                return self.create_signal('BUY', 75, 'Strong bullish move > 2x ATR')
            else:
                return self.create_signal('SELL', 75, 'Strong bearish move > 2x ATR')
        
        return self.create_signal('HOLD', 50, 'Normal volatility, no breakout')