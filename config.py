"""
APEX SIGNAL™ - Centralized Configuration with Safe Mode
Validates environment variables and provides safe defaults for all subsystems.
"""

import os
import logging
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    dotenv_path = Path(__file__).parent / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)
        logging.info("✅ Loaded environment variables from .env file")
except ImportError:
    logging.warning("⚠️  python-dotenv not installed, .env file will not be loaded")

# Import env_loader for backward compatibility
from bot.utils.env_loader import get_env_loader

logger = logging.getLogger(__name__)


class Config:
    """
    Central configuration class with safe mode flags.
    Ensures the system boots without secrets but disables trading/Telegram appropriately.
    """
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        # Load environment via env_loader
        self.env_loader = get_env_loader()
        
        # Operating mode (VERIFIED_TEST or LIVE_SIGNAL)
        self.mode = self.env_loader.mode
        
        # Safe mode flags - critical for production stability
        self.trading_enabled = self._determine_trading_enabled()
        self.telegram_enabled = self._determine_telegram_enabled()
        
        # Application settings
        self.app_name = "APEX SIGNAL™"
        self.version = "3.0.0"
        self.build_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        self.port = int(os.environ.get('PORT', '8000'))
        
        # Capital and risk management
        self.capital = self.env_loader.get_capital()  # Default $50
        self.risk_per_trade = self.env_loader.get_risk_per_trade()  # Default 1.5%
        
        # API credentials (may be None)
        self.alpaca_api_key = self.env_loader.alpaca_api_key
        self.alpaca_secret_key = self.env_loader.alpaca_api_secret
        self.polygon_api_key = self.env_loader.polygon_api_key
        self.telegram_bot_token = self.env_loader.telegram_token
        self.telegram_chat_id = self.env_loader.telegram_chat_id
        
        # Database (optional)
        self.database_url = self.env_loader.get_database_url()
        
        # Logging
        self.log_level = os.environ.get('LOG_LEVEL', 'INFO')
        
        # Log initialization status
        self._log_initialization_status()
    
    def _determine_trading_enabled(self) -> bool:
        """
        Determine if trading should be enabled.
        Trading is enabled only when ALL required trading API keys are present.
        """
        has_alpaca = bool(self.env_loader.alpaca_api_key and self.env_loader.alpaca_api_secret)
        has_polygon = bool(self.env_loader.polygon_api_key)
        
        trading_enabled = has_alpaca and has_polygon
        
        if not trading_enabled:
            logger.warning("⚠️  TRADING DISABLED - Missing required API keys (ALPACA_API_KEY, ALPACA_SECRET_KEY, POLYGON_API_KEY)")
            logger.info("📊 Bot will run in data-only mode for analysis and testing")
        else:
            logger.info("✅ TRADING ENABLED - All required API keys present")
        
        return trading_enabled
    
    def _determine_telegram_enabled(self) -> bool:
        """
        Determine if Telegram notifications should be enabled.
        Telegram is enabled only when both BOT_TOKEN and CHAT_ID are present.
        """
        has_token = bool(self.env_loader.telegram_token and self.env_loader.telegram_token.strip())
        has_chat_id = bool(self.env_loader.telegram_chat_id and self.env_loader.telegram_chat_id.strip())
        
        telegram_enabled = has_token and has_chat_id
        
        if not telegram_enabled:
            logger.warning("⚠️  TELEGRAM DISABLED - Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
            logger.info("📊 Bot will run without Telegram notifications")
        else:
            logger.info("✅ TELEGRAM ENABLED - Credentials present")
        
        return telegram_enabled
    
    def _log_initialization_status(self):
        """Log the initialization status for observability."""
        logger.info("=" * 60)
        logger.info(f"🚀 {self.app_name} v{self.version}")
        logger.info(f"📦 Build Date: {self.build_date}")
        logger.info(f"🔧 Mode: {self.mode}")
        logger.info(f"💰 Capital: ${self.capital:.2f}")
        logger.info(f"⚠️  Risk Per Trade: {self.risk_per_trade * 100:.2f}%")
        logger.info(f"🔌 Trading: {'✅ ENABLED' if self.trading_enabled else '❌ DISABLED'}")
        logger.info(f"📱 Telegram: {'✅ ENABLED' if self.telegram_enabled else '❌ DISABLED'}")
        logger.info(f"🌐 Port: {self.port}")
        logger.info("=" * 60)
    
    def validate(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate configuration and return status with details.
        
        Returns:
            Tuple of (is_valid, validation_dict)
        """
        validation = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'mode': self.mode,
            'trading_enabled': self.trading_enabled,
            'telegram_enabled': self.telegram_enabled
        }
        
        # Check for warnings (non-critical)
        if not self.trading_enabled and self.mode == 'LIVE_SIGNAL':
            validation['warnings'].append("Trading enabled but missing API keys - running in data-only mode")
        
        if not self.telegram_enabled and self.mode == 'LIVE_SIGNAL':
            validation['warnings'].append("Telegram disabled - no signals will be sent")
        
        # Log warnings
        for warning in validation['warnings']:
            logger.warning(f"⚠️  CONFIG WARNING: {warning}")
        
        # Determine if config is valid for the current mode
        if self.mode == 'LIVE_SIGNAL':
            # In LIVE mode, we require either trading or Telegram to be enabled
            if not self.trading_enabled and not self.telegram_enabled:
                validation['valid'] = False
                validation['errors'].append("LIVE mode requires at least trading or Telegram to be enabled")
        
        # Log errors
        for error in validation['errors']:
            logger.error(f"❌ CONFIG ERROR: {error}")
        
        return validation['valid'], validation
    
    def get_settings(self) -> Dict[str, Any]:
        """
        Get all settings as a dictionary (for debugging and health endpoints).
        Secrets are redacted for safety.
        """
        return {
            'app_name': self.app_name,
            'version': self.version,
            'build_date': self.build_date,
            'mode': self.mode,
            'port': self.port,
            'capital': self.capital,
            'risk_per_trade': self.risk_per_trade,
            'trading_enabled': self.trading_enabled,
            'telegram_enabled': self.telegram_enabled,
            'has_alpaca_api': bool(self.alpaca_api_key),
            'has_polygon_api': bool(self.polygon_api_key),
            'has_telegram_token': bool(self.telegram_bot_token),
            'has_telegram_chat_id': bool(self.telegram_chat_id),
            'has_database': bool(self.database_url),
            'log_level': self.log_level
        }
    
    def get_telegram_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """Get Telegram credentials (may be None if disabled)."""
        if self.telegram_enabled:
            return self.telegram_bot_token, self.telegram_chat_id
        return None, None
    
    def get_alpaca_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """Get Alpaca credentials (may be None if trading disabled)."""
        if self.trading_enabled:
            return self.alpaca_api_key, self.alpaca_secret_key
        return None, None
    
    def get_polygon_credentials(self) -> Optional[str]:
        """Get Polygon API key (may be None if trading disabled)."""
        if self.trading_enabled:
            return self.polygon_api_key
        return None


# Global config instance
_config = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def validate_config() -> Tuple[bool, Dict[str, Any]]:
    """Validate the global configuration."""
    config = get_config()
    return config.validate()