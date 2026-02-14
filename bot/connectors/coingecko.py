"""
CoinGecko connector for live market data.
Uses public CoinGecko API (no authentication required).
"""

import requests
import pandas as pd
import logging
from typing import Optional, Dict, Any

from bot.connectors.base import BaseDataConnector


class CoinGeckoConnector(BaseDataConnector):
    """CoinGecko public API connector for market data."""
    
    CONNECTOR_NAME = "coingecko"
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.session = requests.Session()
        self.min_request_interval = 1.0  # 1 request per second (rate limit)
        
        # Symbol mapping for CoinGecko
        self.symbol_map = {
            'BTCUSDT': 'bitcoin',
            'ETHUSDT': 'ethereum',
            'BNBUSDT': 'binancecoin',
        }
    
    def _validate_credentials(self) -> bool:
        """Validate connection (no credentials needed for public API)."""
        try:
            response = self.session.get(f"{self.BASE_URL}/ping", timeout=5)
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"CoinGecko API validation failed: {e}")
            return False
    
    def fetch_current_price(self, symbol: str) -> Optional[float]:
        """
        Fetch current price for a symbol.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            
        Returns:
            Current price in USD or None if failed
        """
        try:
            self._enforce_rate_limit()
            
            coin_id = self.symbol_map.get(symbol, symbol.lower().replace('usdt', ''))
            
            response = self.session.get(
                f"{self.BASE_URL}/simple/price",
                params={
                    'ids': coin_id,
                    'vs_currencies': 'usd'
                },
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            price = data.get(coin_id, {}).get('usd')
            
            self.request_count += 1
            return price
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Failed to fetch price for {symbol}: {e}")
            return None
    
    def fetch_bars(
        self,
        symbol: str,
        timeframe: str,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data from CoinGecko.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            timeframe: Timeframe (daily only for free tier)
            limit: Number of bars (max 365 for free tier)
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            self._enforce_rate_limit()
            
            coin_id = self.symbol_map.get(symbol, symbol.lower().replace('usdt', ''))
            limit = limit or 30
            limit = min(limit, 365)  # CoinGecko free tier limit
            
            response = self.session.get(
                f"{self.BASE_URL}/coins/{coin_id}/market_chart",
                params={
                    'vs_currency': 'usd',
                    'days': limit
                },
                timeout=15
            )
            response.raise_for_status()
            
            data = response.json()
            prices = data.get('prices', [])
            
            # Convert to OHLCV format (CoinGecko only provides closing prices)
            df_data = []
            for i, price_point in enumerate(prices):
                df_data.append({
                    'timestamp': pd.to_datetime(price_point[0], unit='ms'),
                    'open': price_point[1],
                    'high': price_point[1],
                    'low': price_point[1],
                    'close': price_point[1],
                    'volume': 0  # Volume not available in free tier
                })
            
            df = pd.DataFrame(df_data)
            df.set_index('timestamp', inplace=True)
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            self.request_count += 1
            return df
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Failed to fetch bars for {symbol}: {e}")
            return pd.DataFrame()