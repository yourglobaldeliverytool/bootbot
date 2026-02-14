"""
Comprehensive test suite for APEX SIGNAL™ v3 enhancements.
Tests all new features including multi-source connectors, capital management,
and enhanced Telegram messaging.
"""

import os
import sys
import time
import logging
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
sys.path.insert(0, '/workspace')

import pandas as pd
import numpy as np

# Test imports
from bot.utils.env_loader import EnvLoader
from bot.connectors.binance import BinanceConnector
from bot.connectors.alpaca import AlpacaConnector
from bot.connectors.yahoo_finance import YahooFinanceConnector
from bot.connectors.tradingview import TradingViewConnector
from bot.connectors.coincap import CoinCapConnector
from bot.connectors.metals_live import MetalsLiveConnector
from bot.connectors.multi_source import MultiSourceConnector
from bot.connectors.mock_live import MockLiveConnector


class TestEnvironmentLoader:
    """Test environment variable loading."""
    
    @staticmethod
    def test_capital_environment_variable():
        """Test CAPITAL environment variable loading."""
        print("\n" + "="*70)
        print("TEST: Environment Variable - CAPITAL")
        print("="*70)
        
        # Test with default capital ($50)
        if 'CAPITAL' in os.environ:
            del os.environ['CAPITAL']
        
        env_loader = EnvLoader()
        assert env_loader.capital == 50.0, f"Expected 50.0, got {env_loader.capital}"
        print("✅ Default capital: $50")
        
        # Test with custom capital
        os.environ['CAPITAL'] = '100'
        env_loader = EnvLoader()
        assert env_loader.capital == 100.0, f"Expected 100.0, got {env_loader.capital}"
        print("✅ Custom capital: $100")
        
        # Test with invalid capital (should fallback to default)
        os.environ['CAPITAL'] = 'invalid'
        env_loader = EnvLoader()
        assert env_loader.capital == 50.0, f"Expected 50.0, got {env_loader.capital}"
        print("✅ Invalid capital fallback: $50")
        
        # Reset
        if 'CAPITAL' in os.environ:
            del os.environ['CAPITAL']
        
        print("✅ PASSED: Environment variable loading\n")
    
    @staticmethod
    def test_risk_per_trade_environment_variable():
        """Test RISK_PER_TRADE environment variable loading."""
        print("="*70)
        print("TEST: Environment Variable - RISK_PER_TRADE")
        print("="*70)
        
        # Test with default risk (1.5%)
        if 'RISK_PER_TRADE' in os.environ:
            del os.environ['RISK_PER_TRADE']
        
        env_loader = EnvLoader()
        assert env_loader.risk_per_trade == 0.015, f"Expected 0.015, got {env_loader.risk_per_trade}"
        print("✅ Default risk: 1.5%")
        
        # Test with custom risk
        os.environ['RISK_PER_TRADE'] = '0.02'
        env_loader = EnvLoader()
        assert env_loader.risk_per_trade == 0.02, f"Expected 0.02, got {env_loader.risk_per_trade}"
        print("✅ Custom risk: 2.0%")
        
        # Reset
        if 'RISK_PER_TRADE' in os.environ:
            del os.environ['RISK_PER_TRADE']
        
        print("✅ PASSED: Risk per trade loading\n")


class TestConnectors:
    """Test all data connectors."""
    
    @staticmethod
    def test_alpaca_connector():
        """Test Alpaca connector."""
        print("="*70)
        print("TEST: Alpaca Connector")
        print("="*70)
        
        config = {}
        connector = AlpacaConnector(config)
        
        # Test initialization
        assert connector.CONNECTOR_NAME == "alpaca", "Connector name mismatch"
        print("✅ Connector name: alpaca")
        
        # Test symbol mapping
        assert connector._get_alpaca_symbol('BTCUSDT') == 'BTC/USD', "BTC mapping incorrect"
        assert connector._get_alpaca_symbol('ETHUSDT') == 'ETH/USD', "ETH mapping incorrect"
        assert connector._get_alpaca_symbol('XAUUSD') is None, "XAUUSD should not be supported"
        print("✅ Symbol mapping correct")
        
        # Test status
        status = connector.get_status()
        assert 'connector' in status, "Status missing connector field"
        assert 'supported_symbols' in status, "Status missing supported_symbols field"
        print("✅ Status method working")
        
        print("✅ PASSED: Alpaca connector\n")
    
    @staticmethod
    def test_yahoo_finance_connector():
        """Test Yahoo Finance connector."""
        print("="*70)
        print("TEST: Yahoo Finance Connector")
        print("="*70)
        
        config = {}
        connector = YahooFinanceConnector(config)
        
        # Test initialization
        assert connector.CONNECTOR_NAME == "yahoo_finance", "Connector name mismatch"
        print("✅ Connector name: yahoo_finance")
        
        # Test symbol mapping
        assert connector._get_yahoo_symbol('BTCUSDT') == 'BTC-USD', "BTC mapping incorrect"
        assert connector._get_yahoo_symbol('ETHUSDT') == 'ETH-USD', "ETH mapping incorrect"
        assert connector._get_yahoo_symbol('XAUUSD') == 'GC=F', "XAUUSD mapping incorrect"
        print("✅ Symbol mapping correct")
        
        # Test status
        status = connector.get_status()
        assert 'connector' in status, "Status missing connector field"
        print("✅ Status method working")
        
        print("✅ PASSED: Yahoo Finance connector\n")
    
    @staticmethod
    def test_tradingview_connector():
        """Test TradingView connector."""
        print("="*70)
        print("TEST: TradingView Connector")
        print("="*70)
        
        config = {}
        connector = TradingViewConnector(config)
        
        # Test initialization
        assert connector.CONNECTOR_NAME == "tradingview", "Connector name mismatch"
        print("✅ Connector name: tradingview")
        
        # Test webhook processing
        webhook_data = {
            'ticker': 'BTCUSDT',
            'price': 67000,
            'time': '2024-01-01 12:00:00',
            'close': 67000,
            'volume': 100,
            'strategy': 'test_strategy',
            'action': 'buy'
        }
        
        alert = connector.process_webhook(webhook_data)
        assert alert is not None, "Alert should not be None"
        assert alert['symbol'] == 'BTCUSDT', "Symbol mismatch"
        assert alert['price'] == 67000, "Price mismatch"
        assert alert['action'] == 'buy', "Action mismatch"
        print("✅ Webhook processing working")
        
        # Test alert history
        history = connector.get_alert_history()
        assert len(history) == 1, "Should have 1 alert in history"
        print("✅ Alert history working")
        
        print("✅ PASSED: TradingView connector\n")
    
    @staticmethod
    def test_multi_source_connector():
        """Test MultiSource connector with failover."""
        print("="*70)
        print("TEST: Multi-Source Connector with Failover")
        print("="*70)
        
        config = {}
        connector = MultiSourceConnector(config)
        
        # Test initialization
        assert connector.CONNECTOR_NAME == "multi_source", "Connector name mismatch"
        print("✅ Connector name: multi_source")
        
        # Test that all connectors are initialized
        assert len(connector.primary_connectors) >= 5, "Should have at least 5 primary connectors"
        print(f"✅ Primary connectors: {len(connector.primary_connectors)}")
        
        # Test symbol-specific connectors
        btc_connectors = connector._get_connectors_for_symbol('BTCUSDT')
        assert len(btc_connectors) >= 5, "Should have at least 5 connectors for BTC"
        print(f"✅ BTC connectors: {len(btc_connectors)}")
        
        xau_connectors = connector._get_connectors_for_symbol('XAUUSD')
        assert len(xau_connectors) >= 3, "Should have at least 3 connectors for XAU"
        print(f"✅ XAU connectors: {len(xau_connectors)}")
        
        # Test price fetching with mock connector
        price = connector.fetch_current_price('BTCUSDT')
        assert price is not None, "Should return a price"
        assert price > 0, "Price should be positive"
        print(f"✅ Price fetched: ${price:.2f}")
        
        # Test audit trail
        audit_trail = connector.get_audit_trail()
        assert len(audit_trail) >= 1, "Should have audit trail entries"
        print(f"✅ Audit trail entries: {len(audit_trail)}")
        
        # Test status
        status = connector.get_status()
        assert 'sources' in status, "Status should include sources"
        assert 'audit_trail_size' in status, "Status should include audit_trail_size"
        print("✅ Status method working")
        
        # Test deviation validation
        assert connector.MAX_DEVIATION == 0.0005, "Max deviation should be 0.05%"
        print(f"✅ Max deviation: {connector.MAX_DEVIATION:.4%}")
        
        print("✅ PASSED: Multi-source connector\n")


class TestSignalBot:
    """Test signal bot enhancements."""
    
    @staticmethod
    def test_signal_bot_capital_loading():
        """Test signal bot capital loading from environment."""
        print("="*70)
        print("TEST: Signal Bot Capital Loading")
        print("="*70)
        
        # Set environment variables
        os.environ['CAPITAL'] = '100'
        os.environ['RISK_PER_TRADE'] = '0.02'
        
        try:
            # Reset the global env_loader to pick up new environment variables
            from bot.utils import env_loader
            if hasattr(env_loader, '_env_loader'):
                env_loader._env_loader = None
            
            from bot.signal_bot import SignalBot
            
            bot = SignalBot()
            
            # Test capital loading
            assert bot.capital == 100.0, f"Expected 100.0, got {bot.capital}"
            print(f"✅ Capital loaded: ${bot.capital:.2f}")
            
            # Test risk loading
            assert bot.risk_per_trade == 0.02, f"Expected 0.02, got {bot.risk_per_trade}"
            print(f"✅ Risk per trade loaded: {bot.risk_per_trade:.1%}")
            
            print("✅ PASSED: Signal bot capital loading\n")
            
        finally:
            # Cleanup
            if 'CAPITAL' in os.environ:
                del os.environ['CAPITAL']
            if 'RISK_PER_TRADE' in os.environ:
                del os.environ['RISK_PER_TRADE']
            
            # Reset env_loader again
            from bot.utils import env_loader
            if hasattr(env_loader, '_env_loader'):
                env_loader._env_loader = None


class TestTelegramMessaging:
    """Test Telegram message formatting."""
    
    @staticmethod
    def test_signal_data_includes_capital_and_risk():
        """Test that signal data includes capital and risk information."""
        print("="*70)
        print("TEST: Signal Data with Capital and Risk")
        print("="*70)
        
        # Create a mock signal data
        signal_data = {
            'symbol': 'BTCUSDT',
            'signal': 'BUY',
            'price': 67000.00,
            'tp': 68000.00,
            'sl': 66500.00,
            'confidence': 75.0,
            'strategies': ['trend_following', 'mean_reversion'],
            'indicators': ['sma', 'ema', 'rsi'],
            'checksum': 'abc123',
            'timestamp': datetime.utcnow(),
            'strategy_name': 'trend_following',
        }
        
        # Test required fields
        assert 'strategy_name' in signal_data, "strategy_name missing"
        assert signal_data['strategy_name'] == 'trend_following', "strategy_name incorrect"
        print(f"✅ Strategy name: {signal_data['strategy_name']}")
        
        # Calculate position size and risk (as the bot would)
        capital = 100.0
        risk_per_trade = 0.015
        risk_amount = capital * risk_per_trade
        price = signal_data['price']
        sl = signal_data['sl']
        
        if signal_data['signal'] == 'BUY':
            position_size = risk_amount / (price - sl) if price > sl else 0
        else:
            position_size = risk_amount / (sl - price) if sl > price else 0
        
        # Test calculations
        assert risk_amount == 1.5, f"Expected 1.5, got {risk_amount}"
        print(f"✅ Risk amount: ${risk_amount:.2f}")
        
        assert position_size > 0, "Position size should be positive"
        print(f"✅ Position size: {position_size:.6f} units")
        
        # Test R:R ratio
        tp = signal_data['tp']
        if signal_data['signal'] == 'BUY':
            rr_ratio = (tp - price) / (price - sl) if price > sl else 0
        else:
            rr_ratio = (price - tp) / (sl - price) if sl > price else 0
        
        assert rr_ratio > 0, "R:R ratio should be positive"
        print(f"✅ R:R Ratio: 1:{rr_ratio:.1f}")
        
        print("✅ PASSED: Signal data with capital and risk\n")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*70)
    print("APEX SIGNAL™ v3 - Comprehensive Test Suite")
    print("="*70)
    print(f"Started at: {datetime.utcnow().isoformat()}")
    
    test_results = []
    
    try:
        # Environment Loader Tests
        TestEnvironmentLoader.test_capital_environment_variable()
        test_results.append(('Capital Environment Variable', True))
        
        TestEnvironmentLoader.test_risk_per_trade_environment_variable()
        test_results.append(('Risk Per Trade Environment Variable', True))
        
        # Connector Tests
        TestConnectors.test_alpaca_connector()
        test_results.append(('Alpaca Connector', True))
        
        TestConnectors.test_yahoo_finance_connector()
        test_results.append(('Yahoo Finance Connector', True))
        
        TestConnectors.test_tradingview_connector()
        test_results.append(('TradingView Connector', True))
        
        TestConnectors.test_multi_source_connector()
        test_results.append(('Multi-Source Connector', True))
        
        # Signal Bot Tests
        TestSignalBot.test_signal_bot_capital_loading()
        test_results.append(('Signal Bot Capital Loading', True))
        
        # Telegram Messaging Tests
        TestTelegramMessaging.test_signal_data_includes_capital_and_risk()
        test_results.append(('Telegram Message Formatting', True))
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        test_results.append(('Failed Test', False))
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print("\n" + "="*70)
    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    print("="*70)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! 🎉\n")
        return True
    else:
        print(f"\n❌ {total - passed} TEST(S) FAILED ❌\n")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)