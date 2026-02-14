"""
Main application entry point for the modular trading bot.
Demonstrates initialization and dynamic loading of strategies, indicators, and notifiers.
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd

from bot.core.engine import TradingEngine
from bot.core.registry import StrategyRegistry, IndicatorRegistry, NotifierRegistry
from bot.utils.logger import setup_logger
from bot.utils.data_loader import DataLoader


class TradingBot:
    """
    Main trading bot application class.
    Orchestrates all components and manages the trading lifecycle.
    """
    
    def __init__(self, config_path: str = "bot/config/config.yaml"):
        """
        Initialize the trading bot.
        
        Args:
            config_path: Path to the configuration file
        """
        self.config = self._load_config(config_path)
        self.logger = setup_logger(
            "TradingBot",
            log_level=self.config.get('engine', {}).get('log_level', 'INFO')
        )
        
        # Initialize data loader
        self.data_loader = DataLoader(self.logger)
        
        # Initialize trading engine
        self.engine = TradingEngine(self.config.get('engine', {}))
        
        self.logger.info("TradingBot initialized")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load configuration from YAML file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Configuration dictionary
        """
        try:
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)
                return config or {}
            else:
                print(f"Config file not found: {config_path}. Using default configuration.")
                return {}
        except Exception as e:
            print(f"Error loading config: {e}. Using default configuration.")
            return {}
    
    def load_strategies_from_config(self) -> None:
        """
        Load strategies defined in the configuration.
        Strategies are loaded dynamically from the registry.
        """
        strategies_config = self.config.get('strategies', {})
        
        for strategy_name, strategy_config in strategies_config.items():
            if strategy_config.get('enabled', False):
                try:
                    # Load strategy module
                    module_path = f"bot.strategies.{strategy_name}"
                    loaded = self.engine.strategy_registry.load_from_module(module_path)
                    self.logger.info(f"Loaded {loaded} strategies from {module_path}")
                    
                    # Create strategy instance
                    parameters = strategy_config.get('parameters', {})
                    success = self.engine.load_strategy(strategy_name, parameters)
                    
                    if success:
                        self.logger.info(f"Strategy '{strategy_name}' loaded successfully")
                    else:
                        self.logger.warning(f"Failed to load strategy '{strategy_name}'")
                
                except Exception as e:
                    self.logger.error(f"Error loading strategy '{strategy_name}': {e}")
    
    def load_indicators_from_config(self) -> None:
        """
        Load indicators defined in the configuration.
        Indicators are loaded dynamically from the registry.
        """
        indicators_config = self.config.get('indicators', {})
        
        for indicator_name, indicator_config in indicators_config.items():
            if indicator_config.get('enabled', False):
                try:
                    # Load indicator module
                    module_path = f"bot.indicators.{indicator_name}"
                    loaded = self.engine.indicator_registry.load_from_module(module_path)
                    self.logger.info(f"Loaded {loaded} indicators from {module_path}")
                    
                    # Create indicator instance
                    parameters = indicator_config.get('parameters', {})
                    success = self.engine.load_indicator(indicator_name, parameters)
                    
                    if success:
                        self.logger.info(f"Indicator '{indicator_name}' loaded successfully")
                    else:
                        self.logger.warning(f"Failed to load indicator '{indicator_name}'")
                
                except Exception as e:
                    self.logger.error(f"Error loading indicator '{indicator_name}': {e}")
    
    def load_notifiers_from_config(self) -> None:
        """
        Load notifiers defined in the configuration.
        Notifiers are loaded dynamically from the registry.
        """
        notifiers_config = self.config.get('notifiers', {})
        
        for notifier_name, notifier_config in notifiers_config.items():
            if notifier_config.get('enabled', False):
                try:
                    # Load notifier module
                    module_path = f"bot.notifiers.{notifier_name}"
                    loaded = self.engine.notifier_registry.load_from_module(module_path)
                    self.logger.info(f"Loaded {loaded} notifiers from {module_path}")
                    
                    # Create notifier instance
                    parameters = notifier_config.get('parameters', {})
                    success = self.engine.load_notifier(notifier_name, parameters)
                    
                    if success:
                        self.logger.info(f"Notifier '{notifier_name}' loaded successfully")
                    else:
                        self.logger.warning(f"Failed to load notifier '{notifier_name}'")
                
                except Exception as e:
                    self.logger.error(f"Error loading notifier '{notifier_name}': {e}")
    
    def load_data(self) -> pd.DataFrame:
        """
        Load trading data based on configuration.
        
        Returns:
            DataFrame with OHLCV data
        """
        data_config = self.config.get('data', {})
        source = data_config.get('source', 'synthetic')
        
        if source == 'synthetic':
            return self.data_loader.generate_synthetic_data(
                num_periods=data_config.get('num_periods', 1000),
                volatility=data_config.get('volatility', 0.02),
                drift=data_config.get('drift', 0.0001),
                initial_price=data_config.get('initial_price', 100.0)
            )
        elif source == 'csv':
            csv_path = data_config.get('csv_path')
            if csv_path:
                return self.data_loader.load_from_csv(csv_path)
            else:
                raise ValueError("CSV path not specified in configuration")
        else:
            raise ValueError(f"Unknown data source: {source}")
    
    def initialize(self) -> None:
        """
        Initialize all bot components.
        Loads strategies, indicators, and notifiers from configuration.
        """
        self.logger.info("Initializing bot components...")
        
        # Load all components
        self.load_indicators_from_config()
        self.load_strategies_from_config()
        self.load_notifiers_from_config()
        
        # Attach indicators to strategies as needed
        # This can be customized based on strategy requirements
        self._attach_indicators_to_strategies()
        
        self.logger.info("Bot initialization complete")
        self._print_status()
    
    def _attach_indicators_to_strategies(self) -> None:
        """
        Attach loaded indicators to loaded strategies.
        This is a simple implementation that attaches all indicators to all strategies.
        Can be customized based on specific strategy requirements.
        """
        indicators = self.engine.get_active_indicators()
        strategies = self.engine.get_active_strategies()
        
        for strategy_name in strategies:
            for indicator_name in indicators:
                self.engine.attach_indicator_to_strategy(indicator_name, strategy_name)
                self.logger.debug(f"Attached {indicator_name} to {strategy_name}")
    
    def _print_status(self) -> None:
        """Print the current status of the bot."""
        status = self.engine.get_status()
        
        print("\n" + "="*60)
        print("TRADING BOT STATUS")
        print("="*60)
        print(f"Active Strategies: {status['active_strategies']}")
        print(f"Active Indicators: {status['active_indicators']}")
        print(f"Active Notifiers: {status['active_notifiers']}")
        print("="*60 + "\n")
    
    def run(self) -> None:
        """
        Run the trading bot.
        Loads data and executes strategies.
        """
        self.logger.info("Starting trading bot...")
        self.engine.start()
        
        try:
            # Load data
            data = self.load_data()
            self.logger.info(f"Loaded {len(data)} data points")
            
            # Validate data
            if not self.data_loader.validate_data(data):
                self.logger.error("Data validation failed")
                return
            
            # Execute strategies
            signals = self.engine.execute_strategies(data)
            
            # Print signals
            self.logger.info(f"Generated {len(signals)} signals")
            for signal in signals:
                print(f"\nSignal: {signal}")
            
        except Exception as e:
            self.logger.error(f"Error running bot: {e}")
        finally:
            self.engine.stop()
            self.logger.info("Trading bot stopped")


def main():
    """
    Main entry point for the trading bot.
    """
    # Initialize and run the bot
    bot = TradingBot()
    bot.initialize()
    bot.run()


if __name__ == "__main__":
    main()