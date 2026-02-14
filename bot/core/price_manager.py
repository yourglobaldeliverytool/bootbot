"""
Central Price Manager with caching, normalization, and multi-source verification.
Implements 10s TTL cache, symbol normalization, and cross-source verification.
"""

import time
import hashlib
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from bot.connectors.multi_source import MultiSourceConnector


class PriceManager:
    """
    Central price manager with caching and cross-source verification.
    
    Features:
    - Fetch each symbol once per cycle
    - Cache per-symbol result for configurable TTL (default 10s)
    - Symbol normalization map (e.g., BTCUSDT → BTC/USD)
    - Cross-source verification with deviation thresholds
    - SHA-256 checksums for audit trail
    """
    
    # Deviation thresholds by asset class
    DEVIATION_THRESHOLDS = {
        'crypto': 0.015,    # 1.5% for crypto
        'metals': 0.010,    # 1.0% for metals
        'forex': 0.005,     # 0.5% for forex/fiat pairs
    }
    
    # Symbol normalization map
    SYMBOL_NORMALIZATION = {
        # Crypto: Exchange format → Standard format
        'BTCUSDT': {'standard': 'BTC/USD', 'class': 'crypto'},
        'ETHUSDT': {'standard': 'ETH/USD', 'class': 'crypto'},
        
        # Metals
        'XAUUSD': {'standard': 'XAU/USD', 'class': 'metals'},
        'XAGUSD': {'standard': 'XAG/USD', 'class': 'metals'},
        
        # Forex
        'EURUSD': {'standard': 'EUR/USD', 'class': 'forex'},
        'GBPUSD': {'standard': 'GBP/USD', 'class': 'forex'},
    }
    
    def __init__(self, connector: MultiSourceConnector, cache_ttl: int = 10):
        """
        Initialize price manager.
        
        Args:
            connector: Multi-source connector for price fetching
            cache_ttl: Cache time-to-live in seconds (default 10s)
        """
        self.connector = connector
        self.cache_ttl = cache_ttl
        self.logger = logging.getLogger(__name__)
        
        # Price cache: {symbol: {'price': float, 'timestamp': float, 'metadata': dict}}
        self._price_cache: Dict[str, Dict[str, Any]] = {}
        
        # Statistics
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_fetches = 0
    
    def get_price(
        self,
        symbol: str,
        prefer_sources: Optional[List[str]] = None,
        force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get price for a symbol with caching and verification.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            prefer_sources: Optional list of preferred source names
            force_refresh: Force cache refresh
            
        Returns:
            Dictionary with:
                - 'price': float (canonical price)
                - 'source': str (primary source)
                - 'secondary_source': str (secondary source if available)
                - 'timestamp': str (ISO format timestamp)
                - 'deviation': float (deviation between sources)
                - 'checksum': str (SHA-256 checksum)
                - 'metadata': dict (source metadata)
            or None if price cannot be fetched
        """
        # Normalize symbol
        normalized = self._normalize_symbol(symbol)
        if not normalized:
            self.logger.error(f"Cannot normalize symbol: {symbol}")
            return None
        
        # Check cache
        if not force_refresh and self._is_cached(symbol):
            self.cache_hits += 1
            self.logger.debug(f"Cache HIT for {symbol}")
            return self._price_cache[symbol]['data']
        
        # Cache miss - fetch fresh price
        self.cache_misses += 1
        self.total_fetches += 1
        self.logger.debug(f"Cache MISS for {symbol} - fetching fresh price")
        
        # Fetch with cross-source verification
        price_data = self._fetch_with_verification(symbol, normalized, prefer_sources)
        
        if price_data:
            # Cache the result
            self._cache_price(symbol, price_data)
            self.logger.info(f"✅ Price cached for {symbol}: ${price_data['price']:.2f}")
        
        return price_data
    
    def _normalize_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Normalize symbol to standard format and determine asset class.
        
        Args:
            symbol: Raw symbol string
            
        Returns:
            Dict with 'standard' and 'class' keys, or None
        """
        # Case-insensitive lookup
        symbol_upper = symbol.upper()
        
        # Check exact match
        if symbol_upper in self.SYMBOL_NORMALIZATION:
            return self.SYMBOL_NORMALIZATION[symbol_upper]
        
        # Try to determine class from symbol
        if 'USDT' in symbol_upper or 'USD' in symbol_upper:
            # It's a USD pair
            if any(crypto in symbol_upper for crypto in ['BTC', 'ETH', 'LTC', 'XRP', 'ADA']):
                return {'standard': symbol_upper, 'class': 'crypto'}
            elif any(metal in symbol_upper for metal in ['XAU', 'XAG', 'GOLD', 'SILVER']):
                return {'standard': symbol_upper, 'class': 'metals'}
            else:
                return {'standard': symbol_upper, 'class': 'forex'}
        
        # Default: treat as crypto
        return {'standard': symbol_upper, 'class': 'crypto'}
    
    def _fetch_with_verification(
        self,
        symbol: str,
        normalized: Dict[str, Any],
        prefer_sources: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch price with cross-source verification.
        
        Args:
            symbol: Original symbol
            normalized: Normalized symbol info
            prefer_sources: Preferred source names
            
        Returns:
            Price data dict or None
        """
        try:
            # Fetch primary price
            price = self.connector.fetch_current_price(symbol)
            
            if price is None or price <= 0:
                self.logger.error(f"Failed to fetch price for {symbol}")
                return None
            
            # Get deviation threshold for asset class
            asset_class = normalized['class']
            max_deviation = self.DEVIATION_THRESHOLDS.get(asset_class, 0.015)
            
            # Get connector status for source info
            status = self.connector.get_status()
            active_source = status.get('active_data_source', 'unknown')
            sources_status = status.get('sources', {})
            
            # Get audit trail for secondary source info
            audit_trail = self.connector.get_audit_trail(limit=5)
            secondary_source = None
            deviation = 0.0
            
            if audit_trail:
                latest_audit = audit_trail[-1]
                sources = latest_audit.get('sources', {})
                deviation = latest_audit.get('deviation', 0.0)
                
                # Find secondary source (first non-primary)
                for source_name in sources.keys():
                    if source_name != active_source:
                        secondary_source = source_name
                        break
            
            # Check deviation threshold
            if deviation > max_deviation:
                self.logger.warning(
                    f"⚠️ Price deviation {deviation:.4%} exceeds threshold {max_deviation:.4%} "
                    f"for {symbol}"
                )
                # Still use the price but log warning
                # In production, could implement median calculation
            
            # Generate checksum
            checksum = self._generate_checksum(
                symbol,
                price,
                datetime.utcnow().isoformat(),
                active_source,
                secondary_source or 'N/A'
            )
            
            # Build price data
            price_data = {
                'price': price,
                'symbol': symbol,
                'standard_symbol': normalized['standard'],
                'asset_class': asset_class,
                'source': active_source,
                'secondary_source': secondary_source,
                'timestamp': datetime.utcnow().isoformat(),
                'deviation': deviation,
                'max_deviation': max_deviation,
                'checksum': checksum,
                'metadata': {
                    'sources_status': sources_status,
                    'cache_ttl': self.cache_ttl,
                }
            }
            
            return price_data
            
        except Exception as e:
            self.logger.error(f"Error fetching price for {symbol}: {e}")
            return None
    
    def _generate_checksum(
        self,
        symbol: str,
        price: float,
        timestamp: str,
        primary_source: str,
        secondary_source: str
    ) -> str:
        """
        Generate SHA-256 checksum for price verification.
        
        Format: SHA256("{symbol}|{price:.8f}|{timestamp}|{primary}|{secondary}")
        """
        data = f"{symbol}|{price:.8f}|{timestamp}|{primary_source}|{secondary_source}"
        checksum = hashlib.sha256(data.encode()).hexdigest()
        return checksum
    
    def _is_cached(self, symbol: str) -> bool:
        """Check if symbol is cached and not expired."""
        if symbol not in self._price_cache:
            return False
        
        cache_entry = self._price_cache[symbol]
        age = time.time() - cache_entry['timestamp']
        
        return age < self.cache_ttl
    
    def _cache_price(self, symbol: str, price_data: Dict[str, Any]) -> None:
        """Cache price data."""
        self._price_cache[symbol] = {
            'data': price_data,
            'timestamp': time.time()
        }
    
    def invalidate_cache(self, symbol: Optional[str] = None) -> None:
        """
        Invalidate cache for a symbol or all symbols.
        
        Args:
            symbol: Symbol to invalidate, or None for all
        """
        if symbol:
            if symbol in self._price_cache:
                del self._price_cache[symbol]
                self.logger.debug(f"Cache invalidated for {symbol}")
        else:
            self._price_cache.clear()
            self.logger.debug("All cache invalidated")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'total_fetches': self.total_fetches,
            'hit_rate': f"{hit_rate:.1f}%",
            'cached_symbols': list(self._price_cache.keys()),
            'cache_ttl': self.cache_ttl,
        }
    
    def verify_checksum(
        self,
        symbol: str,
        price: float,
        timestamp: str,
        primary_source: str,
        secondary_source: str,
        expected_checksum: str
    ) -> bool:
        """
        Verify a price checksum.
        
        Args:
            symbol: Symbol
            price: Price
            timestamp: Timestamp
            primary_source: Primary source name
            secondary_source: Secondary source name
            expected_checksum: Expected checksum
            
        Returns:
            True if checksum matches
        """
        calculated = self._generate_checksum(
            symbol, price, timestamp, primary_source, secondary_source
        )
        return calculated == expected_checksum