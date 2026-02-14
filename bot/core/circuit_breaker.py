"""
Circuit breaker pattern implementation for connectors.
Prevents cascading failures by temporarily disabling failing connectors.
"""

import time
import logging
from typing import Optional, Callable, Any
from functools import wraps


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Circuit breaker implementation for fault tolerance.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Circuit is open, requests fail immediately
    - HALF_OPEN: Testing if service has recovered
    
    Transitions:
    - CLOSED → OPEN: After K consecutive failures
    - OPEN → HALF_OPEN: After timeout period
    - HALF_OPEN → CLOSED: On successful request
    - HALF_OPEN → OPEN: On failed request
    """
    
    def __init__(
        self,
        name: str,
        max_failures: int = 5,
        timeout: int = 300,
        reset_timeout: int = 60
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Name of the circuit breaker
            max_failures: Max consecutive failures before opening (default 5)
            timeout: How long to stay open before attempting recovery (default 300s)
            reset_timeout: How long to stay in half-open state (default 60s)
        """
        self.name = name
        self.max_failures = max_failures
        self.timeout = timeout
        self.reset_timeout = reset_timeout
        self.logger = logging.getLogger(__name__)
        
        # State
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self.failure_count = 0
        self.last_failure_time = None
        self.opened_at = None
        self.last_success_time = None
        
        # Statistics
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerError: If circuit is open
        """
        self.total_calls += 1
        
        # Check circuit state
        if self.state == 'OPEN':
            if self._should_attempt_reset():
                self.state = 'HALF_OPEN'
                self.logger.info(f"⚡ Circuit {self.name}: OPEN → HALF_OPEN (testing recovery)")
            else:
                self.failed_calls += 1
                raise CircuitBreakerError(
                    f"Circuit breaker {self.name} is OPEN. "
                    f"Failing fast to prevent cascading failures."
                )
        
        try:
            # Call the function
            result = func(*args, **kwargs)
            
            # Success
            self._on_success()
            self.successful_calls += 1
            
            return result
            
        except Exception as e:
            # Failure
            self._on_failure()
            self.failed_calls += 1
            
            # If circuit is open, raise CircuitBreakerError
            if self.state == 'OPEN':
                raise CircuitBreakerError(
                    f"Circuit breaker {self.name} opened after exception: {e}"
                ) from e
            
            # Otherwise, re-raise the original exception
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.opened_at is None:
            return False
        
        elapsed = time.time() - self.opened_at
        return elapsed >= self.timeout
    
    def _on_success(self) -> None:
        """Handle successful call."""
        self.last_success_time = time.time()
        
        if self.state == 'HALF_OPEN':
            # Reset to closed on success
            self.state = 'CLOSED'
            self.failure_count = 0
            self.opened_at = None
            self.logger.info(f"✅ Circuit {self.name}: HALF_OPEN → CLOSED (service recovered)")
    
    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == 'CLOSED':
            # Open circuit after max failures
            if self.failure_count >= self.max_failures:
                self.state = 'OPEN'
                self.opened_at = time.time()
                self.logger.warning(
                    f"🚫 Circuit {self.name}: CLOSED → OPEN "
                    f"({self.failure_count} failures)"
                )
        elif self.state == 'HALF_OPEN':
            # Re-open circuit on failure
            self.state = 'OPEN'
            self.opened_at = time.time()
            self.logger.warning(
                f"🚫 Circuit {self.name}: HALF_OPEN → OPEN "
                f"(recovery test failed)"
            )
    
    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        self.state = 'CLOSED'
        self.failure_count = 0
        self.opened_at = None
        self.logger.info(f"🔄 Circuit {self.name} manually reset to CLOSED")
    
    def get_state(self) -> str:
        """Get current circuit state."""
        return self.state
    
    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            'name': self.name,
            'state': self.state,
            'failure_count': self.failure_count,
            'max_failures': self.max_failures,
            'total_calls': self.total_calls,
            'successful_calls': self.successful_calls,
            'failed_calls': self.failed_calls,
            'last_failure_time': self.last_failure_time,
            'last_success_time': self.last_success_time,
            'opened_at': self.opened_at,
        }


def circuit_breaker(
    name: str,
    max_failures: int = 5,
    timeout: int = 300,
    reset_timeout: int = 60
):
    """
    Decorator to apply circuit breaker to a function.
    
    Args:
        name: Name of the circuit breaker
        max_failures: Max consecutive failures before opening
        timeout: How long to stay open before attempting recovery
        reset_timeout: How long to stay in half-open state
        
    Example:
        @circuit_breaker("alpaca_api", max_failures=3, timeout=60)
        def fetch_price():
            # API call
            pass
    """
    # Create circuit breaker instance per decorated function
    cb = CircuitBreaker(name, max_failures, timeout, reset_timeout)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return cb.call(func, *args, **kwargs)
        return wrapper
    
    return decorator


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""
    
    def __init__(self):
        self._breakers: dict = {}
        self.logger = logging.getLogger(__name__)
    
    def get_or_create(
        self,
        name: str,
        max_failures: int = 5,
        timeout: int = 300,
        reset_timeout: int = 60
    ) -> CircuitBreaker:
        """Get existing circuit breaker or create new one."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name, max_failures, timeout, reset_timeout
            )
            self.logger.debug(f"Created circuit breaker: {name}")
        return self._breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self._breakers.get(name)
    
    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()
        self.logger.info("All circuit breakers reset")
    
    def get_all_stats(self) -> dict:
        """Get statistics for all circuit breakers."""
        return {
            name: breaker.get_stats()
            for name, breaker in self._breakers.items()
        }


# Global circuit breaker registry
_global_registry: Optional[CircuitBreakerRegistry] = None


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = CircuitBreakerRegistry()
    return _global_registry