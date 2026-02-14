"""Ichimoku Bias strategy."""

from bot.core.interfaces import Strategy


class IchimokuBiasStrategy(Strategy):
    """Strategy using Ichimoku Cloud for trend bias."""
    
    STRATEGY_NAME = "ichimoku_bias"
    
    def __init__(self):
        super().__init__()
        self.required_indicators = ['ichimoku']
    
    def generate_signal(self, data, indicators):
        """Generate signal based on Ichimoku Cloud bias."""
        if len(data) < 30:
            return self.create_signal('HOLD', 0, 'Insufficient data')
        
        tenkan = indicators.get('ichimoku_tenkan').iloc[-1] if 'ichimoku_tenkan' in indicators else None
        kijun = indicators.get('ichimoku_kijun').iloc[-1] if 'ichimoku_kijun' in indicators else None
        senkou_a = indicators.get('ichimoku_senkou_a').iloc[-1] if 'ichimoku_senkou_a' in indicators else None
        senkou_b = indicators.get('ichimoku_senkou_b').iloc[-1] if 'ichimoku_senkou_b' in indicators else None
        
        if not all([tenkan, kijun, senkou_a, senkou_b]):
            return self.create_signal('HOLD', 0, 'Ichimoku indicators not available')
        
        close = data['close'].iloc[-1]
        
        # Cloud top and bottom
        cloud_top = max(senkou_a, senkou_b)
        cloud_bottom = min(senkou_a, senkou_b)
        
        # Bullish bias
        if close > cloud_top and tenkan > kijun:
            score = 70 + ((tenkan - kijun) / kijun) * 1000
            return self.create_signal('BUY', min(95, score), 
                'Bullish Ichimoku: above cloud, TK bullish')
        
        # Bearish bias
        if close < cloud_bottom and tenkan < kijun:
            score = 70 + ((kijun - tenkan) / kijun) * 1000
            return self.create_signal('SELL', min(95, score),
                'Bearish Ichimoku: below cloud, TK bearish')
        
        return self.create_signal('HOLD', 50, 'Ichimoku cloud neutral')