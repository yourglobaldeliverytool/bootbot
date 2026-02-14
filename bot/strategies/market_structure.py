"""Market Structure Shift (MSH) strategy."""

from bot.core.interfaces import Strategy


class MarketStructureShiftStrategy(Strategy):
    """Strategy detecting changes in market structure (HH/LL, LH/HL)."""
    
    STRATEGY_NAME = "market_structure"
    
    def __init__(self, lookback: int = 10):
        super().__init__()
        self.lookback = lookback
        self.required_indicators = []
    
    def generate_signal(self, data, indicators):
        """Generate signal based on market structure changes."""
        if len(data) < self.lookback * 2:
            return self.create_signal('HOLD', 0, 'Insufficient data')
        
        # Find recent highs and lows
        recent = data.tail(self.lookback)
        prev = data.tail(self.lookback * 2).head(self.lookback)
        
        current_high = recent['high'].max()
        current_low = recent['low'].min()
        prev_high = prev['high'].max()
        prev_low = prev['low'].min()
        
        # Bullish structure shift: Higher High and Higher Low
        if current_high > prev_high and current_low > prev_low:
            return self.create_signal('BUY', 70, 
                'Bullish structure shift: HH and HL')
        
        # Bearish structure shift: Lower High and Lower Low
        if current_high < prev_high and current_low < prev_low:
            return self.create_signal('SELL', 70,
                'Bearish structure shift: LH and LL')
        
        return self.create_signal('HOLD', 50, 'Market structure unchanged')