# bot/core/engine.py
"""
Core trading engine that orchestrates strategies, indicators, and notifications.
Now supports continuous async execution, heartbeat, safe notification dispatch.
"""

from typing import Dict, List, Optional, Any, Callable, Coroutine
import pandas as pd
import logging
from datetime import datetime, timedelta
import asyncio

from bot.core.interfaces import Strategy, Indicator, Notifier  # keep typing only
from bot.core.registry import StrategyRegistry, IndicatorRegistry, NotifierRegistry


class TradingEngine:
    """
    Main trading engine that coordinates all trading components and can run continuously.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = self._setup_logger()

        # Registries (assume implementations in repo)
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

        # Tasks
        self._main_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

        self.logger.info("TradingEngine initialized")

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger("TradingEngine")
        logger.setLevel(getattr(logging, self.config.get("log_level", "INFO")))
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    # --- loading helpers (unchanged behavior) ---
    def load_strategy(self, strategy_name: str, parameters: Optional[Dict[str, Any]] = None) -> bool:
        strategy = self.strategy_registry.create_instance(strategy_name, parameters)
        if strategy is None:
            self.logger.error(f"Failed to load strategy: {strategy_name}")
            return False
        strategy.logger = self.logger
        self.active_strategies[strategy_name] = strategy
        self.logger.info(f"Strategy loaded: {strategy_name}")
        return True

    def load_indicator(self, indicator_name: str, parameters: Optional[Dict[str, Any]] = None) -> bool:
        indicator = self.indicator_registry.create_instance(indicator_name, parameters)
        if indicator is None:
            self.logger.error(f"Failed to load indicator: {indicator_name}")
            return False
        indicator.logger = self.logger
        self.active_indicators[indicator_name] = indicator
        self.logger.info(f"Indicator loaded: {indicator_name}")
        return True

    def load_notifier(self, notifier_name: str, parameters: Optional[Dict[str, Any]] = None) -> bool:
        notifier = self.notifier_registry.create_instance(notifier_name, parameters)
        if notifier is None:
            self.logger.error(f"Failed to load notifier: {notifier_name}")
            return False
        # ensure notifier has expected API (we will use send_notification)
        notifier.logger = self.logger
        self.active_notifiers[notifier_name] = notifier
        self.logger.info(f"Notifier loaded: {notifier_name}")
        return True

    def attach_indicator_to_strategy(self, indicator_name: str, strategy_name: str) -> bool:
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

    # --- execution and notifier logic ---
    def execute_strategies(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Execute all active strategies synchronously on the provided data.
        Non-blocking regarding notifications (they schedule async tasks if needed).
        """
        signals = []
        self.execution_count += 1
        self.last_execution = datetime.utcnow()

        self.logger.info(f"Executing {len(self.active_strategies)} strategies (exec #{self.execution_count})")

        for strategy_name, strategy in list(self.active_strategies.items()):
            try:
                signal = strategy.generate_signal(data)
                if not isinstance(signal, dict):
                    self.logger.warning(f"Strategy {strategy_name} returned non-dict signal, skipping")
                    continue

                # Append only if valid structure
                signals.append(signal)
                self.logger.debug(
                    f"Strategy '{strategy_name}' generated signal: {signal.get('signal', 'N/A')}"
                )

                # Only notify on meaningful signals (avoid HOLD and None)
                sig_type = (signal.get("signal", None) or "").upper()
                if sig_type in ("BUY", "SELL", "SHORT", "COVER"):
                    # send notifications but protect against notifier API differences
                    self._send_signal_notifications(signal)
                else:
                    self.logger.debug(f"Skipping notification for non-trade signal: {sig_type}")

            except Exception as e:
                self.logger.error(f"Error executing strategy '{strategy_name}': {e}", exc_info=True)

        self.logger.info(f"Generated {len(signals)} signals")
        return signals

    def _send_signal_notifications(self, signal: Dict[str, Any]) -> None:
        """
        Send notifications for a signal through all active notifiers.
        This method is synchronous but notifiers may schedule async tasks internally.
        """
        for notifier_name, notifier in list(self.active_notifiers.items()):
            try:
                if hasattr(notifier, "is_enabled") and not notifier.is_enabled():
                    self.logger.debug(f"Notifier {notifier_name} is disabled, skipping")
                    continue

                # Preferred API: send_notification(message, signal)
                # Build a formatted message (engine-level default). Notifiers may accept (message, signal).
                message = self._format_signal_message(signal)

                # If notifier exposes send_notification, call it.
                if hasattr(notifier, "send_notification"):
                    try:
                        ok = notifier.send_notification(message, signal)
                        if ok:
                            self.logger.debug(f"Notification sent via {notifier_name}")
                        else:
                            self.logger.warning(f"Notifier {notifier_name} returned False")
                    except Exception:
                        # If send_notification is async, try to schedule it
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                loop.create_task(self._call_notifier_async_wrapper(notifier, message, signal))
                            else:
                                asyncio.run(self._call_notifier_async_wrapper(notifier, message, signal))
                        except Exception:
                            self.logger.exception(f"Failed to dispatch async notification via {notifier_name}")

                # Fallbacks: older notifiers may have send_signal or send_message
                elif hasattr(notifier, "send_signal"):
                    try:
                        notifier.send_signal(signal, compact=False)
                        self.logger.debug(f"Notification (send_signal) scheduled via {notifier_name}")
                    except Exception:
                        self.logger.exception(f"Failed to call send_signal on {notifier_name}")
                elif hasattr(notifier, "send_message"):
                    try:
                        notifier.send_message(message)
                        self.logger.debug(f"Notification (send_message) called via {notifier_name}")
                    except Exception:
                        self.logger.exception(f"Failed to call send_message on {notifier_name}")
                else:
                    self.logger.warning(f"Notifier {notifier_name} has no known send API")

            except Exception as e:
                self.logger.error(f"Error sending notification via {notifier_name}: {e}", exc_info=True)

    async def _call_notifier_async_wrapper(self, notifier, message: str, signal: Dict[str, Any]) -> None:
        """
        Async wrapper used to call async notifier methods in a safe manner.
        """
        try:
            if hasattr(notifier, "send_signal_async"):
                await notifier.send_signal_async(signal)
            elif hasattr(notifier, "send_message_async"):
                await notifier.send_message_async(message)
            elif hasattr(notifier, "send_notification"):
                # if send_notification is sync, run it in thread pool
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, notifier.send_notification, message, signal)
            elif hasattr(notifier, "send_signal"):
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, notifier.send_signal, signal, False)
            else:
                self.logger.warning("No async entry point found on notifier for async wrapper")
        except Exception:
            self.logger.exception("Async notifier wrapper failed")

    def _format_signal_message(self, signal: Dict[str, Any]) -> str:
        """
        Engine-level human readable message (fallback).
        """
        try:
            confidence = float(signal.get("confidence", 0.0))
        except Exception:
            confidence = 0.0
        return (
            f"📊 APEX SIGNAL • {signal.get('strategy_name', 'unknown')}\n"
            f"Signal: {signal.get('signal', 'N/A')}\n"
            f"Confidence: {confidence:.2%}\n"
            f"Reason: {signal.get('reason', 'N/A')}\n"
            f"Time: {datetime.utcnow().isoformat()}Z"
        )

    # --- engine runtime control (continuous mode) ---
    async def run_forever(
        self,
        data_provider: Callable[[], Coroutine[Any, Any, pd.DataFrame]],
        interval_seconds: int = 60,
        heartbeat_seconds: int = 3600,
    ) -> None:
        """
        Start the engine continuous loop:
            - data_provider: async callable that returns a pandas.DataFrame (OHLCV)
            - interval_seconds: interval between strategy runs
            - heartbeat_seconds: how often heartbeat messages are emitted
        """
        if self.is_running:
            self.logger.warning("Engine already running")
            return

        self.is_running = True
        self._main_task = asyncio.current_task()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(heartbeat_seconds))

        self.logger.info("🚀 TradingEngine entering continuous loop")
        try:
            while self.is_running:
                start_ts = datetime.utcnow()
                try:
                    data = await data_provider()
                    # data correctness check
                    if data is None or not isinstance(data, pd.DataFrame) or data.shape[0] == 0:
                        self.logger.warning("Data provider returned no data — skipping this iteration")
                    else:
                        self.execute_strategies(data)
                except Exception:
                    self.logger.exception("Error during main loop execution")

                # sleep to respect interval (adjust for execution time)
                elapsed = (datetime.utcnow() - start_ts).total_seconds()
                to_sleep = max(0, interval_seconds - elapsed)
                await asyncio.sleep(to_sleep)
        finally:
            self.logger.info("TradingEngine leaving continuous loop")
            # cancel heartbeat task
            if self._heartbeat_task and not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
            self.is_running = False

    async def _heartbeat_loop(self, heartbeat_seconds: int = 3600):
        """
        Periodic heartbeat that informs notifiers of system status.
        """
        self.logger.info(f"Starting heartbeat loop ({heartbeat_seconds}s)")
        try:
            while self.is_running:
                await asyncio.sleep(heartbeat_seconds)
                stats = {
                    "uptime": str(datetime.utcnow() - (self.last_execution or datetime.utcnow())),
                    "signals_last_hour": self.execution_count,
                    "last_trade_time": (self.last_execution.isoformat() if self.last_execution else "N/A"),
                    "cpu_percent": 0.0,
                    "memory_mb": 0.0,
                }
                for notifier_name, notifier in list(self.active_notifiers.items()):
                    try:
                        if hasattr(notifier, "send_heartbeat"):
                            notifier.send_heartbeat(stats)
                    except Exception:
                        self.logger.exception(f"Heartbeat notification failed for {notifier_name}")
        except asyncio.CancelledError:
            self.logger.debug("Heartbeat loop cancelled")
        except Exception:
            self.logger.exception("Heartbeat loop error")

    def start_background(self, loop_task: asyncio.Task) -> None:
        """
        Expose manual start if someone creates the loop outside of run_forever.
        """
        self._main_task = loop_task
        self.is_running = True

    async def stop(self) -> None:
        """
        Stop engine gracefully.
        """
        self.logger.info("Stopping TradingEngine...")
        self.is_running = False
        # cancel heartbeat if exists
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        self.logger.info("TradingEngine stopped")

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "active_strategies": len(self.active_strategies),
            "active_indicators": len(self.active_indicators),
            "active_notifiers": len(self.active_notifiers),
            "execution_count": self.execution_count,
            "last_execution": self.last_execution.isoformat() if self.last_execution else None,
        }
