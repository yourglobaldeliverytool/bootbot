"""
Mock live connector for testing in sandbox environments.
Simulates real market data when APIs are rate-limited.
"""

import pandas as pd
import numpy as np
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from bot.connectors.base import BaseDataConnector


class MockLiveConnector(BaseDataConnector):
    """Mock live connector that simulates real market data for testing."""
    
    CONNECTOR_NAME = "mock_live"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        np.random.seed(int(datetime.now().timestamp()))
        
        # Base prices for common pairs
        self.base_prices = {
            'BTCUSDT': 65000.0,
            'ETHUSDT': 3500.0,
            'BNBUSDT': 600.0,
        }
        
    def _validate_credentials(self) -> bool:
        """Mock validation - always succeeds."""
        self.logger.info("Mock live connector initialized (for testing)")
        return True
    
    def fetch_current_price(self, symbol: str) -> Optional[float]:
        """Fetch simulated current price."""
        try:
            base_price = self.base_prices.get(symbol, 100.0)
            
            # Add some realistic volatility (±0.5%)
            volatility = np.random.uniform(-0.005, 0.005)
            price = base_price * (1 + volatility)
            
            self.request_count += 1
            return price
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Error fetching mock price: {e}")
            return None
    
    def fetch_bars(
        self,
        symbol: str,
        timeframe: str,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """Fetch simulated historical bars."""
        try:
            limit = limit or 100
            limit = min(limit, 1000)
            
            base_price = self.base_prices.get(symbol, 100.0)
            
            # Generate realistic price movements
            returns = np.random.normal(0, 0.01, limit)
            prices = base_price * np.cumprod(1 + returns)
            
            # Create OHLCV data
            data = []
            for i in range(limit):
                open_price = prices[i]
                high_low_range = open_price * 0.01
                
                data.append({
                    'timestamp': datetime.now() - timedelta(hours=limit-i),
                    'open': open_price,
                    'high': open_price + np.random.uniform(0, high_low_range),
                    'low': open_price - np.random.uniform(0, high_low_range),
                    'close': prices[i] if i < len(prices) - 1 else prices[i],
                    'volume': np.random.uniform(100000, 1000000),
                })
            
            df = pd.DataFrame(data)
            df.set_index('timestamp', inplace=True)
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            self.request_count += 1
            return df
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Error fetching mock bars: {e}")
            return pd.DataFrame()