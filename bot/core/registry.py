"""
Registry system for dynamic loading and management of strategies and indicators.
Allows for pluggable, optional module loading at runtime.
Implements decorator-based auto-registration.
"""

import logging
from typing import Dict, Type, Optional, List, Any
import importlib
import inspect
from bot.core.interfaces import Strategy, Indicator, Notifier


# Decorator for automatic strategy registration
def register_strategy(name: Optional[str] = None):
    """
    Decorator to automatically register a strategy class.
    
    Args:
        name: Optional custom name for the strategy (defaults to class name)
        
    Usage:
        @register_strategy("my_strategy")
        class MyStrategy(Strategy):
            pass
    """
    def decorator(cls: Type[Strategy]):
        # Import registry here to avoid circular imports
        from bot.core.registry import StrategyRegistry
        registry = StrategyRegistry.get_instance()
        
        strategy_name = name or cls.__name__
        registry.register(strategy_name, cls)
        
        return cls
    return decorator


# Decorator for automatic indicator registration
def register_indicator(name: Optional[str] = None):
    """
    Decorator to automatically register an indicator class.
    
    Args:
        name: Optional custom name for the indicator (defaults to class name)
        
    Usage:
        @register_indicator("my_indicator")
        class MyIndicator(Indicator):
            pass
    """
    def decorator(cls: Type[Indicator]):
        from bot.core.registry import IndicatorRegistry
        registry = IndicatorRegistry.get_instance()
        
        indicator_name = name or cls.__name__
        registry.register(indicator_name, cls)
        
        return cls
    return decorator


class BaseRegistry:
    """
    Base registry class for managing plugin-like components.
    Provides methods for registering, retrieving, and listing components.
    """
    
    _instances: Dict[str, 'BaseRegistry'] = {}
    
    @classmethod
    def get_instance(cls, registry_name: str = "default"):
        """Get or create the singleton instance."""
        instance_key = f"{cls.__name__}_{registry_name}"
        if instance_key not in cls._instances:
            cls._instances[instance_key] = cls(registry_name)
        return cls._instances[instance_key]
    
    @classmethod
    def reset(cls):
        """Reset all instances (for testing)."""
        cls._instances.clear()
    
    def __init__(self, registry_name: str):
        """
        Initialize the registry.
        
        Args:
            registry_name: Name of the registry (for logging purposes)
        """
        self.registry_name = registry_name
        self._registry: Dict[str, Type] = {}
        self.logger = logging.getLogger(__name__)
    
    def register(self, name: str, component_class: Type) -> None:
        """
        Register a component class.
        
        Args:
            name: Unique identifier for the component
            component_class: Class to register
            
        Raises:
            ValueError: If component_class is not a valid subclass
        """
        self._registry[name] = component_class
        self.logger.debug(f"Registered {self.registry_name}: {name}")
    
    def get(self, name: str) -> Optional[Type]:
        """
        Retrieve a registered component class by name.
        
        Args:
            name: Name of the component to retrieve
            
        Returns:
            Component class if found, None otherwise
        """
        return self._registry.get(name)
    
    def exists(self, name: str) -> bool:
        """
        Check if a component is registered.
        
        Args:
            name: Name to check
            
        Returns:
            True if registered, False otherwise
        """
        return name in self._registry
    
    def list_all(self) -> List[str]:
        """
        List all registered component names.
        
        Returns:
            List of registered names
        """
        return list(self._registry.keys())
    
    def get_all(self) -> Dict[str, Type]:
        """
        Get all registered components.
        
        Returns:
            Dictionary of all registered components
        """
        return self._registry.copy()
    
    def unregister(self, name: str) -> bool:
        """
        Unregister a component.
        
        Args:
            name: Name of the component to unregister
            
        Returns:
            True if component was unregistered, False if not found
        """
        if name in self._registry:
            del self._registry[name]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all registered components."""
        self._registry.clear()
    
    def count(self) -> int:
        """Get the number of registered components."""
        return len(self._registry)


class StrategyRegistry(BaseRegistry):
    """
    Registry for managing trading strategies.
    Allows dynamic loading and retrieval of strategy classes.
    """
    
    def __init__(self, registry_name: str = "StrategyRegistry"):
        """Initialize the strategy registry."""
        super().__init__(registry_name)
        self.logger = logging.getLogger(f"{__name__}.StrategyRegistry")
    
    def register(self, name: str, strategy_class: Type[Strategy]) -> None:
        """
        Register a strategy class.
        
        Args:
            name: Unique identifier for the strategy
            strategy_class: Strategy class to register
            
        Raises:
            TypeError: If strategy_class is not a subclass of Strategy
        """
        if not inspect.isclass(strategy_class):
            raise TypeError(f"{strategy_class} must be a class, not {type(strategy_class)}")
        
        if not issubclass(strategy_class, Strategy):
            raise TypeError(f"{strategy_class} must be a subclass of Strategy")
        
        super().register(name, strategy_class)
        self.logger.info(f"✅ Registered strategy: {name}")
    
    def create_instance(self, name: str, parameters: Optional[Dict[str, Any]] = None) -> Optional[Strategy]:
        """
        Create an instance of a registered strategy.
        
        Args:
            name: Name of the strategy to instantiate
            parameters: Optional parameters to pass to the strategy constructor
            
        Returns:
            Strategy instance if found and successfully created, None otherwise
        """
        strategy_class = self.get(name)
        if strategy_class is None:
            self.logger.warning(f"Strategy not found in registry: {name}")
            return None
        
        try:
            return strategy_class(name, parameters or {})
        except Exception as e:
            self.logger.error(f"Failed to create instance of strategy {name}: {e}")
            return None
    
    def load_from_module(self, module_path: str) -> int:
        """
        Dynamically load and register all strategies from a module.
        
        Args:
            module_path: Python module path (e.g., 'bot.strategies.trend_following')
            
        Returns:
            Number of strategies loaded
        """
        try:
            module = importlib.import_module(module_path)
        except ImportError as e:
            self.logger.error(f"Failed to import module {module_path}: {e}")
            return 0
        
        count = 0
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (obj is not Strategy and 
                issubclass(obj, Strategy) and 
                obj.__module__ == module_path):
                # Use class name or STRATEGY_NAME attribute if present
                strategy_name = getattr(obj, 'STRATEGY_NAME', obj.__name__)
                self.register(strategy_name, obj)
                count += 1
        
        self.logger.info(f"Loaded {count} strategies from {module_path}")
        return count
    
    def load_all_strategies(self) -> int:
        """
        Load all strategies from the bot.strategies package.
        
        Returns:
            Total number of strategies loaded
        """
        import os
        import glob
        
        total = 0
        strategies_dir = '/workspace/bot/strategies'
        
        if not os.path.exists(strategies_dir):
            self.logger.warning(f"Strategies directory not found: {strategies_dir}")
            return 0
        
        # Find all strategy modules
        module_files = glob.glob(os.path.join(strategies_dir, '*.py'))
        
        for module_path in module_files:
            filename = os.path.basename(module_path)
            module_name = filename.replace('.py', '')
            
            # Skip __init__ and private files
            if module_name.startswith('_') or module_name == '__init__':
                continue
            
            full_module_path = f'bot.strategies.{module_name}'
            
            try:
                count = self.load_from_module(full_module_path)
                total += count
            except Exception as e:
                self.logger.warning(f"Could not load strategies from {module_name}: {e}")
        
        self.logger.info(f"✅ Total strategies loaded: {total}")
        return total


class IndicatorRegistry(BaseRegistry):
    """
    Registry for managing technical indicators.
    Allows dynamic loading and retrieval of indicator classes.
    """
    
    def __init__(self, registry_name: str = "IndicatorRegistry"):
        """Initialize the indicator registry."""
        super().__init__(registry_name)
        self.logger = logging.getLogger(f"{__name__}.IndicatorRegistry")
    
    def register(self, name: str, indicator_class: Type[Indicator]) -> None:
        """
        Register an indicator class.
        
        Args:
            name: Unique identifier for the indicator
            indicator_class: Indicator class to register
            
        Raises:
            TypeError: If indicator_class is not a subclass of Indicator
        """
        if not inspect.isclass(indicator_class):
            raise TypeError(f"{indicator_class} must be a class, not {type(indicator_class)}")
        
        if not issubclass(indicator_class, Indicator):
            raise TypeError(f"{indicator_class} must be a subclass of Indicator")
        
        super().register(name, indicator_class)
        self.logger.debug(f"Registered indicator: {name}")
    
    def create_instance(self, name: str, parameters: Optional[Dict[str, Any]] = None) -> Optional[Indicator]:
        """
        Create an instance of a registered indicator.
        
        Args:
            name: Name of the indicator to instantiate
            parameters: Optional parameters to pass to the indicator constructor
            
        Returns:
            Indicator instance if found and successfully created, None otherwise
        """
        indicator_class = self.get(name)
        if indicator_class is None:
            self.logger.warning(f"Indicator not found in registry: {name}")
            return None
        return indicator_class(name, parameters or {})
    
    def load_from_module(self, module_path: str) -> int:
        """
        Dynamically load and register all indicators from a module.
        
        Args:
            module_path: Python module path (e.g., 'bot.indicators.sma')
            
        Returns:
            Number of indicators loaded
        """
        module = importlib.import_module(module_path)
        count = 0
        
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (obj is not Indicator and 
                issubclass(obj, Indicator) and 
                obj.__module__ == module_path):
                indicator_name = getattr(obj, 'INDICATOR_NAME', obj.__name__)
                self.register(indicator_name, obj)
                count += 1
        
        return count
    
    def load_all_indicators(self) -> int:
        """
        Load all indicators from the bot.indicators package.
        
        Returns:
            Total number of indicators loaded
        """
        import os
        import glob
        
        total = 0
        indicators_dir = '/workspace/bot/indicators'
        
        if not os.path.exists(indicators_dir):
            return 0
        
        module_files = glob.glob(os.path.join(indicators_dir, '*.py'))
        
        for module_path in module_files:
            filename = os.path.basename(module_path)
            module_name = filename.replace('.py', '')
            
            if module_name.startswith('_') or module_name == '__init__':
                continue
            
            full_module_path = f'bot.indicators.{module_name}'
            
            try:
                count = self.load_from_module(full_module_path)
                total += count
            except Exception as e:
                self.logger.warning(f"Could not load indicators from {module_name}: {e}")
        
        self.logger.info(f"✅ Total indicators loaded: {total}")
        return total


class NotifierRegistry(BaseRegistry):
    """
    Registry for managing notification systems.
    Allows dynamic loading and retrieval of notifier classes.
    """
    
    def __init__(self):
        """Initialize the notifier registry."""
        super().__init__("NotifierRegistry")
        self.logger = logging.getLogger(f"{__name__}.NotifierRegistry")
    
    def register(self, name: str, notifier_class: Type[Notifier]) -> None:
        """
        Register a notifier class.
        
        Args:
            name: Unique identifier for the notifier
            notifier_class: Notifier class to register
            
        Raises:
            TypeError: If notifier_class is not a subclass of Notifier
        """
        if not inspect.isclass(notifier_class):
            raise TypeError(f"{notifier_class} must be a class, not {type(notifier_class)}")
        
        if not issubclass(notifier_class, Notifier):
            raise TypeError(f"{notifier_class} must be a subclass of Notifier")
        
        super().register(name, notifier_class)
        self.logger.debug(f"Registered notifier: {name}")
    
    def create_instance(self, name: str, parameters: Optional[Dict[str, Any]] = None) -> Optional[Notifier]:
        """
        Create an instance of a registered notifier.
        
        Args:
            name: Name of the notifier to instantiate
            parameters: Optional parameters to pass to the notifier constructor
            
        Returns:
            Notifier instance if found and successfully created, None otherwise
        """
        notifier_class = self.get(name)
        if notifier_class is None:
            return None
        return notifier_class(name, parameters or {})
    
    def load_from_module(self, module_path: str) -> int:
        """
        Dynamically load and register all notifiers from a module.
        
        Args:
            module_path: Python module path (e.g., 'bot.notifiers.telegram_notifier')
            
        Returns:
            Number of notifiers loaded
        """
        module = importlib.import_module(module_path)
        count = 0
        
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (obj is not Notifier and 
                issubclass(obj, Notifier) and 
                obj.__module__ == module_path):
                notifier_name = getattr(obj, 'NOTIFIER_NAME', obj.__name__)
                self.register(notifier_name, obj)
                count += 1
        
        return count