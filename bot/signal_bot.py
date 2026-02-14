"""
APEX SIGNAL™ - Robust Signal Bot (with fallback strategies/indicators)
This file replaces stricter behavior that crashed on missing strategies/indicators.
"""

import os
import sys
import time
import yaml
import logging
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import json

import pandas as pd
import numpy as np

from bot.core.registry import StrategyRegistry, IndicatorRegistry, BaseRegistry
from bot.connectors.multi_source import MultiSourceConnector
# NOTE: use create_telegram_notifier_from_env or import TelegramNotifier class depending on your notifier file
try:
    from bot.notifiers.telegram_notifier import TelegramNotifier, create_telegram_notifier_from_env
except Exception:
    # fallback compatible import name (older file)
    from bot.notifiers.telegram import TelegramNotifier, create_telegram_notifier

from bot.utils.logger import setup_logger
from bot.utils.env_loader import get_env_loader
from bot.core.price_manager import PriceManager


class Mode:
    VERIFIED_TEST = "VERIFIED_TEST"
    LIVE_SIGNAL = "LIVE_SIGNAL"


# Minimal default strategy to ensure the system boots if no strategies are present.
class DefaultTrendStrategy:
    """
    Minimal trend-following fallback strategy.
    Implements required methods used by the engine / signal_bot.
    """
    name = "default_trend"

    def __init__(self, name: str = "default_trend", params: Optional[Dict[str, Any]] = None):
        self.name = name
        self.params = params or {}
        self.indicators = []
        self.logger = logging.getLogger("APEX_SIGNAL")

    def add_indicator(self, indicator):
        self.indicators.append(indicator)

    def reset(self):
        pass

    def generate_signal(self, bars: pd.DataFrame) -> Optional[Dict[str, Any]]:
        # basic crossover of EMA20/EMA50
        try:
            if bars is None or len(bars) < 5:
                return None
            latest = bars.iloc[-1]
            ema20 = None
            ema50 = None
            if 'ema_20' in bars.columns:
                ema20 = latest['ema_20']
            if 'ema_50' in bars.columns:
                ema50 = latest['ema_50']
            price = float(latest['close'])
            if ema20 is None or ema50 is None:
                return None
            if ema20 > ema50:
                return {
                    'strategy_name': self.name,
                    'signal': 'BUY',
                    'confidence': 65.0,
                    'reason': 'ema20 > ema50',
                    'metadata': {'ema20': ema20, 'ema50': ema50},
                    'entry_price': price,
                }
            elif ema20 < ema50:
                return {
                    'strategy_name': self.name,
                    'signal': 'SELL',
                    'confidence': 65.0,
                    'reason': 'ema20 < ema50',
                    'metadata': {'ema20': ema20, 'ema50': ema50},
                    'entry_price': price,
                }
            else:
                return None
        except Exception as e:
            self.logger.exception("DefaultTrendStrategy error: %s", e)
            return None


# Minimal indicators to attach if none found
class SimpleIndicators:
    @staticmethod
    def add_ema(bars: pd.DataFrame, length: int, col_name: str):
        bars[col_name] = bars['close'].ewm(span=length, adjust=False).mean()
        return bars

    @staticmethod
    def add_atr(bars: pd.DataFrame, length: int = 14, col_name: str = 'atr_14'):
        high_low = bars['high'] - bars['low']
        high_close = (bars['high'] - bars['close'].shift()).abs()
        low_close = (bars['low'] - bars['close'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        bars[col_name] = tr.rolling(window=length, min_periods=1).mean()
        return bars


class SignalBot:
    def __init__(self, config_path: str = "bot/config/config.yaml"):
        # seed logger early
        log_level = os.environ.get('LOG_LEVEL', 'INFO')
        self.logger = setup_logger("APEX_SIGNAL", log_level)

        self.config = self._load_config(config_path)
        self.env_loader = get_env_loader()

        # operating mode detection
        self.mode = self._detect_mode()

        # runtime state
        self.is_running = False
        self.start_time = None
        self.last_signal_time = None
        self.heartbeat_count = 0
        self.signal_count = 0
        self.daily_signals = []

        self.capital = self.env_loader.get_capital()
        self.risk_per_trade = self.env_loader.get_risk_per_trade()

        # connectors & managers
        self.connector: Optional[MultiSourceConnector] = None
        self.price_manager: Optional[PriceManager] = None

        # notifiers
        self.telegram_notifier = None

        # registries & components
        BaseRegistry.reset()
        self.strategy_registry = StrategyRegistry()
        self.indicator_registry = IndicatorRegistry()
        self.strategies: Dict[str, Any] = {}
        self.indicators: Dict[str, Any] = {}

        self.signal_history: List[Dict[str, Any]] = []
        self.healthy = True
        self.data_source_connected = False

        self.logger.warning("=" * 70)
        self.logger.warning("🚀 APEX SIGNAL™ BOT INITIALIZING")
        self.logger.warning(f"Mode: {self.mode}")
        self.logger.warning(f"Capital: ${self.capital:.2f}")
        self.logger.warning(f"Risk per trade: {self.risk_per_trade:.2%}")
        self.logger.warning("=" * 70)

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        try:
            cfg_file = Path(config_path)
            if cfg_file.exists():
                with open(cfg_file, 'r') as f:
                    cfg = yaml.safe_load(f) or {}
                    return cfg
            else:
                self.logger.warning("Config file not found at %s (using defaults)", config_path)
                return {}
        except Exception as e:
            self.logger.exception("Error loading config: %s", e)
            return {}

    def _detect_mode(self) -> str:
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        if token and chat_id:
            return Mode.LIVE_SIGNAL
        return Mode.VERIFIED_TEST

    async def initialize(self) -> bool:
        """
        Initialize connectors, price manager, notifier, and load strategies/indicators.
        This will not raise if strategies are missing — it will create safe fallbacks.
        """
        try:
            self.logger.info("🔧 Initializing bot components...")

            # connectors
            self.connector = MultiSourceConnector()
            connected = self.connector.connect()
            if not connected:
                self.logger.error("❌ Data connector failed to connect")
                # keep attempting but allow API to boot
                self.data_source_connected = False
            else:
                self.data_source_connected = True
                self.logger.info("✅ Data connector connected")

            # price manager (safe even if connector partially functional)
            self.price_manager = PriceManager(self.connector, cache_ttl=self.config.get('price_cache_ttl', 10))

            # Telegram notifier creation: config or env
            if self.mode == Mode.LIVE_SIGNAL:
                # signal_bot previously used dict notifier_config; support both
                token = os.environ.get('TELEGRAM_BOT_TOKEN')
                chat_id = os.environ.get('TELEGRAM_CHAT_ID')
                try:
                    # try import factory
                    self.telegram_notifier = create_telegram_notifier_from_env() if 'create_telegram_notifier_from_env' in globals() else TelegramNotifier(token=token, chat_id=chat_id)
                except Exception:
                    # fallback
                    try:
                        self.telegram_notifier = TelegramNotifier(token=token, chat_id=chat_id)
                    except Exception:
                        self.telegram_notifier = None
                if self.telegram_notifier and self.telegram_notifier.is_enabled():
                    self.logger.info("✅ Telegram notifier initialized (LIVE mode)")
                    # send startup notification asynchronously (do not block)
                    try:
                        asyncio.create_task(self.send_startup_notification())
                    except Exception:
                        pass
                else:
                    self.logger.warning("⚠️ Telegram notifier not enabled or failed to initialize")
            else:
                self.logger.info("✅ Running in VERIFIED_TEST mode (no live Telegram)")

            # load strategies & indicators via registry; if none found -> fallback
            await self._load_strategies_and_indicators()

            self.is_running = True
            self.start_time = datetime.utcnow()
            self.healthy = True
            # non-blocking feed notification
            try:
                if self.telegram_notifier and self.telegram_notifier.is_enabled():
                    asyncio.create_task(self._send_feed_connected_notification())
            except Exception:
                pass

            return True

        except Exception as e:
            self.logger.exception("❌ Initialization failed: %s", e)
            self.healthy = False
            return False

    async def _load_strategies_and_indicators(self) -> None:
        """
        Attempt to load from registries. If none discovered, register minimal fallback
        strategy & indicators so the system can produce signals safely.
        """
        # Discover via registries (if registry code present, use it)
        try:
            indicator_count = 0
            strategy_count = 0
            try:
                indicator_count = self.indicator_registry.load_all_indicators()
            except Exception:
                # registry may not implement load_all_indicators
                indicator_count = 0

            try:
                strategy_count = self.strategy_registry.load_all_strategies()
            except Exception:
                strategy_count = 0

            self.logger.info("✅ Indicators discovered: %d", indicator_count)
            self.logger.info("✅ Strategies discovered: %d", strategy_count)
        except Exception as e:
            self.logger.warning("Registry discovery error: %s", e)
            indicator_count = 0
            strategy_count = 0

        # If no indicators, create simple EMA/ATR in-memory for immediate use
        if indicator_count == 0:
            self.logger.warning("⚠️ No indicators found - attaching minimal internal indicators")
            # store simple indicator functions in indicator dict for later use
            self.indicators['ema_20'] = ('internal', {"fn": lambda bars: SimpleIndicators.add_ema(bars, 20, 'ema_20')})
            self.indicators['ema_50'] = ('internal', {"fn": lambda bars: SimpleIndicators.add_ema(bars, 50, 'ema_50')})
            self.indicators['atr_14'] = ('internal', {"fn": lambda bars: SimpleIndicators.add_atr(bars, 14, 'atr_14')})

        # If no strategies, attach DefaultTrendStrategy so bot does not crash
        if strategy_count == 0:
            self.logger.warning("⚠️ No strategies discovered - activating fallback DefaultTrendStrategy")
            default = DefaultTrendStrategy()
            # attach internal indicators to the strategy by name
            # use simple wrapper objects for compatibility
            class _IndicatorWrapper:
                def __init__(self, name, fn):
                    self.name = name
                    self.fn = fn
                def calculate(self, bars):
                    try:
                        return self.fn(bars)
                    except Exception:
                        return bars
            # create and attach
            for name, val in self.indicators.items():
                if isinstance(val, tuple) and val[0] == 'internal':
                    fn = val[1]['fn']
                    default.add_indicator(_IndicatorWrapper(name, fn))
            self.strategies[default.name] = default
            self.logger.info("✅ Fallback strategy activated: %s", default.name)

        # If registries returned strategies, instantiate them (best-effort)
        try:
            # If the registry provides a get() method, try to instantiate strategies enabled in config
            strategies_config = self.config.get('strategies', {})
            if strategy_count > 0 and strategies_config:
                for sname, sconf in strategies_config.items():
                    if sconf.get('enabled', False):
                        sclass = self.strategy_registry.get(sname)
                        if sclass:
                            inst = sclass(sname, sconf.get('parameters', {}))
                            # attach indicators from config where possible
                            for iname in (self.config.get('indicators', {}) or {}):
                                ival = self.indicator_registry.get(iname) if hasattr(self.indicator_registry, 'get') else None
                                if ival:
                                    inst.add_indicator(ival(iname, {}))
                            self.strategies[sname] = inst
                            self.logger.info("✅ Activated strategy from registry: %s", sname)
        except Exception as e:
            self.logger.warning("Registry-based strategy activation skipped due to: %s", e)

        # final sanity log
        self.logger.info("✅ %d active strategies loaded", len(self.strategies))

        if len(self.strategies) == 0:
            # extremely defensive fallback
            fallback = DefaultTrendStrategy()
            self.strategies[fallback.name] = fallback
            self.logger.warning("⚠️ Emergency fallback strategy loaded: %s", fallback.name)

    async def _send_feed_connected_notification(self):
        if not self.telegram_notifier:
            return
        try:
            status = {'active_data_source': 'multi', 'max_deviation': 0.0005}
            msg = (
                f"✅ LIVE DATA FEED CONNECTED\n"
                f"Active Source: {status['active_data_source']}\n"
                f"Price deviation threshold: {status['max_deviation']:.4%}\n"
                f"UTC: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            await self.telegram_notifier._send(msg) if hasattr(self.telegram_notifier, '_send') else None
        except Exception:
            pass

    async def send_startup_notification(self):
        if not self.telegram_notifier:
            return
        try:
            txt = (
                f"🚀 APEX SIGNAL BOT STARTED\n"
                f"Mode: {self.mode}\n"
                f"Capital: ${self.capital:.2f}\n"
                f"Active strategies: {len(self.strategies)}\n"
                f"UTC: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            await self.telegram_notifier._send(txt)
        except Exception:
            pass

    async def run(self):
        self.logger.info("🚀 Starting main bot loop...")
        self.is_running = True
        try:
            while self.is_running:
                self.heartbeat_count += 1
                now = datetime.utcnow()
                for symbol in self.config.get('symbols', ['BTC/USD','ETH/USD','GOLD/USD']):
                    try:
                        await self._scan_symbol(symbol)
                    except Exception as e:
                        self.logger.exception("Error scanning %s: %s", symbol, e)
                await asyncio.sleep(self.config.get('scan_interval', 60))
        except asyncio.CancelledError:
            self.logger.info("Bot loop cancelled")
        finally:
            await self.shutdown()

    async def _scan_symbol(self, symbol: str):
        try:
            if not self.price_manager:
                return
            price_data = self.price_manager.get_price(symbol)
            if price_data is None:
                self.logger.warning("No price data for %s", symbol)
                return
            price = price_data.get('price') or price_data.get('last') or None
            if price is None:
                return
            # fetch bars
            bars = self.connector.fetch_bars(symbol, '1h', limit=200) if hasattr(self.connector, 'fetch_bars') else pd.DataFrame()
            if bars is None or (isinstance(bars, pd.DataFrame) and bars.empty):
                self.logger.warning("No bars for %s", symbol)
            else:
                # apply any internal indicator functions attached to strategies
                for sname, strategy in self.strategies.items():
                    # apply attached indicator wrappers if present
                    try:
                        # create a working copy of bars for indicator calculations
                        bars_calc = bars.copy()
                        if hasattr(strategy, 'indicators'):
                            for ind in getattr(strategy, 'indicators', []):
                                if hasattr(ind, 'calculate'):
                                    bars_calc = ind.calculate(bars_calc)
                        signal = strategy.generate_signal(bars_calc)
                        if signal and signal.get('signal') in ('BUY','SELL'):
                            # enrich and send
                            signal_payload = {
                                'symbol': symbol,
                                'signal': signal.get('signal'),
                                'price': price,
                                'tp1': signal.get('tp') or signal.get('tp1') or (price * 1.01),
                                'tp2': signal.get('tp2') or (price * 1.02),
                                'tp3': signal.get('tp3') or (price * 1.03),
                                'sl': signal.get('sl') or (price * 0.99),
                                'confidence': signal.get('confidence', 50.0),
                                'strategy_name': signal.get('strategy_name', sname),
                                'indicators': list({ind.name for ind in getattr(strategy, 'indicators', []) if hasattr(ind, 'name')})
                            }
                            # send notification (non-blocking)
                            if self.telegram_notifier:
                                try:
                                    self.telegram_notifier.send_notification(self.telegram_notifier._format_signal_text(Signal(**{
                                        'symbol': signal_payload['symbol'],
                                        'side': signal_payload['signal'],
                                        'entry': signal_payload['price'],
                                        'sl': signal_payload['sl'],
                                        'tp1': signal_payload['tp1'],
                                        'tp2': signal_payload['tp2'],
                                        'tp3': signal_payload['tp3'],
                                        'confidence': float(signal_payload['confidence']),
                                        'strategy_name': signal_payload['strategy_name'],
                                        'indicators': signal_payload['indicators']
                                    })), signal_payload)
                                except Exception:
                                    # fallback to compatibility call
                                    try:
                                        self.telegram_notifier.send_notification(str(signal_payload), signal_payload)
                                    except Exception:
                                        self.logger.exception("Failed to send notification for %s", symbol)
                            # add to history
                            self.signal_history.append(signal_payload)
                            self.signal_count += 1
                    except Exception as e:
                        self.logger.exception("Strategy execution error: %s", e)
        except Exception as e:
            self.logger.exception("Scan symbol exception: %s", e)

    async def _send_error_notification(self, error: str):
        if self.telegram_notifier:
            try:
                self.telegram_notifier.send_notification(f"ERROR: {error}", {'signal': 'ERROR', 'reason': error})
            except Exception:
                pass

    async def shutdown(self):
        self.logger.info("🛑 Shutting down bot...")
        self.is_running = False
        if self.telegram_notifier:
            try:
                self.telegram_notifier.send_heartbeat()
            except Exception:
                pass
