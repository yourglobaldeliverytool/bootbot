"""SQLite database implementation for Apex Signal Bot."""

import sqlite3
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from bot.persistence.models import Signal, ConnectorHealth, Telemetry, AuditLog

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager for signal persistence."""
    
    def __init__(self, db_path: str = "apex_signal.db"):
        """
        Initialize the database.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self._initialize()
    
    def _initialize(self):
        """Initialize database connection and create tables."""
        try:
            # Create database directory if it doesn't exist
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Connect to database
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            
            # Create tables
            self._create_tables()
            
            logger.info(f"✅ Database initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            raise
    
    def _create_tables(self):
        """Create all database tables."""
        # Signals table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                canonical_price REAL NOT NULL,
                primary_price REAL NOT NULL,
                primary_source TEXT NOT NULL,
                primary_timestamp TEXT NOT NULL,
                secondary_price REAL NOT NULL,
                secondary_source TEXT NOT NULL,
                secondary_timestamp TEXT NOT NULL,
                checksum_raw TEXT NOT NULL,
                checksum TEXT NOT NULL UNIQUE,
                tp1 REAL DEFAULT 0,
                tp2 REAL DEFAULT 0,
                tp3 REAL DEFAULT 0,
                sl REAL DEFAULT 0,
                position_size_usd REAL DEFAULT 0,
                position_size_units REAL DEFAULT 0,
                confidence REAL DEFAULT 0,
                strategies TEXT,
                indicators TEXT,
                mode TEXT NOT NULL,
                created_at TEXT NOT NULL,
                verified BOOLEAN DEFAULT 0
            )
        """)
        
        # Connector health table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS connector_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                connector_name TEXT NOT NULL UNIQUE,
                is_healthy BOOLEAN DEFAULT 1,
                last_check TEXT NOT NULL,
                latency_ms REAL DEFAULT 0,
                total_requests INTEGER DEFAULT 0,
                failed_requests INTEGER DEFAULT 0,
                last_error TEXT
            )
        """)
        
        # Telemetry table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                timestamp TEXT NOT NULL,
                labels TEXT
            )
        """)
        
        # Audit log table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                event_data TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                user_id TEXT,
                ip_address TEXT
            )
        """)
        
        # Create indexes for performance
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_created_at ON signals(created_at)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_checksum ON signals(checksum)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON telemetry(timestamp)")
        
        self.conn.commit()
        logger.info("✅ Database tables created")
    
    def save_signal(self, signal: Signal) -> int:
        """
        Save a signal to the database.
        
        Args:
            signal: Signal object to save
            
        Returns:
            The ID of the inserted signal
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO signals (
                    symbol, signal_type, canonical_price, primary_price, primary_source,
                    primary_timestamp, secondary_price, secondary_source, secondary_timestamp,
                    checksum_raw, checksum, tp1, tp2, tp3, sl, position_size_usd,
                    position_size_units, confidence, strategies, indicators, mode, created_at, verified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.symbol, signal.signal_type, signal.canonical_price,
                signal.primary_price, signal.primary_source, signal.primary_timestamp,
                signal.secondary_price, signal.secondary_source, signal.secondary_timestamp,
                signal.checksum_raw, signal.checksum, signal.tp1, signal.tp2, signal.tp3,
                signal.sl, signal.position_size_usd, signal.position_size_units,
                signal.confidence, signal.strategies, signal.indicators,
                signal.mode, signal.created_at, signal.verified
            ))
            self.conn.commit()
            signal_id = cursor.lastrowid
            signal.id = signal_id
            logger.debug(f"✅ Signal saved: ID={signal_id}, checksum={signal.checksum[:12]}...")
            return signal_id
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: signals.checksum" in str(e):
                logger.warning(f"⚠️ Signal with checksum {signal.checksum[:12]}... already exists")
                # Try to get existing signal
                existing = self.get_signal_by_checksum(signal.checksum)
                return existing.id if existing else -1
            raise
        except Exception as e:
            logger.error(f"❌ Failed to save signal: {e}")
            raise
    
    def get_signal_by_id(self, signal_id: int) -> Optional[Signal]:
        """Get a signal by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM signals WHERE id = ?", (signal_id,))
        row = cursor.fetchone()
        if row:
            return Signal(**dict(row))
        return None
    
    def get_signal_by_checksum(self, checksum: str) -> Optional[Signal]:
        """Get a signal by checksum."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM signals WHERE checksum = ?", (checksum,))
        row = cursor.fetchone()
        if row:
            return Signal(**dict(row))
        return None
    
    def get_signals(self, limit: int = 100, symbol: Optional[str] = None) -> List[Signal]:
        """
        Get signals from the database.
        
        Args:
            limit: Maximum number of signals to return
            symbol: Filter by symbol (optional)
            
        Returns:
            List of Signal objects
        """
        cursor = self.conn.cursor()
        if symbol:
            cursor.execute("""
                SELECT * FROM signals 
                WHERE symbol = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (symbol, limit))
        else:
            cursor.execute("""
                SELECT * FROM signals 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        return [Signal(**dict(row)) for row in rows]
    
    def verify_signal(self, signal_id: int) -> Dict[str, Any]:
        """
        Verify a signal by recalculating its checksum.
        
        Args:
            signal_id: ID of the signal to verify
            
        Returns:
            Dictionary with verification result and details
        """
        import hashlib
        
        signal = self.get_signal_by_id(signal_id)
        if not signal:
            return {'status': 'FAIL', 'reason': 'Signal not found'}
        
        # Recalculate checksum
        checksum_raw = (
            f"{signal.symbol}|{signal.canonical_price:.8f}|"
            f"{signal.primary_timestamp}|{signal.primary_source}|"
            f"{signal.secondary_timestamp}|{signal.secondary_source}"
        )
        calculated_checksum = hashlib.sha256(checksum_raw.encode()).hexdigest()
        
        # Compare
        is_valid = calculated_checksum == signal.checksum
        
        result = {
            'status': 'PASS' if is_valid else 'FAIL',
            'signal_id': signal_id,
            'original_checksum': signal.checksum,
            'calculated_checksum': calculated_checksum,
            'checksum_raw': checksum_raw,
            'diff': None if is_valid else {
                'original': signal.checksum,
                'calculated': calculated_checksum
            }
        }
        
        # Update verification status
        if is_valid:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE signals SET verified = 1 WHERE id = ?", (signal_id,))
            self.conn.commit()
        
        return result
    
    def update_connector_health(self, health: ConnectorHealth):
        """Update connector health status."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO connector_health 
            (connector_name, is_healthy, last_check, latency_ms, 
             total_requests, failed_requests, last_error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(connector_name) DO UPDATE SET
                is_healthy = excluded.is_healthy,
                last_check = excluded.last_check,
                latency_ms = excluded.latency_ms,
                total_requests = excluded.total_requests,
                failed_requests = excluded.failed_requests,
                last_error = excluded.last_error
        """, (
            health.connector_name, health.is_healthy, health.last_check,
            health.latency_ms, health.total_requests, health.failed_requests,
            health.last_error
        ))
        self.conn.commit()
    
    def get_connector_health(self, connector_name: str) -> Optional[ConnectorHealth]:
        """Get connector health status."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM connector_health WHERE connector_name = ?", (connector_name,))
        row = cursor.fetchone()
        if row:
            return ConnectorHealth(**dict(row))
        return None
    
    def record_telemetry(self, metric_name: str, metric_value: float, labels: Optional[Dict] = None):
        """Record a telemetry metric."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO telemetry (metric_name, metric_value, timestamp, labels)
            VALUES (?, ?, ?, ?)
        """, (
            metric_name, metric_value,
            datetime.utcnow().isoformat(),
            json.dumps(labels) if labels else None
        ))
        self.conn.commit()
    
    def get_telemetry(self, metric_name: str, limit: int = 100) -> List[Telemetry]:
        """Get telemetry metrics."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM telemetry 
            WHERE metric_name = ?
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (metric_name, limit))
        rows = cursor.fetchall()
        return [Telemetry(**dict(row)) for row in rows]
    
    def log_audit(self, event_type: str, event_data: Dict, user_id: Optional[str] = None, 
                  ip_address: Optional[str] = None):
        """Log an audit event."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO audit_log (event_type, event_data, timestamp, user_id, ip_address)
            VALUES (?, ?, ?, ?, ?)
        """, (
            event_type, json.dumps(event_data),
            datetime.utcnow().isoformat(), user_id, ip_address
        ))
        self.conn.commit()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get aggregate metrics for the /metrics endpoint."""
        cursor = self.conn.cursor()
        
        # Total signals
        cursor.execute("SELECT COUNT(*) FROM signals")
        total_signals = cursor.fetchone()[0]
        
        # Signals by confidence bucket
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN confidence < 30 THEN 'LOW'
                    WHEN confidence < 60 THEN 'MEDIUM'
                    WHEN confidence < 80 THEN 'HIGH'
                    ELSE 'VERY_HIGH'
                END as bucket,
                COUNT(*) as count
            FROM signals
            GROUP BY bucket
        """)
        confidence_buckets = {row['bucket']: row['count'] for row in cursor.fetchall()}
        
        # Signals by type
        cursor.execute("""
            SELECT signal_type, COUNT(*) as count
            FROM signals
            GROUP BY signal_type
        """)
        signals_by_type = {row['signal_type']: row['count'] for row in cursor.fetchall()}
        
        # Connector health
        cursor.execute("SELECT * FROM connector_health")
        connector_health = [dict(row) for row in cursor.fetchall()]
        
        return {
            'total_signals': total_signals,
            'signals_by_confidence_bucket': confidence_buckets,
            'signals_by_type': signals_by_type,
            'connector_health': connector_health
        }
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("✅ Database connection closed")