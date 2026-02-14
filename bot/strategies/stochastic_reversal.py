"""Stochastic Reversal strategy."""

from bot.core.interfaces import Strategy


class StochasticReversalStrategy(Strategy):
    """Strategy using Stochastic oscillator for reversal signals."""
    
    STRATEGY_NAME = "stochastic_reversal"
    
    def __init__(self):
        super().__init__()
        self.required_indicators = ['stochastic']
    
    def generate_signal(self, data, indicators):
        """Generate signal based on Stochastic reversal."""
        if len(data) < 15:
            return self.create_signal('HOLD', 0, 'Insufficient data')
        
        stoch_k = indicators.get('stoch_k').iloc[-1] if 'stoch_k' in indicators else None
        stoch_d = indicators.get('stoch_d').iloc[-1] if 'stoch_d' in indicators else None
        prev_k = indicators.get('stoch_k').iloc[-2] if 'stoch_k' in indicators else None
        prev_d = indicators.get('stoch_d').iloc[-2] if 'stoch_d' in indicators else None
        
        if not all([stoch_k, stoch_d, prev_k, prev_d]):
            return self.create_signal('HOLD', 0, 'Stochastic indicators not available')
        
        # Oversold reversal
        if stoch_k < 20 and stoch_d < 20:
            if prev_k <= prev_d and stoch_k > stoch_d:
                return self.create_signal('BUY', 75, 
                    'Stochastic oversold reversal - bullish crossover')
        
        # Overbought reversal
        if stoch_k > 80 and stoch_d > 80:
            if prev_k >= prev_d and stoch_k < stoch_d:
                return self.create_signal('SELL', 75,
                    'Stochastic overbought reversal - bearish crossover')
        
        return self.create_signal('HOLD', 50, 'Stochastic showing no reversal')