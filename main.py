#!/usr/bin/env python3
"""
APEX SIGNAL™ - Main Application Entry Point (robust)
"""

import sys
import os
import logging
import signal
import asyncio
import json
from pathlib import Path
from datetime import datetime

# add repo root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import get_config, validate_config
from bot.utils.logger import setup_logger

def load_metadata() -> dict:
    metadata_path = Path(__file__).parent / "metadata.json"
    try:
        with open(metadata_path, 'r') as f:
            return json.load(f)
    except Exception:
        return {"name": "APEX SIGNAL™", "version": "3.0.0", "build_date": datetime.utcnow().isoformat(), "git_commit": "unknown"}

logger = None

class Application:
    def __init__(self):
        self.config = get_config()
        self.metadata = load_metadata()
        self.is_running = False
        self.tasks = []
        self.start_time = None
        self.api_server = None

    def print_startup_banner(self):
        banner = f"""
{'=' * 70}
🛡️  {self.metadata.get('name')} • v{self.metadata.get('version')}
{'=' * 70}
📦 Build Date: {self.metadata.get('build_date')}
🔧 Git Commit: {self.metadata.get('git_commit')}
🎯 Trading Pairs: BTC/USD, ETH/USD, GOLD/USD
💰 Capital: ${self.config.capital:.2f}
⚠️  Risk Per Trade: {self.config.risk_per_trade * 100:.2f}%
🔌 Trading: {'✅ ENABLED' if self.config.trading_enabled else '❌ DISABLED'}
📱 Telegram: {'✅ ENABLED' if self.config.telegram_enabled else '❌ DISABLED'}
🌐 Port: {self.config.port}
🚀 Mode: {self.config.mode}
{'=' * 70}
"""
        print(banner)

    def validate_startup(self) -> bool:
        global logger
        logger = setup_logger("APEX_SIGNAL", self.config.log_level)
        self.print_startup_banner()
        logger.info("🚀 Starting APEX SIGNAL™ application...")
        is_valid, validation = validate_config()
        if not is_valid:
            logger.error("❌ Configuration validation failed!")
            for error in validation['errors']:
                logger.error(f"   - {error}")
            # do not hard exit; let app start in reduced functionality
            return False
        if validation['warnings']:
            logger.warning("⚠️ Configuration warnings detected:")
            for w in validation['warnings']:
                logger.warning(f"   - {w}")
        logger.info("✅ Configuration validation passed")
        return True

    async def start(self):
        global logger
        if not self.is_running:
            try:
                self.start_time = datetime.utcnow()
                logger.info("🤖 Initializing signal bot...")
                from bot.signal_bot import SignalBot
                from bot.api.app import create_app

                signal_bot = SignalBot()

                # initialize the bot BEFORE starting server so health endpoint can report actual state
                init_ok = await signal_bot.initialize()
                if not init_ok:
                    logger.warning("⚠️ SignalBot initialization reported failure. API will still start in degraded mode.")

                # create app with bot reference
                logger.info("🌐 Creating FastAPI application...")
                api_app = create_app(signal_bot=signal_bot)

                import uvicorn
                config = uvicorn.Config(
                    app=api_app,
                    host="0.0.0.0",
                    port=self.config.port,
                    loop="asyncio",
                    workers=1,
                    log_level=self.config.log_level.lower()
                )
                server = uvicorn.Server(config)
                self.api_server = server
                self.is_running = True
                logger.info(f"✅ Application started successfully on port {self.config.port}")
                logger.info(f"   Health check: http://0.0.0.0:{self.config.port}/healthz")
                logger.info(f"   API docs: http://0.0.0.0:{self.config.port}/docs")
                await server.serve()
            except Exception as e:
                logger.exception("❌ Failed to start application: %s", e)
                self.is_running = False
                raise

    async def stop(self):
        global logger
        if self.is_running:
            logger.info("🛑 Stopping application...")
            for task in self.tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            self.is_running = False
            logger.info("✅ Application stopped gracefully")

    def run(self):
        global logger
        # validate (logs errors/warnings)
        self.validate_startup()

        # setup signals
        def _handle(signum, frame):
            if logger:
                logger.info("📡 Received signal %s, shutting down...", signum)
            self.is_running = False

        signal.signal(signal.SIGINT, _handle)
        signal.signal(signal.SIGTERM, _handle)

        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            if logger:
                logger.info("👋 Interrupted by user")
        except Exception:
            if logger:
                logger.exception("❌ Application crashed")
            sys.exit(1)


def health_check() -> int:
    try:
        import requests
        port = os.environ.get('PORT', '8000')
        r = requests.get(f"http://localhost:{port}/healthz", timeout=5)
        return 0 if r.status_code == 200 else 1
    except Exception as e:
        print("Health check failed:", e)
        return 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--health-check":
        sys.exit(health_check())
    else:
        app = Application()
        app.run()
