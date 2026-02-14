"""
Polygon.io connector for stocks and crypto data.
High-quality market data with WebSocket support.
"""

import os
import requests
import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime

import pandas as pd

from bot.connectors.base import BaseDataConnector


class PolygonConnector(BaseDataConnector):
    """
    Polygon.io Data API connector.
    Provides high-quality real-time and historical market data.
    """
    
    CONNECTOR_NAME = "polygon"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Get API key from environment or config
        from bot.utils.env_loader import get_env_loader
        env_loader = get_env_loader()
        
        self.api_key = env_loader.get_polygon_credentials()[0] or os.environ.get('POLYGON_API_KEY') or self.config.get('polygon', {}).get('api_key')
        
        self.base_url = "https://api.polygon.io"
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.05  # 20 requests per second
        self.retry_count = 3
        self.retry_delay = 1.0
        
        # Symbol mapping (Binance to Polygon)
        self.symbol_map = {
            'BTCUSDT': 'X:BTCUSD',
            'ETHUSDT': 'X:ETHUSD',
            'XAUUSD': 'X:XAUUSD',
        }
    
    def _validate_credentials(self) -> bool:
        """Validate Polygon API credentials."""
        try:
            if not self.api_key:
                self.logger.warning(f"{self.CONNECTOR_NAME} no API key provided")
                self.is_connected = False
                return False
            
            # Try a simple request
            response = requests.get(
                f"{self.base_url}/v2/aggs/ticker/X:BTCUSD/prev",
                params={'apiKey': self.api_key},
                timeout=10
            )
            
            if response.status_code == 200:
                self.logger.info(f"{self.CONNECTOR_NAME} credentials validated successfully")
                self.is_connected = True
                return True
            elif response.status_code == 401:
                self.logger.warning(f"{self.CONNECTOR_NAME} invalid API key")
                return False
            else:
                self.logger.warning(f"{self.CONNECTOR_NAME} connection test failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"{self.CONNECTOR_NAME} validation error: {e}")
            return False
    
    def _get_polygon_symbol(self, binance_symbol: str) -> Optional[str]:
        """Convert Binance symbol to Polygon symbol."""
        return self.symbol_map.get(binance_symbol)
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make authenticated request with retry logic."""
        url = f"{self.base_url}{endpoint}"
        
        if params is None:
            params = {}
        
        params['apiKey'] = self.api_key
        
        for attempt in range(self.retry_count):
            try:
                # Rate limiting
                current_time = time.time()
                time_since_last_request = current_time - self.last_request_time
                if time_since_last_request < self.min_request_interval:
                    time.sleep(self.min_request_interval - time_since_last_request)
                
                self.last_request_time = time.time()
                
                self.logger.debug(f"Fetching from {self.CONNECTOR_NAME}: {endpoint}")
                
                response = requests.get(url, params=params, timeout=10)
                
                self.logger.info(
                    f"{self.CONNECTOR_NAME} API call: {endpoint} "
                    f"Status: {response.status_code} "
                    f"Timestamp: {datetime.utcnow().isoformat()}"
                )
                
                if response.status_code == 200:
                    self.request_count += 1
                    return response.json()
                elif response.status_code == 429:
                    self.logger.warning(f"{self.CONNECTOR_NAME} rate limited, retrying...")
                    time.sleep(self.retry_delay * (2 ** attempt))
                else:
                    self.logger.error(f"{self.CONNECTOR_NAME} request failed: {response.status_code}")
                    break
                    
            except requests.exceptions.Timeout:
                self.logger.warning(f"{self.CONNECTOR_NAME} request timeout")
                time.sleep(self.retry_delay * (2 ** attempt))
            except Exception as e:
                self.logger.error(f"{self.CONNECTOR_NAME} request error: {e}")
                break
        
        self.error_count += 1
        return None
    
    def fetch_current_price(self, symbol: str) -> Optional[float]:
        """Fetch current price from Polygon."""
        polygon_symbol = self._get_polygon_symbol(symbol)
        if not polygon_symbol:
            return None
        
        # Get latest trade
        endpoint = f"/v2/last/trade/{polygon_symbol}"
        data = self._make_request(endpoint)
        
        if data and data.get('status') == 'OK' and 'results' in data:
            price = data['results']['p']
            self.logger.info(f"{self.CONNECTOR_NAME} price for {symbol}: ${price:.2f}")
            return price
        
        # Fallback to previous close
        endpoint = f"/v2/aggs/ticker/{polygon_symbol}/prev"
        data = self._make_request(endpoint)
        
        if data and data.get('status') == 'OK' and 'results' in data:
            price = data['results'][0]['c']
            self.logger.info(f"{self.CONNECTOR_NAME} price for {symbol}: ${price:.2f}")
            return price
        
        return None
    
    def fetch_bars(self, symbol: str, timeframe: str, limit: Optional[int] = None) -> pd.DataFrame:
        """Fetch OHLCV bars from Polygon."""
        import os
        
        polygon_symbol = self._get_polygon_symbol(symbol)
        if not polygon_symbol:
            return pd.DataFrame()
        
        # Convert timeframe
        timeframe_map = {
            '1m': '1',
            '5m': '5',
            '15m': '15',
            '30m': '30',
            '1h': '60',
            '4h': '240',
            '1d': 'D',
        }
        
        polygon_timeframe = timeframe_map.get(timeframe, '60')
        bars_limit = limit or 100
        
        # Calculate time range (Polygon allows max 50000 bars)
        end_time = int(time.time() * 1000)
        
        params = {
            'adjusted': 'true',
            'sort': 'desc',
            'limit': min(bars_limit, 50000),
        }
        
        endpoint = f"/v2/aggs/ticker/{polygon_symbol}/range/1/{polygon_timeframe}/{end_time}"
        data = self._make_request(endpoint, params)
        
        if data and data.get('status') == 'OK' and 'results' in data:
            bars = data['results']
            if len(bars) > 0:
                df = pd.DataFrame(bars)
                df['timestamp'] = pd.to_datetime(df['t'], unit='ms')
                df = df.rename(columns={
                    'o': 'open',
                    'h': 'high',
                    'l': 'low',
                    'c': 'close',
                    'v': 'volume'
                })
                df = df.set_index('timestamp')
                df = df[['open', 'high', 'low', 'close', 'volume']]
                df = df.sort_index()
                
                self.logger.info(f"{self.CONNECTOR_NAME} fetched {len(df)} bars for {symbol}")
                return df
        
        return pd.DataFrame()
    
    def get_status(self) -> Dict[str, Any]:
        """Get connector status."""
        return {
            'connector': self.CONNECTOR_NAME,
            'is_connected': self.is_connected,
            'has_credentials': bool(self.api_key),
            'request_count': self.request_count,
            'error_count': self.error_count,
            'supported_symbols': list(self.symbol_map.keys()),
        }