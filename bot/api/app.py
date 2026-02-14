"""FastAPI application for Apex Signal Bot."""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging
import asyncio

logger = logging.getLogger(__name__)


def create_app(database=None, signal_bot=None) -> FastAPI:
    """
    Create FastAPI application and attach SignalBot (if provided).
    FastAPI startup will initialize the bot and schedule the main loop as a background task.
    """
    app = FastAPI(
        title="APEX SIGNAL™ API",
        description="Production-grade trading signal platform",
        version="2.0.0"
    )

    # Store references
    app.state.db = database
    # If caller didn't provide a bot, it will be created on startup by main.
    app.state.bot = signal_bot

    # Metrics counters
    app.state.metrics = {
        'signals_emitted_total': 0,
        'connector_failures_total': {},
        'signals_by_confidence_bucket': {
            'LOW': 0,
            'MEDIUM': 0,
            'HIGH': 0,
            'VERY_HIGH': 0
        }
    }

    @app.on_event("startup")
    async def startup_event():
        logger.info("🚀 APEX SIGNAL™ API starting up")
        # If bot instance not attached, do not auto-create here to avoid unexpected side-effects.
        if not app.state.bot:
            logger.warning("No SignalBot instance attached to app.state.bot - API will run without live bot")
            return

        # Initialize the bot (await) and then schedule its run loop in background.
        try:
            init_ok = await app.state.bot.initialize()
            if not init_ok:
                logger.error("SignalBot initialization failed during API startup. Bot will not run.")
                return

            # Schedule the bot run loop as a background task (non-blocking)
            loop = asyncio.get_running_loop()
            loop.create_task(app.state.bot.run())
            logger.info("SignalBot run task scheduled (background)")
        except Exception:
            logger.exception("Failed to initialize/schedule SignalBot")

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("🛑 APEX SIGNAL™ API stopping")
        if app.state.bot and getattr(app.state.bot, "is_running", False):
            try:
                await app.state.bot.shutdown()
            except Exception:
                logger.exception("Error while shutting down the bot")

    @app.get("/healthz")
    async def health_check():
        """Health check endpoint (returns 200 if healthy)."""
        status = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'apex-signal-bot'
        }

        # Check database connection
        if app.state.db:
            try:
                metrics = app.state.db.get_metrics()
                status['database'] = 'connected'
                status['total_signals'] = metrics.get('total_signals', 0)
            except Exception as e:
                status['database'] = f'error: {str(e)}'

        # Check bot status
        bot = app.state.bot
        if bot:
            status['bot_running'] = bool(bot.is_running)
            status['bot_mode'] = getattr(bot, "mode", "unknown")
            status['bot_healthy'] = bool(getattr(bot, "healthy", False))
            status['last_signal_time'] = getattr(bot, "last_signal_time", None).isoformat() if getattr(bot, "last_signal_time", None) else None
            status['signals_emitted_total'] = getattr(bot, "signal_count", 0)
        else:
            status['bot_running'] = False
            status['bot_mode'] = 'unknown'
            status['bot_healthy'] = False

        # Use HTTP 200 for healthy but include bot_healthy flag so CI/ops can inspect
        return JSONResponse(status_code=200, content=status)

    @app.get("/metrics")
    async def get_metrics():
        metrics = {
            'signals_emitted_total': app.state.metrics['signals_emitted_total'],
            'signals_by_confidence_bucket': app.state.metrics['signals_by_confidence_bucket'],
            'connector_failures_total': app.state.metrics['connector_failures_total'],
            'timestamp': datetime.utcnow().isoformat()
        }
        if app.state.db:
            try:
                db_metrics = app.state.db.get_metrics()
                metrics['database'] = db_metrics
            except Exception:
                logger.exception("Could not include database metrics")
        return JSONResponse(content=metrics)

    @app.get("/status")
    async def get_status():
        if not app.state.bot:
            raise HTTPException(status_code=503, detail="Bot not initialized")
        bot = app.state.bot
        status = {
            'mode': getattr(bot, "mode", "unknown"),
            'is_running': bool(getattr(bot, "is_running", False)),
            'start_time': getattr(bot, "start_time", None).isoformat() if getattr(bot, "start_time", None) else None,
            'signal_count': getattr(bot, "signal_count", 0),
            'heartbeat_count': getattr(bot, "heartbeat_count", 0),
            'capital': getattr(bot, "capital", None),
            'risk_per_trade': getattr(bot, "risk_per_trade", None),
            'active_strategies': len(getattr(bot, "strategies", {})),
            'active_indicators': len(getattr(bot, "indicators", {})),
            'last_signal_time': getattr(bot, "last_signal_time", None).isoformat() if getattr(bot, "last_signal_time", None) else None,
            'timestamp': datetime.utcnow().isoformat()
        }
        return status

    @app.get("/signals")
    async def list_signals(limit: int = Query(100, ge=1, le=1000), symbol: Optional[str] = Query(None)):
        if not app.state.db:
            raise HTTPException(status_code=503, detail="Database not initialized")
        signals = app.state.db.get_signals(limit=limit, symbol=symbol)
        return {'count': len(signals), 'signals': [s.to_dict() for s in signals]}

    @app.get("/lastsignal")
    async def get_last_signal():
        if not app.state.db:
            raise HTTPException(status_code=503, detail="Database not initialized")
        signals = app.state.db.get_signals(limit=1)
        if not signals:
            return {'message': 'No signals found'}
        return signals[0].to_dict()

    @app.get("/")
    async def root():
        return {
            'service': 'APEX SIGNAL™',
            'version': '2.0.0',
            'status': 'running',
            'endpoints': {
                'healthz': '/healthz',
                'metrics': '/metrics',
                'status': '/status',
                'signals': '/signals',
                'lastsignal': '/lastsignal'
            }
        }

    return app
