"""
APEX SIGNAL™ - Production-Grade Telegram Signal Bot
Live market data + multi-source price verification + institutional-grade strategies
NO BINANCE - Uses Alpaca, Polygon, Yahoo, TradingView, CoinGecko, CoinCap
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
from bot.notifiers.telegram_notifier import TelegramNotifier
from bot.utils.logger import setup_logger
from bot.utils.env_loader import get_env_loader
from bot.core.price_manager import PriceManager


class Mode:
    """Operating modes for the signal bot."""
    VERIFIED_TEST = "VERIFIED_TEST"
    LIVE_SIGNAL = "LIVE_SIGNAL"


class SignalBot:
    """
    Production-grade Telegram signal bot with:
    - Automatic mode detection
    - Multi-source price verification (NO BINANCE)
    - Dynamic confidence calculation
    - Professional Telegram messaging
    - Railway deployment ready
    - MUST halt without verified live data
    """
    
    def __init__(self, config_path: str = "bot/config/config.yaml"):
        """Initialize the signal bot."""
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Load environment variables (Railway)
        self.env_loader = get_env_loader()
        
        # Detect operating mode
        self.mode = self._detect_mode()
        
        # Setup logging
        log_level = self.config.get('logging', {}).get('level', 'INFO')
        self.logger = setup_logger("APEX_SIGNAL", log_level)
        
        # Bot state
        self.is_running = False
        self.start_time = None
        self.last_signal_time = None
        self.heartbeat_count = 0
        self.signal_count = 0
        self.daily_signals = []
        
        # Capital management - from environment (Railway) with config fallback
        # Default CAPITAL = 50 per requirements
        self.capital = self.env_loader.get_capital()
        self.risk_per_trade = self.env_loader.get_risk_per_trade()
        
        # Initialize components
        self.connector = None
        self.price_manager = None
        self.telegram_notifier = None
        self.strategies = {}
        self.indicators = {}
        
        # Initialize registries (use singleton pattern)
        BaseRegistry.reset()  # Reset for clean state
        self.strategy_registry = StrategyRegistry.get_instance()
        self.indicator_registry = IndicatorRegistry.get_instance()
        
        # Signal history
        self.signal_history: List[Dict[str, Any]] = []
        
        # Health check endpoint
        self.healthy = True
        
        # Data source monitoring
        self.data_source_connected = False
        self.last_data_check = None
        
        # Notification state
        self.daily_summary_sent = False
        self.last_summary_time = None
        
        self.logger.warning("=" * 70)
        self.logger.warning("🚀 APEX SIGNAL™ BOT INITIALIZING")
        self.logger.warning("=" * 70)
        self.logger.warning(f"Mode: {self.mode}")
        self.logger.warning(f"Capital: ${self.capital:.2f}")
        self.logger.warning(f"Risk per trade: {self.risk_per_trade:.1%}")
        self.logger.warning("=" * 70)
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)
                return config or {}
            else:
                self.logger.warning(f"Config file not found: {config_path}")
                return {}
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return {}
    
    def _detect_mode(self) -> str:
        """
        Automatically detect operating mode based on environment.
        LIVE_SIGNAL mode activates if Telegram credentials are present.
        """
        telegram_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        
        if telegram_token and telegram_chat_id:
            return Mode.LIVE_SIGNAL
        else:
            return Mode.VERIFIED_TEST
    
    async def initialize(self) -> bool:
        """Initialize all bot components."""
        try:
            self.logger.info("🔧 Initializing bot components...")
            
            # Initialize data connector
            self.connector = MultiSourceConnector()
            if not self.connector.connect():
                self.logger.error("❌ Failed to connect to data sources")
                self.logger.error("❌ BOT CANNOT OPERATE WITHOUT LIVE DATA")
                return False
            
            self.data_source_connected = True
            self.last_data_check = datetime.utcnow()
            self.logger.info("✅ Data connector connected")
            
            # Initialize price manager with 10s cache
            self.price_manager = PriceManager(self.connector, cache_ttl=10)
            self.logger.info("✅ Price manager initialized with 10s cache")
            
            # Initialize Telegram notifier
            if self.mode == Mode.LIVE_SIGNAL:
                token = os.environ.get('TELEGRAM_BOT_TOKEN')
                chat_id = os.environ.get('TELEGRAM_CHAT_ID')
                
                if token and chat_id:
                    notifier_config = {
                        'bot_token': token,
                        'chat_id': chat_id
                    }
                    self.telegram_notifier = TelegramNotifier(notifier_config)
                    self.logger.info("✅ Telegram notifier initialized (LIVE mode)")
                    
                    # Send startup notification
                    await self._send_startup_notification()
                else:
                    self.logger.error("❌ TELEGRAM CREDENTIALS MISSING IN LIVE MODE")
                    self.logger.error("❌ BOT WILL HALT")
                    return False
            else:
                self.logger.info("✅ Running in VERIFIED_TEST mode (no real Telegram messages)")
            
            # Load strategies and indicators
            await self._load_strategies_and_indicators()
            
            self.is_running = True
            self.start_time = datetime.utcnow()
            self.healthy = True
            
            # Send live feed connected notification
            await self._send_feed_connected_notification()
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Initialization failed: {e}")
            self.healthy = False
            return False
    
    async def _load_strategies_and_indicators(self) -> None:
        """Load all strategies and indicators from all modules."""
        # Load all indicators
        self.indicator_registry = IndicatorRegistry()
        indicator_count = self.indicator_registry.load_all_indicators()
        self.logger.info(f"✅ Loaded {indicator_count} indicators")
        
        # Load all strategies
        self.strategy_registry = StrategyRegistry()
        strategy_count = self.strategy_registry.load_all_strategies()
        self.logger.info(f"✅ Loaded {strategy_count} strategies")
        
        # CRITICAL: Fail if no strategies loaded
        if strategy_count == 0:
            self.logger.error("❌ CRITICAL: No strategies loaded from registry")
            raise RuntimeError("No strategies loaded - cannot operate without strategies")
        
        # Initialize active strategies from config
        strategies_config = self.config.get('strategies', {})
        active_count = 0
        
        for strategy_name, strategy_config in strategies_config.items():
            if strategy_config.get('enabled', False):
                parameters = strategy_config.get('parameters', {})
                
                # Get strategy class and instantiate properly
                strategy_class = self.strategy_registry.get(strategy_name)
                if not strategy_class:
                    self.logger.warning(f"Strategy not found: {strategy_name}")
                    continue
                
                strategy = strategy_class(strategy_name, parameters)
                
                if strategy:
                    # Attach indicators - create instances from registry
                    indicators_config = self.config.get('indicators', {})
                    for indicator_name, indicator_config in indicators_config.items():
                        if indicator_config.get('enabled', False):
                            # Get indicator class and instantiate
                            indicator_class = self.indicator_registry.get(indicator_name)
                            if indicator_class:
                                indicator_params = indicator_config.get('parameters', {})
                                indicator = indicator_class(indicator_name, indicator_params)
                                strategy.add_indicator(indicator)
                            else:
                                self.logger.warning(f"Indicator not found: {indicator_name}")
                    
                    self.strategies[strategy_name] = strategy
                    active_count += 1
                    self.logger.info(f"✅ Activated strategy: {strategy_name}")
        
        self.logger.info(
            f"✅ {active_count} active strategies, {strategy_count} total strategies, "
            f"{indicator_count} indicators available"
        )
    
    async def _send_startup_notification(self) -> None:
        """Send startup notification to Telegram."""
        message = f"""
🚀 APEX SIGNAL BOT™ STARTED
━━━━━━━━━━━━━━━━━━
✅ Bot initialized
💰 Capital: ${self.capital:.2f}
⚠️ Risk per trade: {self.risk_per_trade:.1%}
📊 Strategies: {len(self.strategies)}
🎯 Indicators: {len(self.indicator_registry._registry)}
━━━━━━━━━━━━━━━━━━
⏰ Started at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""
        await self._send_telegram_message(message)
    
    async def _send_feed_connected_notification(self) -> None:
        """Send notification when live feed is connected."""
        if not self.telegram_notifier:
            return
        
        status = self.connector.get_status()
        active_source = status.get('active_data_source', 'Unknown')
        
        message = f"""
✅ LIVE DATA FEED CONNECTED
━━━━━━━━━━━━━━━━━━
📡 Active Source: {active_source}
🔄 Data Verification: ENABLED
⚠️ Price Deviation Limit: {status.get('max_deviation', 0.0005):.4%}
━━━━━━━━━━━━━━━━━━
⏰ Connected at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""
        await self._send_telegram_message(message)
    
    async def _send_feed_failure_notification(self, error: str) -> None:
        """Send notification when feed fails."""
        if not self.telegram_notifier:
            return
        
        message = f"""
❌ LIVE DATA FEED FAILURE
━━━━━━━━━━━━━━━━━━
⚠️ Error: {error}
🔄 Attempting reconnection...
⏰ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
━━━━━━━━━━━━━━━━━━
🚨 Bot will attempt automatic failover
"""
        await self._send_telegram_message(message)
    
    async def _send_daily_summary(self) -> None:
        """Send daily summary notification."""
        if not self.telegram_notifier or self.daily_summary_sent:
            return
        
        today = datetime.utcnow().date()
        
        # Filter today's signals
        todays_signals = [s for s in self.daily_signals if s['timestamp'].date() == today]
        
        if not todays_signals:
            return
        
        # Calculate stats
        buy_signals = len([s for s in todays_signals if s['signal'] == 'BUY'])
        sell_signals = len([s for s in todays_signals if s['signal'] == 'SELL'])
        avg_confidence = np.mean([s['confidence'] for s in todays_signals])
        
        message = f"""
📊 DAILY SUMMARY - APEX SIGNAL BOT™
━━━━━━━━━━━━━━━━━━
📅 Date: {today.strftime('%Y-%m-%d')}
📊 Total Signals: {len(todays_signals)}
🟢 BUY Signals: {buy_signals}
🔴 SELL Signals: {sell_signals}
🎯 Avg Confidence: {avg_confidence:.1f}%
━━━━━━━━━━━━━━━━━━
💰 Capital: ${self.capital:.2f}
⏰ Report at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
━━━━━━━━━━━━━━━━━━
"""
        await self._send_telegram_message(message)
        self.daily_summary_sent = True
        self.last_summary_time = datetime.utcnow()
    
    async def run(self) -> None:
        """Main bot loop."""
        self.logger.info("🚀 Starting main bot loop...")
        
        try:
            while self.is_running:
                # Update heartbeat
                self.heartbeat_count += 1
                
                # Check if it's time for daily summary
                now = datetime.utcnow()
                if not self.daily_summary_sent and now.hour == 23 and now.minute >= 0:
                    await self._send_daily_summary()
                
                # Reset daily summary at midnight
                if self.last_summary_time and (now - self.last_summary_time).days >= 1:
                    self.daily_summary_sent = False
                    self.daily_signals = []
                
                # Scan symbols
                for symbol in self.config.get('symbols', ['BTCUSDT']):
                    try:
                        await self._scan_symbol(symbol)
                    except Exception as e:
                        self.logger.error(f"Error scanning {symbol}: {e}")
                        await self._send_error_notification(f"Scanning error for {symbol}: {e}")
                
                # Wait before next scan
                scan_interval = self.config.get('scan_interval', 60)
                await asyncio.sleep(scan_interval)
                
        except asyncio.CancelledError:
            self.logger.info("Bot loop cancelled")
        except Exception as e:
            self.logger.error(f"Bot loop error: {e}")
            await self._send_error_notification(f"Critical error: {e}")
        finally:
            await self.shutdown()
    
    async def _scan_symbol(self, symbol: str) -> None:
        """Scan a symbol for trading opportunities."""
        try:
            # Fetch current price with PriceManager (includes caching and verification)
            price_data = self.price_manager.get_price(symbol)
            
            if price_data is None:
                self.logger.error(f"❌ No price data for {symbol}")
                self.data_source_connected = False
                await self._send_feed_failure_notification("No price data available")
                return
            
            # Extract price and metadata
            price = price_data['price']
            price_source = price_data['source']
            price_checksum = price_data['checksum']
            
            # Update data source status
            self.data_source_connected = True
            self.last_data_check = datetime.utcnow()
            
            # Fetch historical data
            bars = self.connector.fetch_bars(symbol, '1h', limit=100)
            
            if bars.empty:
                self.logger.warning(f"⚠️ No bar data for {symbol}")
                return
            
            # Calculate indicators
            for indicator_key in self.indicator_registry._registry:
                indicator = self.indicator_registry.create_instance(
                    indicator_key,
                    {}
                )
                if indicator:
                    bars = indicator.calculate(bars)
            
            # Generate signals from all strategies
            signals = []
            strategy_alignment = []
            indicator_confirmation = []
            
            for strategy_name, strategy in self.strategies.items():
                try:
                    signal = strategy.generate_signal(bars)
                    
                    # Check if signal is valid
                    if signal and signal.get('signal') in ['BUY', 'SELL']:
                        signals.append(signal)
                        strategy_alignment.append(strategy_name)
                        
                        # Track indicators used
                        for indicator in strategy.indicators:
                            indicator_confirmation.append(indicator.name)
                        
                except Exception as e:
                    self.logger.error(f"Error in strategy {strategy_name}: {e}")
            
            # Calculate dynamic confidence
            confidence = self._calculate_confidence(
                signals,
                strategy_alignment,
                indicator_confirmation,
                bars
            )
            
            # Intelligent minimum threshold - reject weak confluence
            min_confidence_threshold = 60  # 60% minimum confidence
            if confidence < min_confidence_threshold:
                self.logger.info(
                    f"⏭️ Skipping signal for {symbol} - confidence {confidence:.1f}% "
                    f"below threshold {min_confidence_threshold}%"
                )
                return
            
            # Generate signal if we have valid signals
            if signals:
                # Auto-select best signal
                primary_signal = self._auto_select_best_signal(signals, bars)
                
                if primary_signal and primary_signal.get('signal') in ['BUY', 'SELL']:
                    signal_type = primary_signal.get('signal', 'HOLD')
                    
                    # Find the strategy that produced this signal
                    primary_strategy_name = 'Unknown'
                    if len(strategy_alignment) > 0:
                        primary_strategy_name = strategy_alignment[0]
                    
                    # Generate TP/SL with multiple targets
                    tp_levels, sl = self._calculate_tp_sl_levels(
                        price,
                        signal_type,
                        bars
                    )
                    
                    # Get price data with checksum
                    price_data = self.price_manager.get_price(symbol)
                    if price_data:
                        checksum = price_data['checksum']
                        primary_source = price_data['source']
                        secondary_source = price_data.get('secondary_source', 'N/A')
                        price_deviation = price_data['deviation']
                    else:
                        checksum = self.connector.get_price_checksum(symbol, price)
                        primary_source = 'unknown'
                        secondary_source = 'unknown'
                        price_deviation = 0.0
                    
                    # Create signal message
                    signal_data = {
                        'symbol': symbol,
                        'signal': signal_type,
                        'price': price,
                        'tp': tp_levels[0],
                        'tp1': tp_levels[0],
                        'tp2': tp_levels[1],
                        'tp3': tp_levels[2],
                        'sl': sl,
                        'confidence': confidence,
                        'strategies': strategy_alignment,
                        'indicators': list(set(indicator_confirmation)),
                        'checksum': checksum,
                        'primary_source': primary_source,
                        'secondary_source': secondary_source,
                        'price_deviation': price_deviation,
                        'timestamp': datetime.utcnow(),
                        'strategy_name': primary_strategy_name,
                    }
                    
                    # Send signal to Telegram
                    await self._send_signal(signal_data)
                    
                    self.last_signal_time = datetime.utcnow()
                    self.signal_count += 1
                    self.signal_history.append(signal_data)
                    self.daily_signals.append(signal_data)
                    
        except Exception as e:
            self.logger.error(f"Error scanning {symbol}: {e}")
            await self._send_error_notification(f"Scanning error for {symbol}: {e}")
    
    def _auto_select_best_signal(
        self,
        signals: List[Dict[str, Any]],
        bars: pd.DataFrame
    ) -> Optional[Dict[str, Any]]:
        """
        Automatically select the best signal using AI-based criteria.
        Considers trend alignment, volume confirmation, and volatility.
        """
        if not signals:
            return None
        
        # Score each signal
        scored_signals = []
        
        for signal in signals:
            score = 0
            signal_type = signal.get('signal', 'HOLD')
            
            # Trend alignment score (40%)
            if 'ema_20' in bars.columns and 'ema_50' in bars.columns:
                latest_ema20 = bars['ema_20'].iloc[-1]
                latest_ema50 = bars['ema_50'].iloc[-1]
                
                if signal_type == 'BUY' and latest_ema20 > latest_ema50:
                    score += 40  # Bullish trend alignment
                elif signal_type == 'SELL' and latest_ema20 < latest_ema50:
                    score += 40  # Bearish trend alignment
            
            # Volume confirmation score (30%)
            if 'volume' in bars.columns:
                avg_volume = bars['volume'].iloc[-20:].mean()
                latest_volume = bars['volume'].iloc[-1]
                
                if latest_volume > avg_volume * 1.2:
                    score += 30  # Volume spike confirmation
            
            # Volatility score (30%)
            if 'atr_14' in bars.columns:
                atr = bars['atr_14'].iloc[-1]
                latest_close = bars['close'].iloc[-1]
                
                # ATR in reasonable range (not too flat, not too volatile)
                atr_pct = atr / latest_close
                if 0.01 < atr_pct < 0.05:
                    score += 30  # Good volatility
                elif atr_pct >= 0.01:
                    score += 15  # Acceptable volatility
            
            signal['_score'] = score
            scored_signals.append(signal)
        
        # Select highest scored signal
        if scored_signals:
            best_signal = max(scored_signals, key=lambda x: x['_score'])
            return best_signal
        
        return None
    
    def _calculate_confidence(
        self,
        signals: List[Dict[str, Any]],
        strategy_alignment: List[str],
        indicator_confirmation: List[str],
        bars: pd.DataFrame
    ) -> float:
        """
        Calculate dynamic confidence based on multiple factors.
        Confidence range: 0-100%
        """
        confidence = 0.0
        
        # Strategy alignment (up to 50%)
        num_strategies = max(len(self.strategies), 1)
        aligned_strategies = len(strategy_alignment)
        strategy_score = (aligned_strategies / num_strategies) * 50
        confidence += strategy_score
        
        # Indicator confirmation (up to 30%)
        num_indicators = max(len(self.indicator_registry._registry), 1)
        confirmed_indicators = len(set(indicator_confirmation))
        indicator_score = (confirmed_indicators / num_indicators) * 30
        confidence += indicator_score
        
        # Trend strength (up to 20%)
        if bars is not None and len(bars) > 0:
            if 'ema_20' in bars.columns and 'ema_50' in bars.columns:
                latest_ema20 = bars['ema_20'].iloc[-1]
                latest_ema50 = bars['ema_50'].iloc[-1]
                
                if latest_ema20 > latest_ema50:
                    confidence += 10  # Bullish
                elif latest_ema20 < latest_ema50:
                    confidence += 10  # Bearish
        
        # Ensure confidence is in valid range
        confidence = max(0, min(100, confidence))
        
        return confidence
    
    def _calculate_tp_sl_levels(
        self,
        price: float,
        signal_type: str,
        bars: pd.DataFrame
    ) -> Tuple[List[float], float]:
        """
        Calculate Take Profit levels and Stop Loss with multiple targets.
        TP1: 1x ATR, TP2: 2x ATR, TP3: 3x ATR
        SL: 1.5x ATR
        """
        try:
            # Get ATR if available
            if 'atr_14' in bars.columns:
                atr = bars['atr_14'].iloc[-1]
            else:
                # Default ATR (1% of price)
                atr = price * 0.01
            
            if signal_type == 'BUY':
                tp1 = price + (atr * 1)   # Conservative TP
                tp2 = price + (atr * 2)   # Standard TP
                tp3 = price + (atr * 3)   # Aggressive TP
                sl = price - (atr * 1.5)  # SL
            else:  # SELL
                tp1 = price - (atr * 1)
                tp2 = price - (atr * 2)
                tp3 = price - (atr * 3)
                sl = price + (atr * 1.5)
            
            return [tp1, tp2, tp3], sl
            
        except Exception as e:
            self.logger.error(f"Error calculating TP/SL: {e}")
            # Fallback to 1% TP/SL
            if signal_type == 'BUY':
                return [price * 1.01, price * 1.02, price * 1.03], price * 0.99
            else:
                return [price * 0.99, price * 0.98, price * 0.97], price * 1.01
    
    async def _send_signal(self, signal_data: Dict[str, Any]) -> None:
        """Send signal to Telegram with professional formatting."""
        symbol = signal_data['symbol']
        signal_type = signal_data['signal']
        price = signal_data['price']
        tp1 = signal_data['tp1']
        tp2 = signal_data['tp2']
        tp3 = signal_data['tp3']
        sl = signal_data['sl']
        confidence = signal_data['confidence']
        indicators = signal_data['indicators']
        checksum = signal_data['checksum']
        timestamp = signal_data['timestamp']
        strategy_name = signal_data['strategy_name']
        
        # Determine trend bias
        trend_bias = "🟢 Bullish" if signal_type == 'BUY' else "🔴 Bearish"
        
        # Calculate risk-reward ratio (using TP2 as main target)
        if signal_type == 'BUY':
            rr_ratio = (tp2 - price) / (price - sl) if price > sl else 0
        else:
            rr_ratio = (price - tp2) / (sl - price) if sl > price else 0
        
        # Calculate position size and risk amount
        risk_amount = self.capital * self.risk_per_trade
        if signal_type == 'BUY':
            position_size = risk_amount / (price - sl) if price > sl else 0
        else:
            position_size = risk_amount / (sl - price) if sl > price else 0
        
        # Get market structure status
        market_structure = self._get_market_structure_status()
        
        # Get volume confirmation
        volume_status = self._get_volume_status()
        
        # Get volatility state
        volatility_state = self._get_volatility_state()
        
        # Get active data source
        data_source = self.connector.get_status().get('active_data_source', 'Unknown')
        price_deviation_pct = signal_data.get('price_deviation', 0) * 100
        primary_source = signal_data.get('primary_source', data_source)
        secondary_source = signal_data.get('secondary_source', 'N/A')
        
        # Format message with APEX SIGNAL BOT™ branding
        message = f"""
APEX SIGNAL BOT™ 🚀
━━━━━━━━━━━━━━━━━━

Pair: {symbol}
Direction: {signal_type}
Entry: ${price:,.2f}
Stop Loss: ${sl:,.2f}
Take Profit 1: ${tp1:,.2f}
Take Profit 2: ${tp2:,.2f}
Take Profit 3: ${tp3:,.2f}
Risk/Reward: 1:{rr_ratio:.1f}
Confidence: {confidence:.0f}%
Capital Allocation: ${self.capital:.2f}
Position Size: {position_size:.6f} units

━━━━━━━━━━━━━━━━━━

Indicators Alignment Summary: {', '.join(indicators[:5])}
Market Structure Status: {market_structure}
Volume Confirmation: {volume_status}
Volatility State: {volatility_state}

━━━━━━━━━━━━━━━━━━

🧮 Price Checksum: {checksum[:12]}...
📊 Price Deviation: {price_deviation_pct:.2f}%
📡 Primary Source: {primary_source}
📡 Secondary Source: {secondary_source}
🧠 Strategy: {strategy_name}

━━━━━━━━━━━━━━━━━━

⏰ UTC Timestamp: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}

━━━━━━━━━━━━━━━━━━

⚠️ Educational signal. Not financial advice.
"""
        
        await self._send_telegram_message(message)
        self.logger.info(f"📨 Sent {signal_type} signal for {symbol} (confidence: {confidence:.0f}%, strategy: {strategy_name})")
    
    def _get_market_structure_status(self) -> str:
        """Get current market structure status."""
        # This would analyze HH/HL, LH/LL, etc.
        # For now, return a placeholder
        return "Analyzing..."
    
    def _get_volume_status(self) -> str:
        """Get current volume confirmation status."""
        # This would analyze volume spikes, OBV, etc.
        # For now, return a placeholder
        return "Checking..."
    
    def _get_volatility_state(self) -> str:
        """Get current volatility state."""
        # This would analyze ATR, BB, etc.
        # For now, return a placeholder
        return "Measuring..."
    
    async def _send_error_notification(self, error: str) -> None:
        """Send error notification to Telegram."""
        if not self.telegram_notifier:
            return
        
        message = f"""
⚠️ ERROR DETECTED - APEX SIGNAL BOT™
━━━━━━━━━━━━━━━━━━
❌ Error: {error}
⏰ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
━━━━━━━━━━━━━━━━━━
"""
        await self._send_telegram_message(message)
    
    async def _send_telegram_message(self, message: str) -> None:
        """Send message to Telegram (or log in test mode)."""
        if self.mode == Mode.LIVE_SIGNAL and self.telegram_notifier:
            try:
                success = self.telegram_notifier.send_notification(message)
                if not success:
                    self.logger.warning("⚠️ Failed to send Telegram message")
            except Exception as e:
                self.logger.error(f"❌ Error sending Telegram message: {e}")
        else:
            self.logger.info(f"[TELEGRAM TEST] {message[:100]}...")
    
    async def shutdown(self) -> None:
        """Graceful shutdown."""
        self.logger.info("🛑 Shutting down bot...")
        self.is_running = False
        self.healthy = False
        
        # Send daily summary before shutdown
        if self.telegram_notifier:
            await self._send_daily_summary()


# Main entry point
if __name__ == '__main__':
    import asyncio
    
    async def main():
        bot = SignalBot()
        
        # Initialize bot
        if not await bot.initialize():
            logger = logging.getLogger(__name__)
            logger.error("❌ Bot initialization failed")
            logger.error("❌ CANNOT OPERATE WITHOUT LIVE DATA")
            sys.exit(1)
        
        # Run bot
        try:
            await bot.run()
        except KeyboardInterrupt:
            logger = logging.getLogger(__name__)
            logger.info("🛑 Bot stopped by user")
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"❌ Bot crashed: {e}")
            sys.exit(1)
    
    asyncio.run(main())