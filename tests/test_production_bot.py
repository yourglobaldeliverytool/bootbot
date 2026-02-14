"""Comprehensive test suite for production Apex Signal Bot."""

import unittest
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestEnvironmentLoader(unittest.TestCase):
    """Test environment loader."""
    
    def test_env_loader_creation(self):
        """Test environment loader can be created."""
        from bot.utils.env_loader import EnvLoader
        env = EnvLoader()
        self.assertIsNotNone(env)
        self.assertIn(env.mode, ['VERIFIED_TEST', 'LIVE_SIGNAL'])
    
    def test_mode_detection(self):
        """Test mode detection based on env vars."""
        from bot.utils.env_loader import EnvLoader
        import os
        
        # Test without env vars (should be VERIFIED_TEST)
        env = EnvLoader()
        self.assertEqual(env.mode, 'VERIFIED_TEST')
        
        # Test with env vars (should be LIVE_SIGNAL)
        os.environ['TELEGRAM_BOT_TOKEN'] = 'test_token'
        os.environ['TELEGRAM_CHAT_ID'] = '123456'
        env2 = EnvLoader()
        self.assertEqual(env2.mode, 'LIVE_SIGNAL')
        
        # Cleanup
        del os.environ['TELEGRAM_BOT_TOKEN']
        del os.environ['TELEGRAM_CHAT_ID']


class TestPersistence(unittest.TestCase):
    """Test database persistence."""
    
    def setUp(self):
        """Set up test database."""
        from bot.persistence.database import Database
        self.db = Database(":memory:")
    
    def tearDown(self):
        """Clean up test database."""
        self.db.close()
    
    def test_database_initialization(self):
        """Test database initializes correctly."""
        self.assertIsNotNone(self.db.conn)
    
    def test_save_signal(self):
        """Test saving a signal."""
        from bot.persistence.models import Signal
        
        signal = Signal(
            symbol="BTCUSDT",
            signal_type="BUY",
            canonical_price=65000.0,
            primary_price=65000.0,
            primary_source="Binance",
            primary_timestamp=datetime.utcnow().isoformat(),
            secondary_price=65001.0,
            secondary_source="CoinGecko",
            secondary_timestamp=datetime.utcnow().isoformat(),
            checksum_raw="BTCUSDT|65000.00000000|2024-01-01T00:00:00|Binance|2024-01-01T00:00:00|CoinGecko",
            checksum="test_checksum",
            confidence=75.0,
            mode="VERIFIED_TEST",
            created_at=datetime.utcnow().isoformat()
        )
        
        signal_id = self.db.save_signal(signal)
        self.assertGreater(signal_id, 0)
        self.assertEqual(signal.id, signal_id)
    
    def test_get_signal(self):
        """Test retrieving a signal."""
        from bot.persistence.models import Signal
        
        signal = Signal(
            symbol="ETHUSDT",
            signal_type="SELL",
            canonical_price=3500.0,
            primary_price=3500.0,
            primary_source="Binance",
            primary_timestamp=datetime.utcnow().isoformat(),
            secondary_price=3501.0,
            secondary_source="CoinGecko",
            secondary_timestamp=datetime.utcnow().isoformat(),
            checksum_raw="ETHUSDT|3500.00000000|2024-01-01T00:00:00|Binance|2024-01-01T00:00:00|CoinGecko",
            checksum="test_checksum_eth",
            confidence=80.0,
            mode="VERIFIED_TEST",
            created_at=datetime.utcnow().isoformat()
        )
        
        signal_id = self.db.save_signal(signal)
        retrieved = self.db.get_signal_by_id(signal_id)
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.symbol, "ETHUSDT")
        self.assertEqual(retrieved.signal_type, "SELL")
    
    def test_checksum_verification(self):
        """Test signal checksum verification."""
        import hashlib
        from bot.persistence.models import Signal
        
        checksum_raw = "BTCUSDT|65000.00000000|2024-01-01T00:00:00|Binance|2024-01-01T00:00:00|CoinGecko"
        checksum = hashlib.sha256(checksum_raw.encode()).hexdigest()
        
        signal = Signal(
            symbol="BTCUSDT",
            signal_type="BUY",
            canonical_price=65000.0,
            primary_price=65000.0,
            primary_source="Binance",
            primary_timestamp="2024-01-01T00:00:00",
            secondary_price=65000.0,
            secondary_source="CoinGecko",
            secondary_timestamp="2024-01-01T00:00:00",
            checksum_raw=checksum_raw,
            checksum=checksum,
            confidence=75.0,
            mode="VERIFIED_TEST",
            created_at=datetime.utcnow().isoformat()
        )
        
        signal_id = self.db.save_signal(signal)
        result = self.db.verify_signal(signal_id)
        
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['original_checksum'], checksum)


class TestIndicators(unittest.TestCase):
    """Test technical indicators."""
    
    def setUp(self):
        """Set up test data."""
        # Generate synthetic OHLCV data
        np.random.seed(42)
        dates = pd.date_range(start=datetime.now() - timedelta(days=100), periods=100, freq='h')
        
        self.data = pd.DataFrame({
            'timestamp': dates,
            'open': 65000 + np.cumsum(np.random.randn(100) * 100),
            'high': 65000 + np.cumsum(np.random.randn(100) * 100) + np.abs(np.random.randn(100) * 50),
            'low': 65000 + np.cumsum(np.random.randn(100) * 100) - np.abs(np.random.randn(100) * 50),
            'close': 65000 + np.cumsum(np.random.randn(100) * 100),
            'volume': np.random.randint(100, 1000, 100)
        })
    
    def test_sma_indicator(self):
        """Test SMA indicator."""
        from bot.indicators.sma import SMAIndicator
        
        sma = SMAIndicator(parameters={'period': 20})
        result = sma.calculate(self.data)
        
        self.assertIn('sma_20', result.columns)
        self.assertFalse(result['sma_20'].isna().all())
    
    def test_ema_indicator(self):
        """Test EMA indicator."""
        from bot.indicators.ema import EMAIndicator
        
        ema = EMAIndicator(parameters={'period': 20})
        result = ema.calculate(self.data)
        
        self.assertIn('ema_20', result.columns)
        self.assertFalse(result['ema_20'].isna().all())
    
    def test_rsi_indicator(self):
        """Test RSI indicator."""
        from bot.indicators.rsi import RSIIndicator
        
        rsi = RSIIndicator(parameters={'period': 14})
        result = rsi.calculate(self.data)
        
        self.assertIn('rsi_14', result.columns)
        self.assertFalse(result['rsi_14'].isna().all())
    
    def test_bollinger_bands(self):
        """Test Bollinger Bands indicator."""
        from bot.indicators.bollinger_bands import BollingerBands
        
        bb = BollingerBands(period=20, std_dev=2.0)
        result = bb.calculate(self.data)
        
        self.assertIn('bb_middle_20', result.columns)
        self.assertIn('bb_upper_20', result.columns)
        self.assertIn('bb_lower_20', result.columns)
    
    def test_all_indicators_exist(self):
        """Test all 22 indicators can be imported."""
        indicator_names = [
            'sma', 'ema', 'rsi', 'macd', 'atr',
            'bollinger_bands', 'vwap', 'adx', 'stochastic', 'ichimoku',
            'obv', 'cci', 'williams_r', 'roc', 'keltner_channels',
            'donchian_channels', 'pivot_points', 'heikin_ashi', 
            'supertrend', 'parabolic_sar', 'z_score', 'volume_profile'
        ]
        
        for name in indicator_names:
            try:
                module = __import__(f'bot.indicators.{name}', fromlist=[''])
                self.assertIsNotNone(module)
            except ImportError:
                self.fail(f"Could not import indicator: {name}")


class TestStrategies(unittest.TestCase):
    """Test trading strategies."""
    
    def setUp(self):
        """Set up test data."""
        np.random.seed(42)
        dates = pd.date_range(start=datetime.now() - timedelta(days=100), periods=100, freq='h')
        
        self.data = pd.DataFrame({
            'timestamp': dates,
            'open': 65000 + np.cumsum(np.random.randn(100) * 100),
            'high': 65000 + np.cumsum(np.random.randn(100) * 100) + np.abs(np.random.randn(100) * 50),
            'low': 65000 + np.cumsum(np.random.randn(100) * 100) - np.abs(np.random.randn(100) * 50),
            'close': 65000 + np.cumsum(np.random.randn(100) * 100),
            'volume': np.random.randint(100, 1000, 100)
        })
        
        # Calculate some indicators
        from bot.indicators.sma import SMAIndicator
        from bot.indicators.rsi import RSIIndicator
        
        sma = SMAIndicator(parameters={'period': 20})
        rsi = RSIIndicator(parameters={'period': 14})
        
        self.data = sma.calculate(self.data)
        self.data = rsi.calculate(self.data)
        
        self.indicators = {
            'sma_20': self.data['sma_20'],
            'rsi': self.data['rsi_14']
        }
    
    def test_all_strategies_exist(self):
        """Test all 18 strategies can be imported."""
        strategy_names = [
            'trend_following', 'mean_reversion', 'breakout', 'scalping', 'arbitrage',
            'ema_trend_stack', 'vwap_mean_reversion', 'rsi_momentum', 'macd_expansion',
            'bb_squeeze_breakout', 'atr_volatility_breakout', 'liquidity_sweep',
            'market_structure', 'order_block', 'fvg_fill', 'fibonacci_confluence',
            'ichimoku_bias', 'stochastic_reversal'
        ]
        
        for name in strategy_names:
            try:
                module = __import__(f'bot.strategies.{name}', fromlist=[''])
                self.assertIsNotNone(module)
            except ImportError:
                self.fail(f"Could not import strategy: {name}")
    
    def test_strategy_generation(self):
        """Test strategies can be instantiated."""
        from bot.strategies.mean_reversion import MeanReversionStrategy
        
        strategy = MeanReversionStrategy(name='test_mean_rev', parameters={'period': 20, 'std_threshold': 2.0})
        signal = strategy.generate_signal(self.data)
        
        self.assertIsNotNone(signal)
        # Old strategies return 'signal', new ones return 'signal_type'
        self.assertIn('signal', signal) 
        self.assertIn('reason', signal)
        self.assertIn(signal['signal'], ['BUY', 'SELL', 'HOLD'])


class TestConnectors(unittest.TestCase):
    """Test data connectors."""
    
    def test_connectors_exist(self):
        """Test all connectors can be imported."""
        connector_names = [
            'base', 'binance', 'coingecko', 'coincap', 'metals_live', 'mock_live', 'multi_source'
        ]
        
        for name in connector_names:
            try:
                module = __import__(f'bot.connectors.{name}', fromlist=[''])
                self.assertIsNotNone(module)
            except ImportError:
                self.fail(f"Could not import connector: {name}")
    
    def test_mock_connector(self):
        """Test mock connector returns data."""
        from bot.connectors.mock_live import MockLiveConnector
        
        connector = MockLiveConnector()
        price = connector.fetch_current_price('BTCUSDT')
        
        self.assertIsNotNone(price)
        self.assertIsInstance(price, float)
        self.assertGreater(price, 0)


class TestChecksum(unittest.TestCase):
    """Test checksum calculation."""
    
    def test_checksum_determinism(self):
        """Test checksum is deterministic."""
        import hashlib
        
        checksum_raw = "BTCUSDT|65000.00000000|2024-01-01T00:00:00|Binance|2024-01-01T00:00:00|CoinGecko"
        checksum1 = hashlib.sha256(checksum_raw.encode()).hexdigest()
        checksum2 = hashlib.sha256(checksum_raw.encode()).hexdigest()
        
        self.assertEqual(checksum1, checksum2)
    
    def test_checksum_uniqueness(self):
        """Test different inputs produce different checksums."""
        import hashlib
        
        raw1 = "BTCUSDT|65000.00000000|2024-01-01T00:00:00|Binance|2024-01-01T00:00:00|CoinGecko"
        raw2 = "BTCUSDT|65001.00000000|2024-01-01T00:00:00|Binance|2024-01-01T00:00:00|CoinGecko"
        
        checksum1 = hashlib.sha256(raw1.encode()).hexdigest()
        checksum2 = hashlib.sha256(raw2.encode()).hexdigest()
        
        self.assertNotEqual(checksum1, checksum2)


class TestRESTAPI(unittest.TestCase):
    """Test REST API endpoints."""
    
    def test_api_creation(self):
        """Test FastAPI app can be created."""
        from bot.api.app import create_app
        
        app = create_app()
        self.assertIsNotNone(app)


class TestIntegration(unittest.TestCase):
    """Integration tests."""
    
    def test_full_signal_generation_flow(self):
        """Test complete signal generation flow."""
        from bot.persistence.database import Database
        from bot.persistence.models import Signal
        
        # Create database
        db = Database(":memory:")
        
        # Create and save a signal
        import hashlib
        checksum_raw = "BTCUSDT|65000.00000000|2024-01-01T00:00:00|Binance|2024-01-01T00:00:00|CoinGecko"
        checksum = hashlib.sha256(checksum_raw.encode()).hexdigest()
        
        signal = Signal(
            symbol="BTCUSDT",
            signal_type="BUY",
            canonical_price=65000.0,
            primary_price=65000.0,
            primary_source="Binance",
            primary_timestamp="2024-01-01T00:00:00",
            secondary_price=65000.0,
            secondary_source="CoinGecko",
            secondary_timestamp="2024-01-01T00:00:00",
            checksum_raw=checksum_raw,
            checksum=checksum,
            tp1=65500.0,
            tp2=66000.0,
            tp3=67000.0,
            sl=64500.0,
            position_size_usd=15.0,
            position_size_units=0.00023,
            confidence=78.5,
            strategies='["trend_following","rsi_momentum"]',
            indicators='{"rsi":45,"ema_20":64900}',
            mode="VERIFIED_TEST",
            created_at=datetime.utcnow().isoformat()
        )
        
        signal_id = db.save_signal(signal)
        
        # Verify signal was saved
        retrieved = db.get_signal_by_id(signal_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.signal_type, "BUY")
        
        # Verify checksum
        result = db.verify_signal(signal_id)
        self.assertEqual(result['status'], 'PASS')
        
        # Get signals
        signals = db.get_signals(limit=10)
        self.assertGreater(len(signals), 0)
        
        db.close()


def run_tests():
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestEnvironmentLoader))
    suite.addTests(loader.loadTestsFromTestCase(TestPersistence))
    suite.addTests(loader.loadTestsFromTestCase(TestIndicators))
    suite.addTests(loader.loadTestsFromTestCase(TestStrategies))
    suite.addTests(loader.loadTestsFromTestCase(TestConnectors))
    suite.addTests(loader.loadTestsFromTestCase(TestChecksum))
    suite.addTests(loader.loadTestsFromTestCase(TestRESTAPI))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == '__main__':
    result = run_tests()
    sys.exit(0 if result.wasSuccessful() else 1)