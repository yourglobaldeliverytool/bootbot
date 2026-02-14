"""Environment variable loader for Railway deployment."""

import os
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class EnvLoader:
    """Load and validate environment variables for the signal bot."""
    
    def __init__(self):
        """Initialize the environment loader."""
        self.telegram_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        self.database_url = os.environ.get('DATABASE_URL')
        self.railway_env = os.environ.get('RAILWAY_ENVIRONMENT', 'development')
        self.port = int(os.environ.get('PORT', '8000'))
        
        # Capital management (default $50 as per requirements)
        try:
            self.capital = float(os.environ.get('CAPITAL', '50'))
        except (ValueError, TypeError):
            logger.warning("Invalid CAPITAL value, using default $50")
            self.capital = 50.0
        
        # Risk per trade from environment (optional, falls back to config)
        try:
            self.risk_per_trade = float(os.environ.get('RISK_PERCENT', '1.5')) / 100
        except (ValueError, TypeError):
            self.risk_per_trade = 0.015
        
        # Alpaca API credentials (optional)
        self.alpaca_api_key = os.environ.get('ALPACA_API_KEY')
        self.alpaca_api_secret = os.environ.get('ALPACA_SECRET_KEY')
        
        # Polygon API key (optional)
        self.polygon_api_key = os.environ.get('POLYGON_API_KEY')
        self.polygon_api_base = os.environ.get('POLYGON_API_BASE')
        
        # TradingView webhook secret (optional)
        self.tradingview_webhook_secret = os.environ.get('TRADINGVIEW_WEBHOOK_SECRET')
        
        # Detect operating mode
        self.mode = self._detect_mode()
    
    def _detect_mode(self) -> str:
        """
        Detect operating mode based on environment variables.
        
        Returns:
            'LIVE_SIGNAL' if both TELEGRAM_TOKEN and TELEGRAM_CHAT_ID are present
            'VERIFIED_TEST' otherwise
        """
        has_token = bool(self.telegram_token and self.telegram_token.strip())
        has_chat_id = bool(self.telegram_chat_id and self.telegram_chat_id.strip())
        
        if has_token and has_chat_id:
            logger.info("🚀 LIVE_SIGNAL mode detected - both TELEGRAM_TOKEN and TELEGRAM_CHAT_ID are present")
            return 'LIVE_SIGNAL'
        else:
            logger.info("🧪 VERIFIED_TEST mode detected - missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID")
            return 'VERIFIED_TEST'
    
    def is_live_mode(self) -> bool:
        """Check if running in live mode."""
        return self.mode == 'LIVE_SIGNAL'
    
    def get_telegram_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Get Telegram credentials.
        
        Returns:
            Tuple of (token, chat_id) - both may be None in test mode
        """
        return self.telegram_token, self.telegram_chat_id
    
    def get_database_url(self) -> Optional[str]:
        """Get database URL (for Postgres on Railway)."""
        return self.database_url
    
    def is_railway(self) -> bool:
        """Check if running on Railway."""
        return self.railway_env != 'development'
    
    def get_port(self) -> int:
        """Get the port to listen on (defaults to 8000)."""
        return self.port
    
    def validate(self) -> Tuple[bool, list]:
        """
        Validate environment configuration.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # In live mode, require Telegram credentials
        if self.is_live_mode():
            if not self.telegram_token:
                errors.append("TELEGRAM_BOT_TOKEN is required in LIVE_SIGNAL mode")
            if not self.telegram_chat_id:
                errors.append("TELEGRAM_CHAT_ID is required in LIVE_SIGNAL mode")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def get_env_summary(self) -> dict:
        """Get a summary of environment configuration (without secrets)."""
        return {
            'mode': self.mode,
            'railway_env': self.railway_env,
            'port': self.port,
            'has_telegram_token': bool(self.telegram_token),
            'has_telegram_chat_id': bool(self.telegram_chat_id),
            'has_database_url': bool(self.database_url),
            'capital': self.capital,
            'risk_per_trade': self.risk_per_trade,
            'has_alpaca_api': bool(self.alpaca_api_key),
            'has_polygon_api': bool(self.polygon_api_key),
        }
    
    def get_capital(self) -> float:
        """Get capital amount."""
        return self.capital
    
    def get_risk_per_trade(self) -> float:
        """Get risk per trade percentage."""
        return self.risk_per_trade
    
    def get_alpaca_credentials(self) -> tuple:
        """Get Alpaca API credentials."""
        return self.alpaca_api_key, self.alpaca_api_secret
    
    def get_polygon_credentials(self) -> tuple:
        """Get Polygon API credentials."""
        return self.polygon_api_key, self.polygon_api_base


# Global instance
_env_loader = None


def get_env_loader() -> EnvLoader:
    """Get the global environment loader instance."""
    global _env_loader
    if _env_loader is None:
        _env_loader = EnvLoader()
    return _env_loader