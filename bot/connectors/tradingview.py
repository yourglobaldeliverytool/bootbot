"""
TradingView connector for webhook-based alerts.
Can receive TradingView alerts and provide fallback price data.
"""

import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

import pandas as pd

from bot.connectors.base import BaseDataConnector


class TradingViewConnector(BaseDataConnector):
    """
    TradingView connector for webhook alerts and price data.
    
    This connector can:
    1. Receive webhook alerts from TradingView
    2. Provide fallback price data from TradingView's public data
    3. Track alert history
    
    Note: TradingView doesn't have a public API for fetching historical data,
    so this connector primarily serves as a webhook receiver and backup.
    """
    
    CONNECTOR_NAME = "tradingview"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Alert storage
        self.alert_history: List[Dict[str, Any]] = []
        self.webhook_url = self.config.get('tradingview', {}).get('webhook_url')
        
        # Symbol mapping
        self.symbol_map = {
            'BTCUSDT': 'BINANCE:BTCUSDT',
            'ETHUSDT': 'BINANCE:ETHUSDT',
            'XAUUSD': 'TVC:GOLD',  # Gold on TradingView
        }
        
        # Mock price data for testing (since TradingView has no public API)
        self.mock_prices = {
            'BTCUSDT': 67000.00,
            'ETHUSDT': 3500.00,
            'XAUUSD': 2800.00,
        }
    
    def _validate_credentials(self) -> bool:
        """
        Validate TradingView connector.
        Since TradingView uses webhooks, we just check configuration.
        """
        try:
            self.logger.info(f"{self.CONNECTOR_NAME} connector initialized (webhook mode)")
            self.is_connected = True
            return True
                
        except Exception as e:
            self.logger.error(f"{self.CONNECTOR_NAME} validation error: {e}")
            return False
    
    def _get_tradingview_symbol(self, binance_symbol: str) -> Optional[str]:
        """
        Convert Binance symbol to TradingView symbol.
        
        Args:
            binance_symbol: Binance trading pair
            
        Returns:
            TradingView symbol or None if not supported
        """
        return self.symbol_map.get(binance_symbol)
    
    def process_webhook(self, webhook_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process incoming TradingView webhook alert.
        
        Args:
            webhook_data: JSON data from TradingView webhook
            
        Returns:
            Processed alert data or None
        """
        try:
            self.logger.info(f"Processing TradingView webhook alert")
            
            # Extract alert information
            alert = {
                'timestamp': datetime.utcnow(),
                'symbol': webhook_data.get('ticker', ''),
                'price': float(webhook_data.get('price', 0)),
                'time': webhook_data.get('time', ''),
                'close': float(webhook_data.get('close', 0)),
                'volume': float(webhook_data.get('volume', 0)),
                'strategy': webhook_data.get('strategy', ''),
                'action': webhook_data.get('action', ''),  # buy/sell
                'raw_data': webhook_data,
            }
            
            # Store alert
            self.alert_history.append(alert)
            
            self.request_count += 1
            self.logger.info(
                f"TradingView alert: {alert['symbol']} "
                f"Price: ${alert['price']:.2f} "
                f"Action: {alert['action']}"
            )
            
            return alert
            
        except Exception as e:
            self.logger.error(f"Error processing webhook: {e}")
            self.error_count += 1
            return None
    
    def fetch_current_price(self, symbol: str) -> Optional[float]:
        """
        Fetch current price from TradingView.
        
        Note: Since TradingView has no public API, this returns
        mock data or the latest price from webhook alerts.
        
        Args:
            symbol: Trading pair
            
        Returns:
            Current price or None
        """
        # First, check if we have recent webhook data
        if self.alert_history:
            recent_alerts = [
                alert for alert in self.alert_history
                if alert['symbol'] == symbol
                and (datetime.utcnow() - alert['timestamp']).total_seconds() < 300  # 5 minutes
            ]
            
            if recent_alerts:
                price = recent_alerts[-1]['price']
                self.logger.info(f"{self.CONNECTOR_NAME} price from webhook for {symbol}: ${price:.2f}")
                return price
        
        # Fallback to mock price (for testing)
        price = self.mock_prices.get(symbol)
        if price:
            self.logger.info(f"{self.CONNECTOR_NAME} mock price for {symbol}: ${price:.2f}")
            self.request_count += 1
            return price
        
        self.logger.warning(f"{self.CONNECTOR_NAME} no price available for {symbol}")
        return None
    
    def fetch_bars(
        self,
        symbol: str,
        timeframe: str,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch OHLCV bars from TradingView.
        
        Note: Since TradingView has no public API for historical data,
        this returns an empty DataFrame. Real data must come via webhooks.
        
        Args:
            symbol: Trading pair
            timeframe: Kline interval
            limit: Number of bars
            
        Returns:
            DataFrame with OHLCV data (empty)
        """
        self.logger.info(
            f"{self.CONNECTOR_NAME} historical bars not available "
            f"(use webhook alerts or other connectors)"
        )
        return pd.DataFrame()
    
    def get_latest_alert(self, symbol: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get the latest alert from TradingView.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            Latest alert or None
        """
        if not self.alert_history:
            return None
        
        alerts = self.alert_history
        if symbol:
            alerts = [alert for alert in alerts if alert['symbol'] == symbol]
        
        if alerts:
            return alerts[-1]
        
        return None
    
    def get_alert_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get alert history.
        
        Args:
            symbol: Optional symbol filter
            limit: Maximum number of alerts to return
            
        Returns:
            List of alerts
        """
        alerts = self.alert_history
        if symbol:
            alerts = [alert for alert in alerts if alert['symbol'] == symbol]
        
        return alerts[-limit:]
    
    def generate_webhook_url(self, base_url: str) -> str:
        """
        Generate webhook URL for TradingView alerts.
        
        Args:
            base_url: Base URL of the bot (e.g., https://your-bot.com)
            
        Returns:
            Webhook URL
        """
        return f"{base_url}/webhook/tradingview"
    
    def get_status(self) -> Dict[str, Any]:
        """Get connector status."""
        return {
            'connector': self.CONNECTOR_NAME,
            'is_connected': self.is_connected,
            'has_webhook': bool(self.webhook_url),
            'request_count': self.request_count,
            'error_count': self.error_count,
            'alert_count': len(self.alert_history),
            'supported_symbols': list(self.symbol_map.keys()),
            'webhook_url': self.webhook_url,
        }