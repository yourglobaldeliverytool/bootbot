"""
Data loading utility for the trading bot.
Provides methods to load and prepare OHLCV data for strategies and indicators.
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta
import logging


class DataLoader:
    """
    Utility class for loading and preparing trading data.
    Supports synthetic data generation and CSV loading.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the data loader.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger("DataLoader")
    
    def generate_synthetic_data(
        self,
        num_periods: int = 1000,
        start_date: Optional[Union[str, datetime]] = None,
        volatility: float = 0.02,
        drift: float = 0.0001,
        initial_price: float = 100.0,
        seed: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Generate synthetic OHLCV data using geometric Brownian motion.
        
        Args:
            num_periods: Number of data points to generate
            start_date: Start date for the data (default: 100 days ago)
            volatility: Annual volatility parameter
            drift: Annual drift parameter
            initial_price: Starting price
            seed: Random seed for reproducibility
            
        Returns:
            DataFrame with OHLCV data
        """
        if seed is not None:
            np.random.seed(seed)
        
        # Set start date
        if start_date is None:
            start_date = datetime.now() - timedelta(days=num_periods)
        elif isinstance(start_date, str):
            start_date = pd.to_datetime(start_date)
        
        # Generate returns using geometric Brownian motion
        dt = 1.0 / 252.0  # Daily time step
        random_shocks = np.random.normal(0, 1, num_periods)
        returns = (drift - 0.5 * volatility ** 2) * dt + volatility * np.sqrt(dt) * random_shocks
        
        # Generate price series
        log_prices = np.log(initial_price) + np.cumsum(returns)
        prices = np.exp(log_prices)
        
        # Generate OHLC from close prices
        date_range = pd.date_range(start=start_date, periods=num_periods, freq='D')
        
        # Create DataFrame with close prices
        df = pd.DataFrame({
            'timestamp': date_range,
            'close': prices
        })
        
        # Generate OHLC from close prices
        df['open'] = df['close'].shift(1).fillna(initial_price)
        
        # Generate high and low with some variation
        intraday_range = df['close'] * volatility * np.random.uniform(0.5, 1.5, num_periods)
        df['high'] = df[['open', 'close']].max(axis=1) + intraday_range * np.random.uniform(0.2, 0.5, num_periods)
        df['low'] = df[['open', 'close']].min(axis=1) - intraday_range * np.random.uniform(0.2, 0.5, num_periods)
        
        # Generate volume
        base_volume = 1000000
        volume_noise = np.random.normal(1, 0.3, num_periods)
        df['volume'] = base_volume * volume_noise * np.abs(df['close'].pct_change().fillna(0) + 1)
        df['volume'] = df['volume'].clip(lower=0)
        
        # Ensure OHLC relationships are valid
        df['high'] = df[['open', 'high', 'close']].max(axis=1)
        df['low'] = df[['open', 'low', 'close']].min(axis=1)
        
        # Set timestamp as index
        df.set_index('timestamp', inplace=True)
        
        self.logger.info(f"Generated synthetic data: {num_periods} periods")
        return df
    
    def load_from_csv(
        self,
        file_path: str,
        timestamp_column: str = 'timestamp',
        date_format: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Load OHLCV data from a CSV file.
        
        Args:
            file_path: Path to the CSV file
            timestamp_column: Name of the timestamp column
            date_format: Optional date format string for parsing
            
        Returns:
            DataFrame with OHLCV data
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If required columns are missing
        """
        try:
            df = pd.read_csv(file_path)
            
            # Parse timestamp
            if timestamp_column in df.columns:
                if date_format:
                    df[timestamp_column] = pd.to_datetime(df[timestamp_column], format=date_format)
                else:
                    df[timestamp_column] = pd.to_datetime(df[timestamp_column])
                df.set_index(timestamp_column, inplace=True)
            
            # Validate required columns
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")
            
            # Sort by timestamp
            df.sort_index(inplace=True)
            
            self.logger.info(f"Loaded data from CSV: {len(df)} rows")
            return df
            
        except FileNotFoundError:
            self.logger.error(f"File not found: {file_path}")
            raise
        except Exception as e:
            self.logger.error(f"Error loading CSV: {e}")
            raise
    
    def validate_data(self, df: pd.DataFrame) -> bool:
        """
        Validate that the DataFrame has required OHLCV columns and valid data.
        
        Args:
            df: DataFrame to validate
            
        Returns:
            True if valid, False otherwise
        """
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        
        # Check for required columns
        if not all(col in df.columns for col in required_columns):
            self.logger.error(f"Missing required columns: {required_columns}")
            return False
        
        # Check for NaN values
        if df[required_columns].isnull().any().any():
            self.logger.warning("Data contains NaN values")
            return False
        
        # Check for valid OHLC relationships
        invalid_ohlc = (df['high'] < df[['open', 'close']].max(axis=1)) | \
                       (df['low'] > df[['open', 'close']].min(axis=1))
        
        if invalid_ohlc.any():
            self.logger.warning(f"Found {invalid_ohlc.sum()} invalid OHLC relationships")
            return False
        
        # Check for negative values
        if (df[required_columns] < 0).any().any():
            self.logger.error("Data contains negative values")
            return False
        
        self.logger.info("Data validation passed")
        return True
    
    def resample_data(
        self,
        df: pd.DataFrame,
        timeframe: str = '1D'
    ) -> pd.DataFrame:
        """
        Resample data to a different timeframe.
        
        Args:
            df: DataFrame with OHLCV data
            timeframe: Resampling frequency (e.g., '1H', '1D', '1W')
            
        Returns:
            Resampled DataFrame
        """
        resampled = df.resample(timeframe).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        self.logger.info(f"Resampled data to {timeframe}: {len(resampled)} rows")
        return resampled
    
    def add_returns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add return columns to the DataFrame.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with added return columns
        """
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        
        return df
    
    def get_latest_data(
        self,
        df: pd.DataFrame,
        n_periods: int = 100
    ) -> pd.DataFrame:
        """
        Get the latest n periods of data.
        
        Args:
            df: DataFrame with OHLCV data
            n_periods: Number of periods to retrieve
            
        Returns:
            DataFrame with the latest n periods
        """
        return df.tail(n_periods).copy()