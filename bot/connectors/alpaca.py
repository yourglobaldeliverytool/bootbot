"""
Alpaca connector for crypto and stock trading.
Supports BTC, ETH and major stocks.
"""

import requests
import time
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

import pandas as pd

from bot.connectors.base import BaseDataConnector


class AlpacaConnector(BaseDataConnector):
    """
    Alpaca Data API connector.
    Provides live market data for crypto and stocks.
    """
    
    CONNECTOR_NAME = "alpaca"
    
    # Alpaca API endpoints
    BASE_URL = "https://data.alpaca.markets/v2"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Get API credentials from environment or config
        from bot.utils.env_loader import get_env_loader
        env_loader = get_env_loader()
        
        self.api_key = env_loader.get_alpaca_credentials()[0] or self.config.get('alpaca', {}).get('api_key')
        self.api_secret = env_loader.get_alpaca_credentials()[1] or self.config.get('alpaca', {}).get('api_secret')
        
        # Headers for authentication
        self.headers = {}
        if self.api_key and self.api_secret:
            self.headers = {
                'APCA-API-KEY-ID': self.api_key,
                'APCA-API-SECRET-KEY': self.api_secret
            }
        
        # Rate limiting settings
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 10 requests per second max
        self.retry_count = 3
        self.retry_delay = 1.0
        
        # Symbol mapping (Binance to Alpaca)
        self.symbol_map = {
            'BTCUSDT': 'BTC/USD',
            'ETHUSDT': 'ETH/USD',
            'XAUUSD': None,  # Alpaca doesn't support gold directly
        }
    
    def _validate_credentials(self) -> bool:
        """
        Validate Alpaca API credentials.
        For public data, credentials are optional.
        """
        try:
            # Try a simple request to check connectivity
            response = requests.get(
                f"{self.BASE_URL}/stocks/AAPL/snapshot",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code in [200, 401]:
                # 200 = success, 401 = connected but invalid credentials (can still use public data)
                if response.status_code == 200:
                    self.logger.info(f"{self.CONNECTOR_NAME} credentials validated successfully")
                else:
                    self.logger.info(f"{self.CONNECTOR_NAME} using public data mode")
                self.is_connected = True
                return True
            else:
                self.logger.warning(f"{self.CONNECTOR_NAME} connection test failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"{self.CONNECTOR_NAME} validation error: {e}")
            return False
    
    def _get_alpaca_symbol(self, binance_symbol: str) -> Optional[str]:
        """
        Convert Binance symbol to Alpaca symbol.
        
        Args:
            binance_symbol: Binance trading pair
            
        Returns:
            Alpaca symbol or None if not supported
        """
        return self.symbol_map.get(binance_symbol)
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make authenticated request to Alpaca API with retry logic.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            Response JSON or None on failure
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        for attempt in range(self.retry_count):
            try:
                # Rate limiting
                current_time = time.time()
                time_since_last_request = current_time - self.last_request_time
                if time_since_last_request < self.min_request_interval:
                    time.sleep(self.min_request_interval - time_since_last_request)
                
                self.last_request_time = time.time()
                
                self.logger.debug(f"Fetching from {self.CONNECTOR_NAME}: {endpoint}")
                
                response = requests.get(
                    url,
                    headers=self.headers,
                    params=params,
                    timeout=10
                )
                
                # Log the API call
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
                elif response.status_code in [451, 500, 502, 503, 504]:
                    self.logger.warning(f"{self.CONNECTOR_NAME} server error: {response.status_code}")
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
        """
        Fetch current price from Alpaca.
        
        Args:
            symbol: Trading pair
            
        Returns:
            Current price or None
        """
        alpaca_symbol = self._get_alpaca_symbol(symbol)
        if not alpaca_symbol:
            self.logger.debug(f"{self.CONNECTOR_NAME} does not support {symbol}")
            return None
        
        # Get latest trade
        endpoint = f"/stocks/{alpaca_symbol}/trades/latest"
        data = self._make_request(endpoint)
        
        if data and 'trade' in data:
            price = data['trade']['p']
            self.logger.info(f"{self.CONNECTOR_NAME} price for {symbol}: ${price:.2f}")
            return price
        
        # Fallback to snapshot
        endpoint = f"/stocks/{alpaca_symbol}/snapshot"
        data = self._make_request(endpoint)
        
        if data and 'latestTrade' in data:
            price = data['latestTrade']['p']
            self.logger.info(f"{self.CONNECTOR_NAME} price for {symbol}: ${price:.2f}")
            return price
        
        return None
    
    def fetch_bars(
        self,
        symbol: str,
        timeframe: str,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch OHLCV bars from Alpaca.
        
        Args:
            symbol: Trading pair
            timeframe: Kline interval (1m, 5m, 15m, 1h, 1d)
            limit: Number of bars
            
        Returns:
            DataFrame with OHLCV data
        """
        alpaca_symbol = self._get_alpaca_symbol(symbol)
        if not alpaca_symbol:
            return pd.DataFrame()
        
        # Convert timeframe to Alpaca format
        timeframe_map = {
            '1m': '1Min',
            '5m': '5Min',
            '15m': '15Min',
            '30m': '30Min',
            '1h': '1Hour',
            '4h': '4Hour',
            '1d': '1Day',
        }
        
        alpaca_timeframe = timeframe_map.get(timeframe, '1Min')
        bars_limit = limit or 100
        
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=bars_limit)
        
        params = {
            'start': start_time.isoformat(),
            'end': end_time.isoformat(),
            'timeframe': alpaca_timeframe,
            'limit': min(bars_limit, 10000)  # Alpaca max is 10000
        }
        
        endpoint = f"/stocks/{alpaca_symbol}/bars"
        data = self._make_request(endpoint, params)
        
        if data and 'bars' in data:
            bars = data['bars']
            if len(bars) > 0:
                df = pd.DataFrame(bars)
                df['t'] = pd.to_datetime(df['t'])
                df = df.rename(columns={
                    't': 'timestamp',
                    'o': 'open',
                    'h': 'high',
                    'l': 'low',
                    'c': 'close',
                    'v': 'volume'
                })
                df = df.set_index('timestamp')
                df = df[['open', 'high', 'low', 'close', 'volume']]
                
                self.logger.info(f"{self.CONNECTOR_NAME} fetched {len(df)} bars for {symbol}")
                return df
        
        self.logger.warning(f"{self.CONNECTOR_NAME} no bars found for {symbol}")
        return pd.DataFrame()
    
    def get_status(self) -> Dict[str, Any]:
        """Get connector status."""
        return {
            'connector': self.CONNECTOR_NAME,
            'is_connected': self.is_connected,
            'has_credentials': bool(self.api_key and self.api_secret),
            'request_count': self.request_count,
            'error_count': self.error_count,
            'last_request_time': datetime.fromtimestamp(self.last_request_time).isoformat() if self.last_request_time else None,
            'supported_symbols': list(self.symbol_map.keys()),
        }