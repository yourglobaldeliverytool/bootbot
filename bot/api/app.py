"""FastAPI application for Apex Signal Bot."""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


def create_app(database=None, signal_bot=None) -> FastAPI:
    """
    Create FastAPI application.
    
    Args:
        database: Database instance for persistence
        signal_bot: SignalBot instance for status
        
    Returns:
        FastAPI application
    """
    app = FastAPI(
        title="APEX SIGNAL™ API",
        description="Production-grade trading signal platform",
        version="2.0.0"
    )
    
    # Store references
    app.state.db = database
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
        logger.info("🚀 APEX SIGNAL™ API started")
    
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("🛑 APEX SIGNAL™ API stopped")
    
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
                # Try to get metrics from database
                metrics = app.state.db.get_metrics()
                status['database'] = 'connected'
                status['total_signals'] = metrics.get('total_signals', 0)
            except Exception as e:
                status['database'] = f'error: {str(e)}'
        
        # Check bot status
        if app.state.bot:
            status['bot_running'] = app.state.bot.is_running
            status['bot_mode'] = app.state.bot.mode
        else:
            status['bot_running'] = False
            status['bot_mode'] = 'unknown'
        
        return JSONResponse(status_code=200, content=status)
    
    @app.get("/metrics")
    async def get_metrics():
        """
        Get Prometheus-style metrics.
        Returns signal counts, connector health, etc.
        """
        metrics = {
            'signals_emitted_total': app.state.metrics['signals_emitted_total'],
            'signals_by_confidence_bucket': app.state.metrics['signals_by_confidence_bucket'],
            'connector_failures_total': app.state.metrics['connector_failures_total'],
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Add database metrics if available
        if app.state.db:
            db_metrics = app.state.db.get_metrics()
            metrics['database'] = db_metrics
        
        return JSONResponse(content=metrics)
    
    @app.get("/status")
    async def get_status():
        """Get current bot status (same as Telegram /status)."""
        if not app.state.bot:
            raise HTTPException(status_code=503, detail="Bot not initialized")
        
        status = {
            'mode': app.state.bot.mode,
            'is_running': app.state.bot.is_running,
            'start_time': app.state.bot.start_time.isoformat() if app.state.bot.start_time else None,
            'signal_count': app.state.bot.signal_count,
            'heartbeat_count': app.state.bot.heartbeat_count,
            'capital': app.state.bot.capital,
            'risk_per_trade': app.state.bot.risk_per_trade,
            'active_strategies': len(app.state.bot.strategies),
            'active_indicators': len(app.state.bot.indicators),
            'last_signal_time': app.state.bot.last_signal_time.isoformat() if app.state.bot.last_signal_time else None,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return status
    
    @app.get("/signals")
    async def list_signals(
        limit: int = Query(100, ge=1, le=1000),
        symbol: Optional[str] = Query(None, description="Filter by symbol")
    ):
        """List signals from database."""
        if not app.state.db:
            raise HTTPException(status_code=503, detail="Database not initialized")
        
        signals = app.state.db.get_signals(limit=limit, symbol=symbol)
        return {
            'count': len(signals),
            'signals': [s.to_dict() for s in signals]
        }
    
    @app.get("/signals/{signal_id}")
    async def get_signal(signal_id: int):
        """Get a specific signal by ID."""
        if not app.state.db:
            raise HTTPException(status_code=503, detail="Database not initialized")
        
        signal = app.state.db.get_signal_by_id(signal_id)
        if not signal:
            raise HTTPException(status_code=404, detail="Signal not found")
        
        return signal.to_dict()
    
    @app.post("/signals/{signal_id}/verify")
    async def verify_signal(signal_id: int):
        """
        Verify a signal by recalculating its checksum.
        Returns PASS/FAIL with details.
        """
        if not app.state.db:
            raise HTTPException(status_code=503, detail="Database not initialized")
        
        result = app.state.db.verify_signal(signal_id)
        
        if result['status'] == 'FAIL' and 'Signal not found' in result.get('reason', ''):
            raise HTTPException(status_code=404, detail=result['reason'])
        
        return result
    
    @app.get("/lastsignal")
    async def get_last_signal():
        """Get the most recent signal."""
        if not app.state.db:
            raise HTTPException(status_code=503, detail="Database not initialized")
        
        signals = app.state.db.get_signals(limit=1)
        if not signals:
            return {'message': 'No signals found'}
        
        return signals[0].to_dict()
    
    @app.get("/")
    async def root():
        """Root endpoint with API info."""
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