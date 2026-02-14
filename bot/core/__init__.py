"""
Core module for the trading bot engine and base interfaces.
"""

from bot.core.interfaces import Indicator, Strategy, Notifier
from bot.core.engine import TradingEngine
from bot.core.registry import StrategyRegistry, IndicatorRegistry

__all__ = [
    'Indicator',
    'Strategy',
    'Notifier',
    'TradingEngine',
    'StrategyRegistry',
    'IndicatorRegistry',
]