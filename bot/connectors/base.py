"""Base connector class for all data sources.

All connectors must inherit from this class and implement the required methods.
Provides common functionality including circuit breaker protection, rate limiting,
retry logic, and health checking.
"""

import time
import logging
from typing import Optional, Dict, Any, Callable
from datetime import datetime

from bot.core.circuit_breaker import get_circuit_breaker_registry
from bot.core.rate_limiter import GlobalRateLimiter


class BaseDataConnector:
    """
    Base class for all data connectors.
    
    All connectors must inherit from this class and implement:
    - fetch_current_price()
    - fetch_bars()
    - _validate_credentials()
    
    This class provides:
    - Circuit breaker protection
    - Rate limiting
    - Retry with exponential backoff
    - Health checking
    - Response validation
    - Safe operation without API keys
    """
    
    CONNECTOR_NAME = "base"
    
    # Retry configuration
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0  # seconds
    DEFAULT_BACKOFF_MULTIPLIER = 2.0
    
    # Circuit breaker configuration
    DEFAULT_MAX_FAILURES = 3
    DEFAULT_CIRCUIT_TIMEOUT = 300  # seconds
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the connector."""
        self.config = config or {}
        self.is_connected = False
        self.is_enabled = True
        self.logger = logging.getLogger(__name__)
        
        # Request tracking
        self.request_count = 0
        self.error_count = 0
        self.success_count = 0
        self.last_request_time = None
        self.last_success_time = None
        self.last_error_time = None
        
        # Consecutive failure tracking for circuit breaker
        self.consecutive_failures = 0
        self.circuit_open_time = None
        
        # Retry settings
        self.max_retries = self.config.get('max_retries', self.DEFAULT_MAX_RETRIES)
        self.retry_delay = self.config.get('retry_delay', self.DEFAULT_RETRY_DELAY)
        self.backoff_multiplier = self.config.get('backoff_multiplier', self.DEFAULT_BACKOFF_MULTIPLIER)
        
        # Circuit breaker settings
        self.max_failures = self.config.get('max_failures', self.DEFAULT_MAX_FAILURES)
        self.circuit_timeout = self.config.get('circuit_timeout', self.DEFAULT_CIRCUIT_TIMEOUT)
        
        # Circuit breaker for this connector
        self.circuit_breaker = get_circuit_breaker_registry().get_or_create(
            self.CONNECTOR_NAME,
            max_failures=self.max_failures,
            timeout=self.circuit_timeout
        )
        
        # Rate limiter
        self.rate_limiter = GlobalRateLimiter.get()
        
        # Latency tracking
        self.latency_ms = []
        self.max_latency_samples = 100
        
    def connect(self) -> bool:
        """
        Connect to the data source.
        
        Returns:
            True if connection successful, False otherwise
        """
        # If disabled, return False without attempting connection
        if not self.is_enabled:
            self.logger.info(f"{self.CONNECTOR_NAME} is disabled, skipping connection")
            return False
            
        # Check circuit breaker state
        if self.circuit_breaker.get_state() == 'OPEN':
            self.logger.warning(
                f"Circuit breaker is OPEN for {self.CONNECTOR_NAME}, "
                f"skipping connection attempt"
            )
            return False
        
        # Validate credentials if available
        if not self._validate_credentials():
            self.logger.warning(f"{self.CONNECTOR_NAME} credentials validation failed")
            self._disable_connector("Missing or invalid credentials")
            return False
        
        try:
            # Perform health check
            if self._health_check():
                self.is_connected = True
                self.logger.info(f"✅ {self.CONNECTOR_NAME} connected successfully")
                return True
            else:
                self.logger.warning(f"{self.CONNECTOR_NAME} health check failed")
                self._disable_connector("Health check failed")
                return False
        except Exception as e:
            self.logger.error(f"{self.CONNECTOR_NAME} connection error: {e}")
            self._record_failure()
            return False
    
    def _validate_credentials(self) -> bool:
        """
        Validate that required credentials are present.
        
        Subclasses should override this to check for specific API keys.
        Returns True if credentials are present and valid, False otherwise.
        """
        # Default: assume valid (for connectors that don't require credentials)
        return True
    
    def _health_check(self) -> bool:
        """
        Perform a health check on the connector.
        
        Subclasses should override this to test connectivity.
        Returns True if healthy, False otherwise.
        """
        # Default: assume healthy
        return True
    
    def _validate_response(self, response: Any) -> bool:
        """
        Validate a response from the data source.
        
        Args:
            response: Response to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Default: assume valid
        return True
    
    def _enforce_rate_limit(self) -> None:
        """Enforce rate limiting before making a request."""
        endpoint_name = self.CONNECTOR_NAME
        
        # Check if we can make a request
        if not self.rate_limiter.can_request(endpoint_name):
            wait_time = self.rate_limiter.wait_until_available(endpoint_name)
            if wait_time > 0:
                self.logger.info(
                    f"Rate limited for {endpoint_name}, waiting {wait_time:.1f}s"
                )
                time.sleep(wait_time)
    
    def _retry_with_backoff(
        self,
        func: Callable,
        *args,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        **kwargs
    ) -> Optional[Any]:
        """
        Execute a function with exponential backoff retry logic.
        
        Args:
            func: Function to call
            *args: Positional arguments
            max_retries: Maximum number of retries (uses default if None)
            retry_delay: Initial retry delay in seconds (uses default if None)
            **kwargs: Keyword arguments
            
        Returns:
            Function result or None if all retries fail
        """
        if max_retries is None:
            max_retries = self.max_retries
        if retry_delay is None:
            retry_delay = self.retry_delay
        
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                # Enforce rate limiting
                self._enforce_rate_limit()
                
                # Call function with circuit breaker protection
                result = self.circuit_breaker.call(func, *args, **kwargs)
                
                # Record success
                self._record_success()
                
                # Consume rate limit token
                self.rate_limiter.consume(self.CONNECTOR_NAME)
                
                return result
                
            except Exception as e:
                last_exception = e
                self._record_failure()
                
                self.logger.warning(
                    f"{self.CONNECTOR_NAME} error (attempt {attempt + 1}/{max_retries}): {e}"
                )
                
                # Exponential backoff
                if attempt < max_retries - 1:
                    delay = retry_delay * (self.backoff_multiplier ** attempt)
                    self.logger.debug(f"Retrying in {delay:.1f}s...")
                    time.sleep(delay)
        
        # All retries failed
        self.logger.error(
            f"All retries failed for {self.CONNECTOR_NAME}: {last_exception}"
        )
        return None
    
    def _circuit_breaker(self, func: Callable, *args, **kwargs) -> Optional[Any]:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result or None if circuit is open
            
        Raises:
            Exception: From the circuit breaker if it's open
        """
        try:
            return self.circuit_breaker.call(func, *args, **kwargs)
        except Exception as e:
            if "circuit breaker" in str(e).lower():
                self.logger.warning(f"Circuit breaker prevented call: {e}")
                return None
            raise
    
    def _record_success(self) -> None:
        """Record a successful request."""
        self.success_count += 1
        self.consecutive_failures = 0
        self.last_success_time = datetime.utcnow()
        self.last_request_time = datetime.utcnow()
    
    def _record_failure(self) -> None:
        """Record a failed request."""
        self.error_count += 1
        self.consecutive_failures += 1
        self.last_error_time = datetime.utcnow()
        self.last_request_time = datetime.utcnow()
        
        # Check if we should disable connector (circuit breaker logic)
        if self.consecutive_failures >= self.max_failures:
            self._disable_connector(
                f"Too many consecutive failures ({self.consecutive_failures})"
            )
    
    def _disable_connector(self, reason: str) -> None:
        """
        Disable the connector temporarily.
        
        Args:
            reason: Reason for disabling
        """
        self.is_enabled = False
        self.is_connected = False
        self.circuit_open_time = datetime.utcnow()
        
        self.logger.warning(
            f"🚫 {self.CONNECTOR_NAME} DISABLED: {reason}"
        )
        self.logger.warning(
            f"Connector will re-enable after {self.circuit_timeout}s"
        )
    
    def _check_circuit_timeout(self) -> bool:
        """
        Check if circuit timeout has elapsed and re-enable if so.
        
        Returns:
            True if connector was re-enabled, False otherwise
        """
        if self.is_enabled:
            return False
        
        if self.circuit_open_time is None:
            return False
        
        elapsed = (datetime.utcnow() - self.circuit_open_time).total_seconds()
        
        if elapsed >= self.circuit_timeout:
            self.is_enabled = True
            self.consecutive_failures = 0
            self.circuit_open_time = None
            self.logger.info(f"✅ {self.CONNECTOR_NAME} re-enabled after timeout")
            return True
        
        return False
    
    def fetch_current_price(self, symbol: str) -> Optional[float]:
        """
        Fetch current price for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            
        Returns:
            Current price or None if not available
        """
        raise NotImplementedError("Subclasses must implement fetch_current_price")
    
    def fetch_bars(
        self,
        symbol: str,
        timeframe: str,
        limit: Optional[int] = None
    ) -> Optional:
        """
        Fetch historical bars for a symbol.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe (e.g., '1h', '1d')
            limit: Number of bars to fetch
            
        Returns:
            DataFrame with OHLCV data or None if not available
        """
        raise NotImplementedError("Subclasses must implement fetch_bars")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get connector status.
        
        Returns:
            Dictionary with status information
        """
        avg_latency = (
            sum(self.latency_ms) / len(self.latency_ms)
            if self.latency_ms else 0
        )
        
        return {
            'connector': self.CONNECTOR_NAME,
            'is_connected': self.is_connected,
            'is_enabled': self.is_enabled,
            'request_count': self.request_count,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'consecutive_failures': self.consecutive_failures,
            'success_rate': (
                (self.success_count / self.request_count * 100)
                if self.request_count > 0 else 0
            ),
            'last_request_time': (
                self.last_request_time.isoformat()
                if self.last_request_time else None
            ),
            'last_success_time': (
                self.last_success_time.isoformat()
                if self.last_success_time else None
            ),
            'last_error_time': (
                self.last_error_time.isoformat()
                if self.last_error_time else None
            ),
            'circuit_breaker_state': self.circuit_breaker.get_state(),
            'circuit_open_time': (
                self.circuit_open_time.isoformat()
                if self.circuit_open_time else None
            ),
            'avg_latency_ms': round(avg_latency, 2),
        }
    
    def reset(self) -> None:
        """Reset connector state (for testing)."""
        self.is_enabled = True
        self.is_connected = False
        self.consecutive_failures = 0
        self.circuit_open_time = None
        self.circuit_breaker.reset()
        self.logger.info(f"{self.CONNECTOR_NAME} reset")