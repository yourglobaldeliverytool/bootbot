"""
Yahoo Finance connector for market data.
Provides backup price feeds for stocks, crypto, and commodities.
"""

import requests
import time
import logging
import re
from typing import Optional, Dict, Any
from datetime import datetime

import pandas as pd

from bot.connectors.base import BaseDataConnector


class YahooFinanceConnector(BaseDataConnector):
    """
    Yahoo Finance API connector.
    Provides backup market data for stocks, crypto, and commodities.
    Uses Yahoo Finance's public API endpoints.
    """
    
    CONNECTOR_NAME = "yahoo_finance"
    
    # Yahoo Finance API endpoints
    BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Rate limiting settings
        self.last_request_time = 0
        self.min_request_interval = 0.5  # 2 requests per second max
        self.retry_count = 3
        self.retry_delay = 1.0
        
        # Symbol mapping (Binance to Yahoo Finance)
        self.symbol_map = {
            'BTCUSDT': 'BTC-USD',
            'ETHUSDT': 'ETH-USD',
            'XAUUSD': 'GC=F',  # Gold futures
        }
    
    def _validate_credentials(self) -> bool:
        """
        Validate Yahoo Finance connectivity.
        Yahoo Finance public API doesn't require authentication.
        """
        try:
            # Try a simple request to check connectivity
            response = requests.get(
                f"{self.BASE_URL}/BTC-USD?interval=1d&range=1d",
                timeout=10
            )
            
            if response.status_code == 200:
                self.logger.info(f"{self.CONNECTOR_NAME} connection validated successfully")
                self.is_connected = True
                return True
            else:
                self.logger.warning(f"{self.CONNECTOR_NAME} connection test failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"{self.CONNECTOR_NAME} validation error: {e}")
            return False
    
    def _get_yahoo_symbol(self, binance_symbol: str) -> Optional[str]:
        """
        Convert Binance symbol to Yahoo Finance symbol.
        
        Args:
            binance_symbol: Binance trading pair
            
        Returns:
            Yahoo Finance symbol or None if not supported
        """
        return self.symbol_map.get(binance_symbol)
    
    def _make_request(self, symbol: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make request to Yahoo Finance API with retry logic.
        
        Args:
            symbol: Yahoo Finance symbol
            params: Query parameters
            
        Returns:
            Response JSON or None on failure
        """
        yahoo_symbol = self._get_yahoo_symbol(symbol)
        if not yahoo_symbol:
            return None
        
        url = f"{self.BASE_URL}/{yahoo_symbol}"
        
        default_params = {
            'interval': '1m',
            'range': '1d',
        }
        
        if params:
            default_params.update(params)
        
        for attempt in range(self.retry_count):
            try:
                # Rate limiting
                current_time = time.time()
                time_since_last_request = current_time - self.last_request_time
                if time_since_last_request < self.min_request_interval:
                    time.sleep(self.min_request_interval - time_since_last_request)
                
                self.last_request_time = time.time()
                
                # Add user agent to avoid blocking
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                self.logger.debug(f"Fetching from {self.CONNECTOR_NAME}: {yahoo_symbol}")
                
                response = requests.get(
                    url,
                    headers=headers,
                    params=default_params,
                    timeout=10
                )
                
                # Log the API call
                self.logger.info(
                    f"{self.CONNECTOR_NAME} API call: {yahoo_symbol} "
                    f"Status: {response.status_code} "
                    f"Timestamp: {datetime.utcnow().isoformat()}"
                )
                
                if response.status_code == 200:
                    self.request_count += 1
                    data = response.json()
                    
                    # Check for valid data
                    if data and 'chart' in data and 'result' in data['chart']:
                        if data['chart']['result']:
                            return data
                        else:
                            self.logger.warning(f"{self.CONNECTOR_NAME} no data for {yahoo_symbol}")
                            return None
                
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
        Fetch current price from Yahoo Finance.
        
        Args:
            symbol: Trading pair
            
        Returns:
            Current price or None
        """
        data = self._make_request(symbol)
        
        if data:
            result = data['chart']['result'][0]
            meta = result.get('meta', {})
            
            if 'regularMarketPrice' in meta:
                price = meta['regularMarketPrice']
                self.logger.info(f"{self.CONNECTOR_NAME} price for {symbol}: ${price:.2f}")
                return price
            
            if 'previousClose' in meta:
                price = meta['previousClose']
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
        Fetch OHLCV bars from Yahoo Finance.
        
        Args:
            symbol: Trading pair
            timeframe: Kline interval (1m, 5m, 15m, 1h, 1d)
            limit: Number of bars
            
        Returns:
            DataFrame with OHLCV data
        """
        # Convert timeframe to Yahoo Finance format
        timeframe_map = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '1h': '1h',
            '4h': '1d',  # Yahoo doesn't have 4h, use 1d
            '1d': '1d',
        }
        
        yahoo_timeframe = timeframe_map.get(timeframe, '1m')
        
        # Convert limit to range
        range_map = {
            50: '1mo',
            100: '3mo',
            200: '6mo',
            500: '1y',
        }
        
        range_value = range_map.get(limit or 100, '3mo')
        
        params = {
            'interval': yahoo_timeframe,
            'range': range_value,
        }
        
        data = self._make_request(symbol, params)
        
        if data:
            result = data['chart']['result'][0]
            timestamp = result.get('timestamp', [])
            indicators = result.get('indicators', {})
            
            if timestamp and indicators:
                quote = indicators.get('quote', [{}])[0]
                
                df_data = {
                    'timestamp': [datetime.fromtimestamp(ts) for ts in timestamp],
                    'open': quote.get('open', []),
                    'high': quote.get('high', []),
                    'low': quote.get('low', []),
                    'close': quote.get('close', []),
                    'volume': quote.get('volume', []),
                }
                
                df = pd.DataFrame(df_data)
                df = df.set_index('timestamp')
                
                # Handle missing values
                df = df.dropna()
                
                self.logger.info(f"{self.CONNECTOR_NAME} fetched {len(df)} bars for {symbol}")
                return df
        
        self.logger.warning(f"{self.CONNECTOR_NAME} no bars found for {symbol}")
        return pd.DataFrame()
    
    def get_status(self) -> Dict[str, Any]:
        """Get connector status."""
        return {
            'connector': self.CONNECTOR_NAME,
            'is_connected': self.is_connected,
            'request_count': self.request_count,
            'error_count': self.error_count,
            'last_request_time': datetime.fromtimestamp(self.last_request_time).isoformat() if self.last_request_time else None,
            'supported_symbols': list(self.symbol_map.keys()),
        }