"""EMA Trend Stack strategy."""

from bot.core.interfaces import Strategy


class EMATrendStackStrategy(Strategy):
    """Strategy using multiple EMA periods for trend confirmation."""
    
    STRATEGY_NAME = "ema_trend_stack"
    
    def __init__(self, fast_ema: int = 9, mid_ema: int = 21, slow_ema: int = 55):
        super().__init__()
        self.fast_ema = fast_ema
        self.mid_ema = mid_ema
        self.slow_ema = slow_ema
        self.required_indicators = ['ema']
    
    def generate_signal(self, data, indicators):
        """Generate signal based on EMA stack alignment."""
        if len(data) < self.slow_ema:
            return self.create_signal('HOLD', 0, 'Insufficient data')
        
        # Get EMA values
        ema_fast = indicators.get(f'ema_{self.fast_ema}').iloc[-1] if f'ema_{self.fast_ema}' in indicators else None
        ema_mid = indicators.get(f'ema_{self.mid_ema}').iloc[-1] if f'ema_{self.mid_ema}' in indicators else None
        ema_slow = indicators.get(f'ema_{self.slow_ema}').iloc[-1] if f'ema_{self.slow_ema}' in indicators else None
        
        if not all([ema_fast, ema_mid, ema_slow]):
            return self.create_signal('HOLD', 0, 'Missing EMA indicators')
        
        close = data['close'].iloc[-1]
        
        # Bullish stack: fast > mid > slow
        if ema_fast > ema_mid > ema_slow:
            if close > ema_fast:
                score = 75 + min(25, (close - ema_slow) / ema_slow * 1000)
                return self.create_signal('BUY', score, 
                    f'Bullish EMA stack: {self.fast_ema} > {self.mid_ema} > {self.slow_ema}')
        
        # Bearish stack: fast < mid < slow
        if ema_fast < ema_mid < ema_slow:
            if close < ema_fast:
                score = 75 + min(25, (ema_slow - close) / ema_slow * 1000)
                return self.create_signal('SELL', score,
                    f'Bearish EMA stack: {self.fast_ema} < {self.mid_ema} < {self.slow_ema}')
        
        return self.create_signal('HOLD', 50, 'EMA stack not aligned')