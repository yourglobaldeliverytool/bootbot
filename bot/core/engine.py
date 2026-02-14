"""
Core trading engine that orchestrates strategies, indicators, and notifications.
Manages the trading lifecycle and coordinates between components.
"""

from typing import Dict, List, Optional, Any
import pandas as pd
import logging
from datetime import datetime

from bot.core.interfaces import Strategy, Indicator, Notifier, Signal
from bot.core.registry import StrategyRegistry, IndicatorRegistry, NotifierRegistry


class TradingEngine:
    """
    Main trading engine that coordinates all trading components.
    
    Responsibilities:
    - Load and manage strategies via registry
    - Load and manage indicators via registry
    - Execute strategies and generate signals
    - Route signals to notifiers
    - Maintain state and configuration
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the trading engine.
        
        Args:
            config: Configuration dictionary for the engine
        """
        self.config = config or {}
        self.logger = self._setup_logger()
        
        # Initialize registries
        self.strategy_registry = StrategyRegistry()
        self.indicator_registry = IndicatorRegistry()
        self.notifier_registry = NotifierRegistry()
        
        # Active components
        self.active_strategies: Dict[str, Strategy] = {}
        self.active_indicators: Dict[str, Indicator] = {}
        self.active_notifiers: Dict[str, Notifier] = {}
        
        # Engine state
        self.is_running = False
        self.last_execution: Optional[datetime] = None
        self.execution_count = 0
        
        self.logger.info("TradingEngine initialized")
    
    def _setup_logger(self) -> logging.Logger:
        """
        Set up the logger for the engine.
        
        Returns:
            Configured logger instance
        """
        logger = logging.getLogger("TradingEngine")
        logger.setLevel(getattr(logging, self.config.get('log_level', 'INFO')))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def load_strategy(self, strategy_name: str, parameters: Optional[Dict[str, Any]] = None) -> bool:
        """
        Load a strategy from the registry and create an instance.
        
        Args:
            strategy_name: Name of the strategy to load
            parameters: Optional parameters for the strategy
            
        Returns:
            True if strategy loaded successfully, False otherwise
        """
        strategy = self.strategy_registry.create_instance(strategy_name, parameters)
        if strategy is None:
            self.logger.error(f"Failed to load strategy: {strategy_name}")
            return False
        
        strategy.logger = self.logger
        self.active_strategies[strategy_name] = strategy
        self.logger.info(f"Strategy loaded: {strategy_name}")
        return True
    
    def load_indicator(self, indicator_name: str, parameters: Optional[Dict[str, Any]] = None) -> bool:
        """
        Load an indicator from the registry and create an instance.
        
        Args:
            indicator_name: Name of the indicator to load
            parameters: Optional parameters for the indicator
            
        Returns:
            True if indicator loaded successfully, False otherwise
        """
        indicator = self.indicator_registry.create_instance(indicator_name, parameters)
        if indicator is None:
            self.logger.error(f"Failed to load indicator: {indicator_name}")
            return False
        
        indicator.logger = self.logger
        self.active_indicators[indicator_name] = indicator
        self.logger.info(f"Indicator loaded: {indicator_name}")
        return True
    
    def load_notifier(self, notifier_name: str, parameters: Optional[Dict[str, Any]] = None) -> bool:
        """
        Load a notifier from the registry and create an instance.
        
        Args:
            notifier_name: Name of the notifier to load
            parameters: Optional parameters for the notifier
            
        Returns:
            True if notifier loaded successfully, False otherwise
        """
        notifier = self.notifier_registry.create_instance(notifier_name, parameters)
        if notifier is None:
            self.logger.error(f"Failed to load notifier: {notifier_name}")
            return False
        
        notifier.logger = self.logger
        self.active_notifiers[notifier_name] = notifier
        self.logger.info(f"Notifier loaded: {notifier_name}")
        return True
    
    def attach_indicator_to_strategy(self, indicator_name: str, strategy_name: str) -> bool:
        """
        Attach an indicator to a strategy.
        
        Args:
            indicator_name: Name of the indicator to attach
            strategy_name: Name of the strategy to attach to
            
        Returns:
            True if attached successfully, False otherwise
        """
        if indicator_name not in self.active_indicators:
            self.logger.error(f"Indicator not found: {indicator_name}")
            return False
        
        if strategy_name not in self.active_strategies:
            self.logger.error(f"Strategy not found: {strategy_name}")
            return False
        
        self.active_strategies[strategy_name].add_indicator(
            self.active_indicators[indicator_name]
        )
        self.logger.info(f"Attached indicator '{indicator_name}' to strategy '{strategy_name}'")
        return True
    
    def execute_strategies(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Execute all active strategies on the provided data.
        
        Args:
            data: OHLCV DataFrame with columns: ['open', 'high', 'low', 'close', 'volume']
            
        Returns:
            List of signal dictionaries generated by strategies
        """
        signals = []
        self.execution_count += 1
        self.last_execution = datetime.now()
        
        self.logger.info(f"Executing {len(self.active_strategies)} strategies")
        
        for strategy_name, strategy in self.active_strategies.items():
            try:
                signal = strategy.generate_signal(data)
                signals.append(signal)
                self.logger.debug(
                    f"Strategy '{strategy_name}' generated signal: {signal.get('signal', 'N/A')}"
                )
                
                # Send notifications if enabled
                self._send_signal_notifications(signal)
                
            except Exception as e:
                self.logger.error(f"Error executing strategy '{strategy_name}': {e}")
        
        self.logger.info(f"Generated {len(signals)} signals")
        return signals
    
    def _send_signal_notifications(self, signal: Dict[str, Any]) -> None:
        """
        Send notifications for a signal through all active notifiers.
        
        Args:
            signal: Signal dictionary to notify about
        """
        for notifier_name, notifier in self.active_notifiers.items():
            if notifier.is_enabled():
                try:
                    message = self._format_signal_message(signal)
                    success = notifier.send_notification(message, signal)
                    if success:
                        self.logger.debug(f"Notification sent via {notifier_name}")
                    else:
                        self.logger.warning(f"Failed to send notification via {notifier_name}")
                except Exception as e:
                    self.logger.error(f"Error sending notification via {notifier_name}: {e}")
    
    def _format_signal_message(self, signal: Dict[str, Any]) -> str:
        """
        Format a signal into a readable message.
        
        Args:
            signal: Signal dictionary
            
        Returns:
            Formatted message string
        """
        return (
            f"📊 Trading Signal\n"
            f"Strategy: {signal.get('strategy_name', 'Unknown')}\n"
            f"Signal: {signal.get('signal', 'N/A')}\n"
            f"Confidence: {signal.get('confidence', 0):.2%}\n"
            f"Reason: {signal.get('reason', 'N/A')}\n"
            f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    
    def get_active_strategies(self) -> List[str]:
        """
        Get list of active strategy names.
        
        Returns:
            List of active strategy names
        """
        return list(self.active_strategies.keys())
    
    def get_active_indicators(self) -> List[str]:
        """
        Get list of active indicator names.
        
        Returns:
            List of active indicator names
        """
        return list(self.active_indicators.keys())
    
    def get_active_notifiers(self) -> List[str]:
        """
        Get list of active notifier names.
        
        Returns:
            List of active notifier names
        """
        return list(self.active_notifiers.keys())
    
    def reset_strategies(self) -> None:
        """Reset all active strategies."""
        for strategy in self.active_strategies.values():
            strategy.reset()
        self.logger.info("All strategies reset")
    
    def reset_indicators(self) -> None:
        """Reset all active indicators."""
        for indicator in self.active_indicators.values():
            indicator.reset()
        self.logger.info("All indicators reset")
    
    def start(self) -> None:
        """Start the trading engine."""
        self.is_running = True
        self.logger.info("TradingEngine started")
    
    def stop(self) -> None:
        """Stop the trading engine."""
        self.is_running = False
        self.logger.info("TradingEngine stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the engine.
        
        Returns:
            Dictionary containing engine status information
        """
        return {
            'is_running': self.is_running,
            'active_strategies': len(self.active_strategies),
            'active_indicators': len(self.active_indicators),
            'active_notifiers': len(self.active_notifiers),
            'execution_count': self.execution_count,
            'last_execution': self.last_execution.isoformat() if self.last_execution else None,
        }