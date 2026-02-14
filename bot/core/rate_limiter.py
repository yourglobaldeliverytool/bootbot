"""
Rate limiter implementation to prevent API rate limiting (429 errors).
Implements token bucket algorithm with per-API tracking.
"""

import time
import logging
from typing import Dict, Optional
from collections import deque


class RateLimiter:
    """
    Rate limiter using token bucket algorithm.
    
    Prevents API rate limiting by tracking requests per endpoint
    and throttling when limits are approached.
    
    Algorithm:
    - Each API has a capacity (max requests) and refill rate
    - Requests consume tokens from the bucket
    - Tokens refill over time
    - If bucket is empty, request is blocked/throttled
    """
    
    def __init__(self):
        """Initialize rate limiter."""
        self.logger = logging.getLogger(__name__)
        
        # Rate limits per API endpoint
        # Format: {endpoint: {'capacity': int, 'refill_rate': float, 'tokens': float, 'last_refill': float}}
        self._limits: Dict[str, Dict[str, float]] = {}
        
        # Default limits for common public APIs
        self._default_limits = {
            'coingecko': {'capacity': 10, 'refill_rate': 1/10},  # 10 req/min
            'coincap': {'capacity': 30, 'refill_rate': 1/2},      # 30 req/min
            'yahoo_finance': {'capacity': 60, 'refill_rate': 1},   # 60 req/min
            'alpaca': {'capacity': 200, 'refill_rate': 200/60},    # 200 req/min
            'polygon': {'capacity': 5, 'refill_rate': 5/60},       # 5 req/min (free tier)
            'metals_live': {'capacity': 10, 'refill_rate': 1/10},  # 10 req/min
            'default': {'capacity': 60, 'refill_rate': 1},         # 60 req/min
        }
        
        # Request history for sliding window (used for more precise limiting)
        self._history: Dict[str, deque] = {}
        
        # Statistics
        self._stats: Dict[str, Dict[str, int]] = {}
    
    def add_limit(self, endpoint: str, capacity: int, refill_rate: float) -> None:
        """
        Add or update rate limit for an endpoint.
        
        Args:
            endpoint: API endpoint name
            capacity: Maximum requests per time window
            refill_rate: Requests per second to refill tokens
        """
        self._limits[endpoint] = {
            'capacity': float(capacity),
            'refill_rate': refill_rate,
            'tokens': float(capacity),
            'last_refill': time.time(),
        }
        self._history[endpoint] = deque()
        self._stats[endpoint] = {'allowed': 0, 'blocked': 0, 'throttled': 0}
        self.logger.info(f"Added rate limit for {endpoint}: {capacity} req, {refill_rate:.2f} req/s")
    
    def get_limit(self, endpoint: str) -> Optional[Dict[str, float]]:
        """Get rate limit config for endpoint."""
        if endpoint in self._limits:
            return self._limits[endpoint]
        elif endpoint in self._default_limits:
            # Initialize from defaults
            default = self._default_limits[endpoint]
            self.add_limit(endpoint, int(default['capacity']), default['refill_rate'])
            return self._limits[endpoint]
        else:
            # Use default
            return None
    
    def _refill_tokens(self, endpoint: str) -> None:
        """Refill tokens for an endpoint based on elapsed time."""
        if endpoint not in self._limits:
            return
        
        limit = self._limits[endpoint]
        now = time.time()
        elapsed = now - limit['last_refill']
        
        # Refill tokens
        tokens_to_add = elapsed * limit['refill_rate']
        limit['tokens'] = min(limit['capacity'], limit['tokens'] + tokens_to_add)
        limit['last_refill'] = now
    
    def can_request(self, endpoint: str, cost: int = 1) -> bool:
        """
        Check if a request can be made without exceeding rate limits.
        
        Args:
            endpoint: API endpoint name
            cost: Request cost (default 1)
            
        Returns:
            True if request can proceed, False if rate limited
        """
        limit = self.get_limit(endpoint)
        
        if not limit:
            # No limit set, allow request
            return True
        
        # Refill tokens
        self._refill_tokens(endpoint)
        
        # Check if we have enough tokens
        if limit['tokens'] >= cost:
            return True
        else:
            self.logger.debug(f"Rate limited for {endpoint}: {limit['tokens']:.1f} tokens")
            return False
    
    def consume(self, endpoint: str, cost: int = 1) -> bool:
        """
        Consume tokens for a request.
        
        Args:
            endpoint: API endpoint name
            cost: Request cost (default 1)
            
        Returns:
            True if request was allowed, False if rate limited
        """
        limit = self.get_limit(endpoint)
        
        if not limit:
            # No limit set, allow request
            return True
        
        # Refill tokens first
        self._refill_tokens(endpoint)
        
        # Check and consume
        if limit['tokens'] >= cost:
            limit['tokens'] -= cost
            
            # Track statistics
            if endpoint not in self._stats:
                self._stats[endpoint] = {'allowed': 0, 'blocked': 0, 'throttled': 0}
            self._stats[endpoint]['allowed'] += 1
            
            # Add to history
            if endpoint not in self._history:
                self._history[endpoint] = deque()
            self._history[endpoint].append(time.time())
            
            return True
        else:
            # Rate limited
            if endpoint not in self._stats:
                self._stats[endpoint] = {'allowed': 0, 'blocked': 0, 'throttled': 0}
            self._stats[endpoint]['blocked'] += 1
            
            self.logger.warning(
                f"🚫 Rate limit hit for {endpoint}: "
                f"{limit['tokens']:.1f}/{limit['capacity']} tokens available"
            )
            
            return False
    
    def wait_until_available(self, endpoint: str, cost: int = 1) -> float:
        """
        Calculate wait time until request can be made.
        
        Args:
            endpoint: API endpoint name
            cost: Request cost (default 1)
            
        Returns:
            Seconds to wait before request can proceed
        """
        limit = self.get_limit(endpoint)
        
        if not limit:
            return 0.0
        
        # Refill tokens
        self._refill_tokens(endpoint)
        
        if limit['tokens'] >= cost:
            return 0.0
        else:
            # Calculate time to refill
            tokens_needed = cost - limit['tokens']
            wait_time = tokens_needed / limit['refill_rate']
            return max(0, wait_time)
    
    def get_remaining(self, endpoint: str) -> Optional[int]:
        """Get remaining requests for endpoint."""
        limit = self.get_limit(endpoint)
        
        if not limit:
            return None
        
        # Refill tokens
        self._refill_tokens(endpoint)
        
        return int(limit['tokens'])
    
    def get_stats(self, endpoint: Optional[str] = None) -> Dict:
        """
        Get rate limiter statistics.
        
        Args:
            endpoint: Specific endpoint, or None for all
            
        Returns:
            Statistics dictionary
        """
        if endpoint:
            if endpoint in self._stats:
                return self._stats[endpoint].copy()
            return {}
        
        # Return all stats
        return {
            ep: stats.copy()
            for ep, stats in self._stats.items()
        }
    
    def reset(self, endpoint: Optional[str] = None) -> None:
        """
        Reset rate limiter for endpoint or all endpoints.
        
        Args:
            endpoint: Specific endpoint, or None for all
        """
        if endpoint:
            if endpoint in self._limits:
                self._limits[endpoint]['tokens'] = self._limits[endpoint]['capacity']
                self._limits[endpoint]['last_refill'] = time.time()
                if endpoint in self._history:
                    self._history[endpoint].clear()
                self.logger.debug(f"Reset rate limiter for {endpoint}")
        else:
            # Reset all
            for ep in self._limits:
                self._limits[ep]['tokens'] = self._limits[ep]['capacity']
                self._limits[ep]['last_refill'] = time.time()
            for ep in self._history:
                self._history[ep].clear()
            self.logger.debug("Reset all rate limiters")


class GlobalRateLimiter:
    """Singleton global rate limiter instance."""
    
    _instance: Optional[RateLimiter] = None
    
    @classmethod
    def get(cls) -> RateLimiter:
        """Get or create the global rate limiter instance."""
        if cls._instance is None:
            cls._instance = RateLimiter()
            # Initialize default limits
            for endpoint, config in cls._instance._default_limits.items():
                if endpoint != 'default':
                    cls._instance.add_limit(
                        endpoint,
                        int(config['capacity']),
                        config['refill_rate']
                    )
        return cls._instance


def rate_limit(endpoint: str, cost: int = 1, wait: bool = True):
    """
    Decorator to apply rate limiting to a function.
    
    Args:
        endpoint: API endpoint name
        cost: Request cost (default 1)
        wait: If True, wait until available (default True)
        
    Example:
        @rate_limit("coingecko", cost=1, wait=True)
        def fetch_price():
            # API call
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            limiter = GlobalRateLimiter.get()
            
            # Check if we can make the request
            if not limiter.can_request(endpoint, cost):
                if wait:
                    # Wait until available
                    wait_time = limiter.wait_until_available(endpoint, cost)
                    if wait_time > 0:
                        logging.getLogger(__name__).info(
                            f"Rate limited for {endpoint}, waiting {wait_time:.1f}s"
                        )
                        time.sleep(wait_time)
                else:
                    raise Exception(f"Rate limit exceeded for {endpoint}")
            
            # Consume tokens
            if not limiter.consume(endpoint, cost):
                if not wait:
                    raise Exception(f"Rate limit exceeded for {endpoint}")
                # Should not happen if we waited
                time.sleep(0.1)
                limiter.consume(endpoint, cost)
            
            # Call function
            return func(*args, **kwargs)
        
        return wrapper
    return decorator