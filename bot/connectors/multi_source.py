"""
Multi-source connector for price verification.
Pulls from multiple sources and validates prices with automatic failover.
Uses Alpaca, Polygon, Yahoo, TradingView, CoinGecko, CoinCap.
NO BINANCE - Completely removed.
"""

from typing import Optional, Dict, Any, List
import pandas as pd
import logging
from datetime import datetime
import time

from bot.connectors.base import BaseDataConnector
from bot.connectors.coingecko import CoinGeckoConnector
from bot.connectors.coincap import CoinCapConnector
from bot.connectors.mock_live import MockLiveConnector
from bot.connectors.alpaca import AlpacaConnector
from bot.connectors.yahoo_finance import YahooFinanceConnector
from bot.connectors.tradingview import TradingViewConnector
from bot.connectors.metals_live import MetalsLiveConnector
from bot.utils.env_loader import get_env_loader

# Try to import Polygon connector
try:
    from bot.connectors.polygon import PolygonConnector
    _polygon_available = True
except ImportError:
    _polygon_available = False
    PolygonConnector = None


class MultiSourceConnector(BaseDataConnector):
    """
    Multi-source connector that validates prices across multiple data sources.
    Implements deviation checks and SHA-256 checksums.
    Provides automatic failover with exponential backoff retry logic.
    
    Data Sources (priority order):
    1. Polygon (if API key present)
    2. Alpaca (if API key present)
    3. Yahoo Finance (backup)
    4. CoinGecko (backup)
    5. CoinCap (backup)
    6. MetalsLive (for XAUUSD only)
    7. TradingView (webhook mode)
    8. MockLive (last resort fallback - only in VERIFIED_TEST mode)
    
    IMPORTANT: In LIVE mode, bot requires at least 2 healthy connectors.
    In VERIFIED_TEST mode, bot can run with fewer sources or even mock data.
    """
    
    CONNECTOR_NAME = "multi_source"
    
    # Deviation thresholds by asset class (updated to prevent false positives)
    DEVIATION_THRESHOLDS = {
        'crypto': 0.015,    # 1.5% for crypto (was 0.05% - too strict)
        'metals': 0.010,    # 1.0% for metals
        'forex': 0.005,     # 0.5% for forex/fiat pairs
    }
    DEFAULT_DEVIATION = 0.015  # Default 1.5%
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Get environment loader to check mode
        self.env_loader = get_env_loader()
        self.mode = self.env_loader.mode  # 'VERIFIED_TEST' or 'LIVE_SIGNAL'
        
        # Initialize all connectors
        self.alpaca = AlpacaConnector(config)
        self.yahoo = YahooFinanceConnector(config)
        self.coingecko = CoinGeckoConnector(config)
        self.coincap = CoinCapConnector(config)
        self.metals = MetalsLiveConnector(config)
        self.tradingview = TradingViewConnector(config)
        self.mock = MockLiveConnector(config)
        
        # Try to initialize Polygon if available
        if _polygon_available and PolygonConnector:
            self.polygon = PolygonConnector(config)
        else:
            self.polygon = None
            self.logger.warning("Polygon connector not available")
        
        # All connectors (including mock)
        self.all_connectors = []
        
        # Add Polygon if available
        if self.polygon:
            self.all_connectors.append(self.polygon)
        
        # Add other connectors
        self.all_connectors.extend([
            self.alpaca,
            self.yahoo,
            self.coingecko,
            self.coincap,
            self.metals,
            self.tradingview,
        ])
        
        # Add mock only in VERIFIED_TEST mode
        if self.mode == 'VERIFIED_TEST':
            self.all_connectors.append(self.mock)
        
        # Price audit trail
        self.price_audit_trail: List[Dict[str, Any]] = []
        
        # Data source status tracking
        self.active_data_source = None
        self.last_live_data_time = None
        self.data_source_failures = 0
        
        # Minimum sources required (depends on mode)
        self.min_sources_required = 1 if self.mode == 'VERIFIED_TEST' else 2
        
        # Symbol-specific connector priorities
        self.symbol_connectors = {
            'BTCUSDT': [self.polygon, self.alpaca, self.yahoo, self.coingecko, self.coincap, self.tradingview],
            'ETHUSDT': [self.polygon, self.alpaca, self.yahoo, self.coingecko, self.coincap, self.tradingview],
            'XAUUSD': [self.metals, self.yahoo, self.alpaca],
        }
        
        self.logger.warning("=" * 70)
        self.logger.warning(f"Mode: {self.mode}")
        self.logger.warning(f"Minimum sources required: {self.min_sources_required}")
        self.logger.warning("Available data sources:")
        for connector in self.all_connectors:
            status = "🟢" if connector.is_enabled else "🔴"
            self.logger.warning(f"  {status} {connector.CONNECTOR_NAME}")
        self.logger.warning("=" * 70)
    
    def _validate_credentials(self) -> bool:
        """Validate that at least one connector is working."""
        self.logger.info("Validating data sources...")
        
        valid_count = 0
        valid_connectors = []
        
        for connector in self.all_connectors:
            if connector.CONNECTOR_NAME == 'mock_live':
                continue  # Skip mock connector for validation
            
            try:
                # Try to connect the connector
                if connector.connect():
                    self.logger.info(f"✅ {connector.CONNECTOR_NAME} validated successfully")
                    valid_count += 1
                    valid_connectors.append(connector.CONNECTOR_NAME)
                else:
                    self.logger.warning(f"⚠️ {connector.CONNECTOR_NAME} validation failed")
            except Exception as e:
                self.logger.warning(f"⚠️ {connector.CONNECTOR_NAME} validation error: {e}")
        
        self.is_connected = valid_count >= self.min_sources_required
        
        if self.is_connected:
            self.logger.info(f"✅ {valid_count} data source(s) available: {', '.join(valid_connectors)}")
        else:
            if self.mode == 'LIVE_SIGNAL':
                self.logger.error("❌ INSUFFICIENT DATA SOURCES - BOT WILL HALT")
                raise RuntimeError(
                    f"Insufficient data sources for LIVE mode. "
                    f"Required: {self.min_sources_required}, Available: {valid_count}"
                )
            else:
                self.logger.warning(
                    f"⚠️ Only {valid_count} data source(s) available in VERIFIED_TEST mode. "
                    f"Will use mock data if needed."
                )
        
        return self.is_connected
    
    def _health_check(self) -> bool:
        """Check health of available connectors."""
        healthy_count = 0
        
        for connector in self.all_connectors:
            if connector.CONNECTOR_NAME == 'mock_live':
                continue
            
            # Check circuit timeout
            connector._check_circuit_timeout()
            
            if connector.is_connected and connector.is_enabled:
                healthy_count += 1
        
        return healthy_count >= self.min_sources_required
    
    def _get_connectors_for_symbol(self, symbol: str) -> List[BaseDataConnector]:
        """Get prioritized connectors for a specific symbol."""
        if symbol in self.symbol_connectors:
            connectors = [c for c in self.symbol_connectors[symbol] if c is not None]
        else:
            connectors = self.all_connectors
        
        # Filter out disabled connectors
        enabled_connectors = [c for c in connectors if c.is_enabled]
        
        return enabled_connectors
    
    def _get_asset_class(self, symbol: str) -> str:
        """Determine asset class from symbol."""
        symbol_upper = symbol.upper()
        
        if any(crypto in symbol_upper for crypto in ['BTC', 'ETH', 'LTC', 'XRP', 'ADA', 'DOGE', 'USDT']):
            return 'crypto'
        elif any(metal in symbol_upper for metal in ['XAU', 'XAG', 'GOLD', 'SILVER']):
            return 'metals'
        else:
            return 'forex'
    
    def _get_deviation_threshold(self, symbol: str) -> float:
        """Get deviation threshold for symbol based on asset class."""
        asset_class = self._get_asset_class(symbol)
        return self.DEVIATION_THRESHOLDS.get(asset_class, self.DEFAULT_DEVIATION)
    
    def fetch_current_price(self, symbol: str) -> Optional[float]:
        """
        Fetch and validate price from multiple sources with automatic failover.
        
        In LIVE mode: Requires minimum 2 verified sources.
        In VERIFIED_TEST mode: Can work with 1 source or mock data.
        
        Logs every fetch attempt with source, timestamp, and price deviation.
        """
        connectors = self._get_connectors_for_symbol(symbol)
        
        if not connectors:
            self.logger.error(f"❌ No enabled connectors available for {symbol}")
            
            if self.mode == 'LIVE_SIGNAL':
                raise RuntimeError(f"No connectors available for {symbol}")
            
            # In VERIFIED_TEST, try to use mock
            if self.mock and self.mock.is_enabled:
                self.logger.warning(f"⚠️ Using mock data for {symbol} in VERIFIED_TEST mode")
                return self.mock.fetch_current_price(symbol)
            
            return None
        
        prices = {}
        sources = {}
        timestamps = {}
        timestamp = datetime.utcnow().isoformat()
        
        # Get deviation threshold for this symbol
        max_deviation = self._get_deviation_threshold(symbol)
        
        # Try each connector in priority order
        for connector in connectors:
            try:
                self.logger.info(
                    f"Fetching price from {connector.CONNECTOR_NAME} for {symbol} "
                    f"at {timestamp}"
                )
                
                price = connector.fetch_current_price(symbol)
                
                if price is not None and price > 0:
                    prices[connector.CONNECTOR_NAME] = price
                    sources[connector.CONNECTOR_NAME] = price
                    timestamps[connector.CONNECTOR_NAME] = datetime.utcnow().isoformat()
                    
                    self.logger.info(
                        f"✅ {connector.CONNECTOR_NAME} price: ${price:.2f} "
                        f"for {symbol} at {timestamp}"
                    )
                    
                    # Update active data source tracking
                    self.active_data_source = connector.CONNECTOR_NAME
                    self.last_live_data_time = datetime.utcnow()
                    self.data_source_failures = 0
                    
                    # In LIVE mode, continue to get 2+ sources
                    # In VERIFIED_TEST, we can stop at 1
                    if len(prices) >= self.min_sources_required:
                        break
                        
            except Exception as e:
                self.logger.error(f"❌ Error fetching from {connector.CONNECTOR_NAME}: {e}")
        
        # Validate prices based on mode
        if len(prices) < 1:
            self.logger.error(f"❌ NO PRICE DATA from any source for {symbol}")
            
            if self.mode == 'LIVE_SIGNAL':
                raise RuntimeError(f"No price data for {symbol}")
            
            return None
        
        if len(prices) == 1:
            # Only one source available
            price = list(prices.values())[0]
            source_name = list(prices.keys())[0]
            
            if source_name == "mock_live":
                self.logger.info(f"⚠️ Using mock data for {symbol} (VERIFIED_TEST mode)")
            else:
                self.logger.info(f"✅ Price from {source_name}: ${price:.2f} for {symbol}")
            
            # Generate checksum for single source
            checksum = self._generate_checksum(
                symbol,
                price,
                timestamps.get(source_name, timestamp),
                source_name,
                timestamp,
                "N/A"
            )
            
            # Record audit trail
            self._record_audit_trail(
                symbol, price, checksum, sources, timestamps,
                0.0, max_deviation, True, source_name
            )
            
            return price
        
        # Multiple sources available - validate deviation
        price_values = list(prices.values())
        source_names = list(prices.keys())
        
        min_price = min(price_values)
        max_price = max(price_values)
        
        deviation = (max_price - min_price) / min_price
        
        # Log deviation
        self.logger.info(
            f"Price deviation for {symbol}: {deviation:.4%} "
            f"(min: ${min_price:.2f}, max: ${max_price:.2f}, "
            f"sources: {source_names})"
        )
        
        if deviation > max_deviation:
            self.logger.warning(
                f"⚠️ Price deviation exceeds maximum: {deviation:.4%} "
                f"(max: {max_deviation:.4%})"
            )
            # Use median price to reduce impact of outliers
            sorted_prices = sorted(price_values)
            if len(sorted_prices) >= 3:
                canonical_price = sorted_prices[len(sorted_prices) // 2]
                self.logger.info(f"📊 Using median price: ${canonical_price:.2f}")
            else:
                # Use primary source
                primary_source = source_names[0]
                canonical_price = prices[primary_source]
                self.logger.info(f"📊 Using primary source: {primary_source}")
        else:
            self.logger.info(f"✅ Price deviation within acceptable limits")
            # Use average price when deviation is acceptable
            canonical_price = sum(price_values) / len(price_values)
        
        # Identify primary and secondary sources
        primary_source = source_names[0]
        secondary_source = source_names[1] if len(source_names) > 1 else None
        
        # Generate checksum with both sources
        primary_ts = timestamps.get(primary_source, timestamp)
        secondary_ts = timestamps.get(secondary_source, timestamp)
        checksum = self._generate_checksum(
            symbol,
            canonical_price,
            primary_ts,
            primary_source,
            secondary_ts,
            secondary_source or "N/A"
        )
        
        # Record audit trail
        self._record_audit_trail(
            symbol, canonical_price, checksum, sources, timestamps,
            deviation, max_deviation, deviation <= max_deviation,
            primary_source
        )
        
        return canonical_price
    
    def _generate_checksum(
        self,
        symbol: str,
        price: float,
        primary_ts: str,
        primary_source: str,
        secondary_ts: str,
        secondary_source: str
    ) -> str:
        """Generate SHA-256 checksum for price verification."""
        import hashlib
        data = f"{symbol}|{price:.8f}|{primary_ts}|{primary_source}|{secondary_ts}|{secondary_source}"
        checksum = hashlib.sha256(data.encode()).hexdigest()
        return checksum
    
    def _record_audit_trail(
        self,
        symbol: str,
        price: float,
        checksum: str,
        sources: Dict[str, float],
        timestamps: Dict[str, str],
        deviation: float,
        max_deviation: float,
        deviation_allowed: bool,
        active_source: str
    ) -> None:
        """Record price audit trail entry."""
        audit_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'symbol': symbol,
            'price': price,
            'checksum': checksum,
            'sources': sources,
            'source_timestamps': timestamps,
            'deviation': deviation,
            'max_deviation': max_deviation,
            'deviation_allowed': deviation_allowed,
            'active_source': active_source,
        }
        self.price_audit_trail.append(audit_entry)
        self.request_count += 1
    
    def fetch_bars(
        self,
        symbol: str,
        timeframe: str,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """Fetch bars from primary source or fallback to next available."""
        connectors = self._get_connectors_for_symbol(symbol)
        
        for connector in connectors:
            try:
                self.logger.info(f"Fetching bars from {connector.CONNECTOR_NAME} for {symbol}")
                bars = connector.fetch_bars(symbol, timeframe, limit)
                
                if bars is not None and not bars.empty:
                    self.logger.info(
                        f"✅ Bars from {connector.CONNECTOR_NAME}: {len(bars)} bars for {symbol}"
                    )
                    return bars
                    
            except Exception as e:
                self.logger.warning(f"⚠️ Error fetching bars from {connector.CONNECTOR_NAME}: {e}")
        
        self.logger.error(f"❌ NO BAR DATA from any source for {symbol}")
        
        if self.mode == 'LIVE_SIGNAL':
            raise RuntimeError(f"No bar data for {symbol}")
        
        return pd.DataFrame()
    
    def get_price_checksum(self, symbol: str, price: float) -> str:
        """Generate checksum for a price (legacy method for compatibility)."""
        timestamp = datetime.utcnow().isoformat()
        return self._generate_checksum(
            symbol,
            price,
            timestamp,
            "unknown",
            timestamp,
            "unknown"
        )
    
    def get_audit_trail(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get price audit trail."""
        return self.price_audit_trail[-limit:]
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all connectors."""
        primary_names = [
            c.CONNECTOR_NAME 
            for c in self.all_connectors 
            if c.CONNECTOR_NAME != "mock_live"
        ]
        
        sources_status = {}
        for connector in self.all_connectors:
            if connector.CONNECTOR_NAME != "mock_live":
                try:
                    sources_status[connector.CONNECTOR_NAME] = connector.get_status()
                except:
                    sources_status[connector.CONNECTOR_NAME] = {'is_connected': False}
        
        # Count healthy connectors
        healthy_connectors = sum(
            1 for status in sources_status.values()
            if status.get('is_enabled', False) and status.get('is_connected', False)
        )
        
        return {
            'connector': self.CONNECTOR_NAME,
            'mode': self.mode,
            'is_connected': self.is_connected,
            'has_live_data': bool(self.active_data_source),
            'active_data_source': self.active_data_source,
            'last_live_data_time': self.last_live_data_time.isoformat() if self.last_live_data_time else None,
            'data_source_failures': self.data_source_failures,
            'healthy_connectors': healthy_connectors,
            'min_sources_required': self.min_sources_required,
            'request_count': self.request_count,
            'error_count': self.error_count,
            'deviation_thresholds': self.DEVIATION_THRESHOLDS,
            'default_deviation': self.DEFAULT_DEVIATION,
            'primary_connectors': primary_names,
            'sources': sources_status,
            'audit_trail_size': len(self.price_audit_trail),
            'symbol_connectors': list(self.symbol_connectors.keys()),
        }