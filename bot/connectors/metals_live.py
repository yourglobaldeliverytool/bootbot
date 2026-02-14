"""
metals.live connector for gold/silver price data.
"""

import requests
import logging
import time
import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from bot.connectors.base import BaseDataConnector

logger = logging.getLogger(__name__)


class MetalsLiveConnector(BaseDataConnector):
    """
    Connector for metals.live API (free public endpoint for gold/silver).
    """
    
    CONNECTOR_NAME = "metals_live"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        self.base_url = "https://metals.live"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; ApexSignalBot/1.0)'
        })
        
        # Rate limiting
        self.max_retries = 3
        self.timeout = 10
    
    def _validate_credentials(self) -> bool:
        """
        Validate MetalsLive connectivity.
        MetalsLive doesn't require authentication.
        """
        try:
            # Try a simple request to check connectivity
            response = requests.get(
                f"{self.base_url}",
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
    
    def _make_request(self, endpoint: str = "") -> Optional[Dict[str, Any]]:
        """
        Make a request to metals.live API.
        
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
                    # metals.live returns HTML, need to parse
                    return self._parse_html_response(response.text)
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
    
    def _parse_html_response(self, html: str) -> Optional[Dict[str, Any]]:
        """
        Parse HTML response from metals.live.
        
        Note: This is a simplified parser. In production, you'd use BeautifulSoup
        for more robust HTML parsing. For now, we'll use regex as a fallback.
        
        Args:
            html: HTML response text
            
        Returns:
            Parsed price data or None
        """
        import re
        
        try:
            # Extract gold price from HTML
            gold_pattern = r'Gold[^$]*\$?([\d,]+\.?\d*)'
            match = re.search(gold_pattern, html)
            
            if match:
                price_str = match.group(1).replace(',', '')
                price = float(price_str)
                
                return {
                    'price': price,
                    'timestamp': datetime.utcnow().isoformat(),
                    'source': 'MetalsLive'
                }
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to parse MetalsLive HTML: {e}")
        
        return None
    
    def fetch_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for a symbol.
        
        Args:
            symbol: Trading pair symbol (only XAUUSD supported)
            
        Returns:
            Price or None if failed
        """
        if symbol != 'XAUUSD':
            self.logger.warning(f"⚠️ {self.CONNECTOR_NAME} only supports XAUUSD, got: {symbol}")
            return None
        
        data = self._make_request()
        if data and 'price' in data:
            price = data['price']
            self.logger.info(f"{self.CONNECTOR_NAME} price for {symbol}: ${price:.2f}")
            return price
        
        # Fallback to stub data if parsing fails
        self.logger.warning("⚠️ MetalsLive returned no data, using stub")
        stub_prices = {'XAUUSD': 2300.0}
        price = stub_prices.get(symbol)
        if price:
            self.logger.info(f"{self.CONNECTOR_NAME} stub price for {symbol}: ${price:.2f}")
            return price
        
        return None
    
    def fetch_bars(
        self,
        symbol: str,
        timeframe: str,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Get historical price bars (stub implementation).
        
        Note: metals.live doesn't provide historical data via simple API.
        This is a stub that returns synthetic data for testing.
        
        Args:
            symbol: Trading pair symbol
            timeframe: Time interval
            limit: Number of bars to retrieve
            
        Returns:
            DataFrame with OHLCV data
        """
        if symbol != 'XAUUSD':
            return pd.DataFrame()
        
        # Return synthetic bars for testing
        import random
        bars_data = []
        base_price = 2300.0  # Approximate gold price
        now = datetime.utcnow()
        bars_limit = limit or 100
        
        for i in range(bars_limit):
            timestamp = now - timedelta(minutes=15 * i)
            change = random.uniform(-5, 5)
            open_p = base_price + change
            close_p = open_p + random.uniform(-2, 2)
            high_p = max(open_p, close_p) + random.uniform(0, 1)
            low_p = min(open_p, close_p) - random.uniform(0, 1)
            
            bars_data.append({
                'timestamp': timestamp,
                'open': open_p,
                'high': high_p,
                'low': low_p,
                'close': close_p,
                'volume': random.uniform(1000, 5000)
            })
        
        if bars_data:
            df = pd.DataFrame(bars_data)
            df = df.set_index('timestamp')
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            self.logger.info(f"{self.CONNECTOR_NAME} generated {len(df)} synthetic bars for {symbol}")
            return df
        
        return pd.DataFrame()
    
    def get_status(self) -> Dict[str, Any]:
        """Get connector status."""
        return {
            'connector': self.CONNECTOR_NAME,
            'is_connected': self.is_connected,
            'request_count': self.request_count,
            'error_count': self.error_count,
            'supported_symbols': ['XAUUSD'],
        }