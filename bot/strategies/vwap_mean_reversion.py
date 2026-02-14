"""VWAP Mean Reversion strategy."""

from bot.core.interfaces import Strategy


class VWAPMeanReversionStrategy(Strategy):
    """Mean reversion strategy using VWAP as equilibrium point."""
    
    STRATEGY_NAME = "vwap_mean_reversion"
    
    def __init__(self, std_threshold: float = 1.5):
        super().__init__()
        self.std_threshold = std_threshold
        self.required_indicators = ['vwap']
    
    def generate_signal(self, data, indicators):
        """Generate mean reversion signal around VWAP."""
        if len(data) < 20:
            return self.create_signal('HOLD', 0, 'Insufficient data')
        
        vwap = indicators.get('vwap').iloc[-1] if 'vwap' in indicators else None
        if vwap is None:
            return self.create_signal('HOLD', 0, 'VWAP not available')
        
        close = data['close'].iloc[-1]
        
        # Calculate deviation from VWAP
        deviation = (close - vwap) / vwap
        
        # Buy if significantly below VWAP
        if deviation < -0.005:  # 0.5% below VWAP
            score = 60 + min(40, abs(deviation) * 5000)
            return self.create_signal('BUY', score, 
                f'Price {deviation*100:.2f}% below VWAP, mean reversion expected')
        
        # Sell if significantly above VWAP
        if deviation > 0.005:  # 0.5% above VWAP
            score = 60 + min(40, deviation * 5000)
            return self.create_signal('SELL', score,
                f'Price {deviation*100:.2f}% above VWAP, mean reversion expected')
        
        return self.create_signal('HOLD', 50, 'Price near VWAP')