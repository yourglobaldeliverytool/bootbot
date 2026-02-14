"""
Abstract base classes and interfaces for the modular trading bot.
All strategies, indicators, and notifiers must implement these interfaces.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union
import pandas as pd
import numpy as np


class Indicator(ABC):
    """
    Abstract base class for all technical indicators.
    
    All indicators must implement the calculate and reset methods.
    Indicators should be stateless or explicitly manage their state.
    """
    
    def __init__(self, name: str, parameters: Optional[Dict[str, Any]] = None):
        """
        Initialize the indicator.
        
        Args:
            name: Unique identifier for the indicator
            parameters: Configuration parameters for the indicator
        """
        self.name = name
        self.parameters = parameters or {}
        self.logger = None
    
    @abstractmethod
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate the indicator values on the provided data.
        
        Args:
            data: OHLCV DataFrame with columns: ['open', 'high', 'low', 'close', 'volume']
            
        Returns:
            DataFrame with original data plus indicator column(s)
        """
        pass
    
    @abstractmethod
    def reset(self) -> None:
        """
        Reset the indicator to its initial state.
        Clears any cached values or internal state.
        """
        pass
    
    def get_name(self) -> str:
        """Return the name of the indicator."""
        return self.name
    
    def get_parameters(self) -> Dict[str, Any]:
        """Return the current parameters."""
        return self.parameters.copy()


class Strategy(ABC):
    """
    Abstract base class for all trading strategies.
    
    Strategies must implement generate_signal and set_parameters methods.
    Strategies can use any combination of indicators.
    """
    
    def __init__(self, name: str, parameters: Optional[Dict[str, Any]] = None):
        """
        Initialize the strategy.
        
        Args:
            name: Unique identifier for the strategy
            parameters: Configuration parameters for the strategy
        """
        self.name = name
        self.parameters = parameters or {}
        self.indicators: Dict[str, Indicator] = {}
        self.logger = None
    
    @abstractmethod
    def generate_signal(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate trading signal based on the provided data.
        
        Args:
            data: OHLCV DataFrame with columns: ['open', 'high', 'low', 'close', 'volume']
            
        Returns:
            Dictionary containing:
                - 'signal': str ('BUY', 'SELL', or 'HOLD')
                - 'confidence': float (0.0 to 1.0)
                - 'reason': str (explanation for the signal)
                - 'metadata': dict (additional strategy-specific data)
        """
        pass
    
    @abstractmethod
    def set_parameters(self, parameters: Dict[str, Any]) -> None:
        """
        Update strategy parameters dynamically.
        
        Args:
            parameters: Dictionary of parameter names and values to update
        """
        pass
    
    def add_indicator(self, indicator: Indicator) -> None:
        """
        Add an indicator to the strategy.
        
        Args:
            indicator: Indicator instance to add
        """
        self.indicators[indicator.get_name()] = indicator
    
    def get_name(self) -> str:
        """Return the name of the strategy."""
        return self.name
    
    def get_parameters(self) -> Dict[str, Any]:
        """Return the current parameters."""
        return self.parameters.copy()
    
    def get_indicators(self) -> Dict[str, Indicator]:
        """Return all registered indicators."""
        return self.indicators.copy()
    
    def reset(self) -> None:
        """Reset the strategy and all its indicators."""
        for indicator in self.indicators.values():
            indicator.reset()


class Notifier(ABC):
    """
    Abstract base class for all notification systems.
    
    Notifiers must implement the send_notification method.
    Different notification channels (Telegram, Email, Slack) inherit from this.
    """
    
    def __init__(self, name: str, parameters: Optional[Dict[str, Any]] = None):
        """
        Initialize the notifier.
        
        Args:
            name: Unique identifier for the notifier
            parameters: Configuration parameters for the notifier
        """
        self.name = name
        self.parameters = parameters or {}
        self.enabled = True
        self.logger = None
    
    @abstractmethod
    def send_notification(self, message: str, data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send a notification message.
        
        Args:
            message: The notification message to send
            data: Optional additional data to include with the notification
            
        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        pass
    
    def enable(self) -> None:
        """Enable this notifier."""
        self.enabled = True
    
    def disable(self) -> None:
        """Disable this notifier."""
        self.enabled = False
    
    def is_enabled(self) -> bool:
        """Check if this notifier is enabled."""
        return self.enabled
    
    def get_name(self) -> str:
        """Return the name of the notifier."""
        return self.name
    
    def get_parameters(self) -> Dict[str, Any]:
        """Return the current parameters."""
        return self.parameters.copy()


class Signal(ABC):
    """
    Abstract base class for signal objects.
    
    Signals represent trading decisions with associated metadata.
    """
    
    def __init__(self, strategy_name: str, signal_type: str, confidence: float, 
                 timestamp: pd.Timestamp, reason: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize a signal.
        
        Args:
            strategy_name: Name of the strategy that generated this signal
            signal_type: Type of signal ('BUY', 'SELL', 'HOLD')
            confidence: Confidence level (0.0 to 1.0)
            timestamp: When the signal was generated
            reason: Explanation for the signal
            metadata: Additional signal-specific data
        """
        self.strategy_name = strategy_name
        self.signal_type = signal_type
        self.confidence = confidence
        self.timestamp = timestamp
        self.reason = reason
        self.metadata = metadata or {}
    
    def get_signal_type(self) -> str:
        """Return the signal type."""
        return self.signal_type
    
    def get_confidence(self) -> float:
        """Return the confidence level."""
        return self.confidence
    
    def get_timestamp(self) -> pd.Timestamp:
        """Return the timestamp."""
        return self.timestamp
    
    def get_reason(self) -> str:
        """Return the reason for the signal."""
        return self.reason
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return the metadata."""
        return self.metadata.copy()
    
    def __repr__(self) -> str:
        """String representation of the signal."""
        return (f"Signal(strategy={self.strategy_name}, type={self.signal_type}, "
                f"confidence={self.confidence:.2f}, time={self.timestamp})")