"""
CoinCap API connector for price data.
"""

import requests
import logging
import time
import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime

from bot.connectors.base import BaseDataConnector

logger = logging.getLogger(__name__)


class CoinCapConnector(BaseDataConnector):
    """
    Connector for CoinCap public API (no authentication required).
    """
    
    CONNECTOR_NAME = "coincap"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        self.base_url = "https://api.coincap.io/v2"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; ApexSignalBot/1.0)'
        })
        
        # Symbol mapping
        self.symbol_map = {
            'BTCUSDT': 'bitcoin',
            'ETHUSDT': 'ethereum',
            'XAUUSD': None  # CoinCap doesn't support gold
        }
        
        # Rate limiting
        self.max_retries = 3
        self.timeout = 10
    
    def _validate_credentials(self) -> bool:
        """
        Validate CoinCap connectivity.
        CoinCap doesn't require authentication.
        """
        try:
            # Try a simple request to check connectivity
            response = requests.get(
                f"{self.base_url}/assets/bitcoin",
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
    
    def _get_coincap_symbol(self, binance_symbol: str) -> Optional[str]:
        """
        Convert Binance symbol to CoinCap symbol.
        
        Args:
            binance_symbol: Binance trading pair
            
        Returns:
            CoinCap symbol or None if not supported
        """
        return self.symbol_map.get(binance_symbol)
    
    def _make_request(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """
        Make a request to CoinCap API with retry logic.
        
        Args:
            endpoint: API endpoint path
            
        Returns:
            Response data or None if failed
        """
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                response = self.session.get(url, timeout=self.timeout)
                latency = (time.time() - start_time) * 1000
                
                self.logger.debug(
                    f"{self.CONNECTOR_NAME} API call: {endpoint} "
                    f"Status: {response.status_code} "
                    f"Latency: {latency:.2f}ms"
                )
                
                if response.status_code == 200:
                    self.request_count += 1
                    return response.json()
                elif response.status_code == 429:
                    # Rate limited
                    wait_time = 2 ** attempt  # Exponential backoff
                    self.logger.warning(f"⚠️ {self.CONNECTOR_NAME} rate limited, waiting {wait_time}s")
                    time.sleep(wait_time)
                else:
                    self.logger.warning(f"⚠️ {self.CONNECTOR_NAME} returned status {response.status_code}")
                    
            except requests.exceptions.Timeout:
                self.logger.warning(f"⚠️ {self.CONNECTOR_NAME} request timed out (attempt {attempt + 1})")
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"⚠️ {self.CONNECTOR_NAME} request failed: {e}")
            
            # Wait before retry
            if attempt < self.max_retries - 1:
                time.sleep(1 + attempt * 0.5)
        
        self.error_count += 1
        return None
    
    def fetch_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            
        Returns:
            Price or None if failed
        """
        cc_symbol = self._get_coincap_symbol(symbol)
        if not cc_symbol:
            self.logger.warning(f"⚠️ {self.CONNECTOR_NAME} does not support symbol: {symbol}")
            return None
        
        data = self._make_request(f"/assets/{cc_symbol}")
        if data and 'data' in data:
            asset = data['data']
            price = float(asset.get('priceUsd', 0))
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
        Get historical price bars.
        
        Args:
            symbol: Trading pair symbol
            timeframe: Time interval (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Number of bars to retrieve
            
        Returns:
            DataFrame with OHLCV data
        """
        cc_symbol = self._get_coincap_symbol(symbol)
        if not cc_symbol:
            return pd.DataFrame()
        
        # Convert interval format
        interval_map = {
            '1m': 'm1',
            '5m': 'm5',
            '15m': 'm15',
            '1h': 'h1',
            '4h': 'h6',
            '1d': 'd1'
        }
        cc_interval = interval_map.get(timeframe, 'h1')
        bars_limit = limit or 100
        
        data = self._make_request(
            f"/assets/{cc_symbol}/history?interval={cc_interval}&limit={bars_limit}"
        )
        
        if data and 'data' in data:
            bars_data = []
            for item in data['data']:
                bars_data.append({
                    'timestamp': pd.to_datetime(item['time']),
                    'open': float(item['open']),
                    'high': float(item['high']),
                    'low': float(item['low']),
                    'close': float(item['close']),
                    'volume': float(item.get('volumeUsd', 0))
                })
            
            if bars_data:
                df = pd.DataFrame(bars_data)
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
            'request_count': self.request_count,
            'error_count': self.error_count,
            'supported_symbols': list(self.symbol_map.keys()),
        }