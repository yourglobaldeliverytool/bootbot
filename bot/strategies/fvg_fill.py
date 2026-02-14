"""Fair Value Gap Fill strategy."""

from bot.core.interfaces import Strategy


class FVGFillStrategy(Strategy):
    """Strategy identifying Fair Value Gaps (imbalances) and potential fills."""
    
    STRATEGY_NAME = "fvg_fill"
    
    def __init__(self):
        super().__init__()
        self.required_indicators = []
    
    def generate_signal(self, data, indicators):
        """
        Generate signal based on Fair Value Gap identification.
        Note: Simplified stub implementation.
        """
        if len(data) < 3:
            return self.create_signal('HOLD', 0, 'Insufficient data')
        
        # Look for FVG in last 3 candles
        recent = data.tail(3)
        
        # Bullish FVG: gap between candle 1 high and candle 3 low
        if recent.iloc[1]['high'] < recent.iloc[0]['low']:
            fvg_top = recent.iloc[1]['high']
            fvg_bottom = recent.iloc[0]['low']
            close = data['close'].iloc[-1]
            
            if close >= fvg_bottom and close <= fvg_top:
                return self.create_signal('BUY', 65, 'Price in bullish FVG, fill expected')
        
        # Bearish FVG: gap between candle 1 low and candle 3 high
        if recent.iloc[1]['low'] > recent.iloc[0]['high']:
            fvg_top = recent.iloc[0]['high']
            fvg_bottom = recent.iloc[1]['low']
            close = data['close'].iloc[-1]
            
            if close >= fvg_bottom and close <= fvg_top:
                return self.create_signal('SELL', 65, 'Price in bearish FVG, fill expected')
        
        return self.create_signal('HOLD', 50, 'No FVG detected')