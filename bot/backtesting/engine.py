"""
Backtesting engine for testing strategies on historical data.
"""

from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
import logging
from datetime import datetime
from pathlib import Path

from bot.core.interfaces import Strategy, Indicator
from bot.core.registry import StrategyRegistry, IndicatorRegistry
from bot.backtesting.metrics import PerformanceMetrics


class BacktestEngine:
    """Backtesting engine for historical strategy testing."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        
        # Registries
        self.strategy_registry = StrategyRegistry()
        self.indicator_registry = IndicatorRegistry()
        
        # Components
        self.strategies: Dict[str, Strategy] = {}
        self.indicators: Dict[str, Indicator] = {}
        
        # Backtest state
        self.data: Optional[pd.DataFrame] = None
        self.trades: List[Dict[str, Any]] = []
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.equity_curve: List[float] = []
        self.initial_capital = self.config.get('initial_capital', 100000)
        self.current_capital = self.initial_capital
        
        # Transaction costs
        self.commission = self.config.get('commission', 0.001)
        self.slippage = self.config.get('slippage', 0.0001)
        
    def load_data(
        self,
        data: Optional[pd.DataFrame] = None,
        num_periods: Optional[int] = None
    ) -> None:
        """Load historical data for backtesting."""
        if data is not None:
            self.data = data.copy()
        elif num_periods is not None:
            self.data = self._generate_synthetic_data(num_periods)
        else:
            raise ValueError("Must provide either data or num_periods")
        
        # Reset state
        self.trades = []
        self.positions = {}
        self.equity_curve = []
        self.current_capital = self.initial_capital
    
    def _generate_synthetic_data(
        self,
        num_periods: int,
        initial_price: float = 100.0,
        volatility: float = 0.02,
        drift: float = 0.0001
    ) -> pd.DataFrame:
        """Generate synthetic OHLCV data."""
        np.random.seed(42)
        returns = np.random.normal(drift, volatility, num_periods)
        prices = initial_price * np.cumprod(1 + returns)
        
        data = pd.DataFrame(index=pd.date_range(
            start=datetime.now() - pd.Timedelta(days=num_periods),
            periods=num_periods,
            freq='1D'
        ))
        
        data['close'] = prices
        data['open'] = data['close'].shift(1).fillna(initial_price)
        high_low_range = data['close'] * volatility * 0.5
        data['high'] = data[['open', 'close']].max(axis=1) + high_low_range * np.random.random(num_periods)
        data['low'] = data[['open', 'close']].min(axis=1) - high_low_range * np.random.random(num_periods)
        data['volume'] = np.random.randint(100000, 1000000, num_periods)
        
        return data
    
    def add_strategy(self, strategy_name: str, parameters: Optional[Dict[str, Any]] = None) -> bool:
        """Add a strategy to the backtest."""
        strategy = self.strategy_registry.create_instance(strategy_name, parameters)
        if strategy is None:
            return False
        strategy.logger = self.logger
        self.strategies[strategy_name] = strategy
        return True
    
    def add_indicator(self, indicator_name: str, parameters: Optional[Dict[str, Any]] = None) -> bool:
        """Add an indicator to the backtest."""
        indicator = self.indicator_registry.create_instance(indicator_name, parameters)
        if indicator is None:
            return False
        indicator.logger = self.logger
        self.indicators[indicator_name] = indicator
        return True
    
    def attach_indicator_to_strategy(self, indicator_name: str, strategy_name: str) -> bool:
        """Attach an indicator to a strategy."""
        if indicator_name not in self.indicators or strategy_name not in self.strategies:
            return False
        self.strategies[strategy_name].add_indicator(self.indicators[indicator_name])
        return True
    
    def run(self, symbol: str = 'TEST') -> Dict[str, Any]:
        """Run the backtest."""
        if self.data is None or not self.strategies:
            raise ValueError("No data or strategies loaded")
        
        # Calculate indicators
        for indicator in self.indicators.values():
            self.data = indicator.calculate(self.data)
        
        # Run strategies
        for i in range(20, len(self.data)):  # Start after warmup period
            historical_data = self.data.iloc[:i+1]
            current_bar = self.data.iloc[i]
            
            for strategy in self.strategies.values():
                try:
                    signal = strategy.generate_signal(historical_data)
                    if signal.get('signal') in ['BUY', 'SELL']:
                        self._execute_signal(signal, current_bar)
                except Exception as e:
                    self.logger.error(f"Error executing strategy: {e}")
        
        # Calculate final equity
        final_capital = self.current_capital
        
        # Calculate metrics
        metrics = PerformanceMetrics.calculate(
            self.initial_capital, final_capital, self.trades, self.equity_curve
        )
        
        return {
            'metrics': metrics,
            'trades': self.trades,
            'final_capital': final_capital,
        }
    
    def _execute_signal(self, signal: Dict[str, Any], bar: pd.Series) -> None:
        """Execute a trading signal."""
        signal_type = signal.get('signal', 'HOLD')
        price = bar['close']
        
        if signal_type == 'BUY':
            quantity = int(self.current_capital * 0.1 / price)
            cost = quantity * price * (1 + self.commission + self.slippage)
            if cost <= self.current_capital:
                self.current_capital -= cost
                self.trades.append({
                    'type': 'BUY',
                    'quantity': quantity,
                    'price': price,
                    'timestamp': bar.name
                })
        elif signal_type == 'SELL':
            if self.trades:
                last_trade = [t for t in self.trades if t['type'] == 'BUY'][-1]
                quantity = last_trade['quantity']
                proceeds = quantity * price * (1 - self.commission - self.slippage)
                self.current_capital += proceeds
                self.trades.append({
                    'type': 'SELL',
                    'quantity': quantity,
                    'price': price,
                    'timestamp': bar.name
                })
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """Generate a backtest report."""
        metrics = results['metrics']
        return f"""
BACKTEST REPORT
{'='*60}
Initial Capital: ${self.initial_capital:,.2f}
Final Capital: ${results['final_capital']:,.2f}
Total Return: {metrics['total_return']:.2%}
Win Rate: {metrics['win_rate']:.2%}
Profit Factor: {metrics['profit_factor']:.2f}
Max Drawdown: {metrics['max_drawdown']:.2%}
Sharpe Ratio: {metrics['sharpe_ratio']:.2f}
Total Trades: {metrics['num_trades']}
{'='*60}
"""