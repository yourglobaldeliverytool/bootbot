"""
Data connectors for APEX SIGNAL™.
Multiple data sources with automatic failover.
Uses Alpaca, Polygon, Yahoo, TradingView, CoinGecko, CoinCap, MetalsLive.
"""

from bot.connectors.base import BaseDataConnector
from bot.connectors.coingecko import CoinGeckoConnector
from bot.connectors.coincap import CoinCapConnector
from bot.connectors.metals_live import MetalsLiveConnector
from bot.connectors.mock_live import MockLiveConnector
from bot.connectors.multi_source import MultiSourceConnector
from bot.connectors.alpaca import AlpacaConnector
from bot.connectors.yahoo_finance import YahooFinanceConnector
from bot.connectors.tradingview import TradingViewConnector

# Polygon connector (if API key available)
try:
    from bot.connectors.polygon import PolygonConnector
    _polygon_available = True
except ImportError:
    _polygon_available = False
    PolygonConnector = None

__all__ = [
    'BaseDataConnector',
    'CoinGeckoConnector',
    'CoinCapConnector',
    'MetalsLiveConnector',
    'MockLiveConnector',
    'MultiSourceConnector',
    'AlpacaConnector',
    'YahooFinanceConnector',
    'TradingViewConnector',
]

if _polygon_available:
    __all__.append('PolygonConnector')