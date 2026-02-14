#!/usr/bin/env python3
"""
APEX SIGNAL™ - Main Application Entry Point
Production-grade startup with config validation, health checks, and graceful error handling.
"""

import sys
import os
import logging
import signal
import asyncio
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import get_config, validate_config
from bot.utils.logger import setup_logger

# Load metadata
def load_metadata() -> dict:
    """Load system metadata from metadata.json."""
    metadata_path = Path(__file__).parent / "metadata.json"
    try:
        with open(metadata_path, 'r') as f:
            return json.load(f)
    except Exception:
        return {
            "name": "APEX SIGNAL™",
            "version": "3.0.0",
            "build_date": datetime.utcnow().isoformat(),
            "git_commit": "unknown"
        }

logger = None


class Application:
    """Main application orchestrator with graceful startup and shutdown."""
    
    def __init__(self):
        """Initialize application with config validation."""
        self.config = get_config()
        self.metadata = load_metadata()
        self.is_running = False
        self.tasks = []
        self.start_time = None
        
    def print_startup_banner(self):
        """Print branded startup banner."""
        banner = f"""
{'=' * 70}
🛡️  {self.metadata['name']} • v{self.metadata['version']}
{'=' * 70}
📦 Build Date: {self.metadata['build_date']}
🔧 Git Commit: {self.metadata['git_commit']}
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
        """
        Validate configuration before starting the application.
        
        Returns:
            True if validation passed, False otherwise
        """
        global logger
        
        # Setup logging first
        logger = setup_logger("APEX_SIGNAL", self.config.log_level)
        
        # Print branded banner
        self.print_startup_banner()
        
        logger.info("🚀 Starting APEX SIGNAL™ application...")
        
        # Validate configuration
        is_valid, validation = validate_config()
        
        if not is_valid:
            logger.error("❌ Configuration validation failed!")
            for error in validation['errors']:
                logger.error(f"   - {error}")
            logger.error("Cannot start application. Please fix configuration issues.")
            return False
        
        # Log warnings
        if validation['warnings']:
            logger.warning("⚠️  Configuration warnings detected:")
            for warning in validation['warnings']:
                logger.warning(f"   - {warning}")
        
        logger.info("✅ Configuration validation passed")
        logger.info(f"   Mode: {self.config.mode}")
        logger.info(f"   Trading: {'ENABLED' if self.config.trading_enabled else 'DISABLED'}")
        logger.info(f"   Telegram: {'ENABLED' if self.config.telegram_enabled else 'DISABLED'}")
        
        return True
    
    async def start(self):
        """Start the application components."""
        global logger
        
        if not self.is_running:
            try:
                self.start_time = datetime.utcnow()
                
                # Import and initialize signal bot
                logger.info("🤖 Initializing signal bot...")
                from bot.signal_bot import SignalBot
                from bot.api.app import create_app
                
                # Create signal bot instance
                signal_bot = SignalBot()
                
                # Create FastAPI application
                logger.info("🌐 Creating FastAPI application...")
                api_app = create_app(signal_bot=signal_bot)
                
                # Import uvicorn for serving
                import uvicorn
                
                # Configure uvicorn
                config = uvicorn.Config(
                    app=api_app,
                    host="0.0.0.0",
                    port=self.config.port,
                    loop="asyncio",
                    workers=1,
                    log_level=self.config.log_level.lower()
                )
                
                server = uvicorn.Server(config)
                
                # Store reference for shutdown
                self.api_server = server
                self.is_running = True
                
                logger.info(f"✅ Application started successfully on port {self.config.port}")
                logger.info(f"   Health check: http://0.0.0.0:{self.config.port}/healthz")
                logger.info(f"   API docs: http://0.0.0.0:{self.config.port}/docs")
                
                # Start the server
                await server.serve()
                
            except Exception as e:
                logger.error(f"❌ Failed to start application: {e}")
                logger.exception("Full traceback:")
                self.is_running = False
                raise
    
    async def stop(self):
        """Stop the application gracefully."""
        global logger
        
        if self.is_running:
            logger.info("🛑 Stopping application...")
            
            # Cancel any background tasks
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
        """Run the application with signal handling."""
        global logger
        
        # Validate startup configuration
        if not self.validate_startup():
            sys.exit(1)
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"📡 Received signal {signum}, shutting down...")
            self.is_running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Run the async application
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            logger.info("👋 Interrupted by user")
        except Exception as e:
            logger.error(f"❌ Application crashed: {e}")
            logger.exception("Full traceback:")
            sys.exit(1)


def health_check():
    """
    Simple health check function for Docker.
    Returns exit code 0 if healthy, 1 otherwise.
    """
    try:
        import requests
        port = os.environ.get('PORT', '8000')
        response = requests.get(f"http://localhost:{port}/healthz", timeout=5)
        return 0 if response.status_code == 200 else 1
    except Exception as e:
        print(f"Health check failed: {e}")
        return 1


if __name__ == "__main__":
    # Determine mode: run app or health check
    if len(sys.argv) > 1 and sys.argv[1] == "--health-check":
        sys.exit(health_check())
    else:
        app = Application()
        app.run()