"""Database models for Apex Signal Bot."""

import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict, field


@dataclass
class Signal:
    """Signal data model."""
    id: Optional[int] = None
    symbol: str = ""
    signal_type: str = ""  # BUY, SELL, HOLD
    canonical_price: float = 0.0
    primary_price: float = 0.0
    primary_source: str = ""
    primary_timestamp: str = ""
    secondary_price: float = 0.0
    secondary_source: str = ""
    secondary_timestamp: str = ""
    checksum_raw: str = ""
    checksum: str = ""
    tp1: float = 0.0
    tp2: float = 0.0
    tp3: float = 0.0
    sl: float = 0.0
    position_size_usd: float = 0.0
    position_size_units: float = 0.0
    confidence: float = 0.0
    strategies: str = ""  # JSON string
    indicators: str = ""  # JSON string
    mode: str = ""
    created_at: Optional[str] = None
    verified: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Signal':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class ConnectorHealth:
    """Connector health monitoring data model."""
    id: Optional[int] = None
    connector_name: str = ""
    is_healthy: bool = False
    last_check: str = ""
    latency_ms: float = 0.0
    total_requests: int = 0
    failed_requests: int = 0
    last_error: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return ((self.total_requests - self.failed_requests) / self.total_requests) * 100


@dataclass
class Telemetry:
    """Telemetry and metrics data model."""
    id: Optional[int] = None
    metric_name: str = ""
    metric_value: float = 0.0
    timestamp: str = ""
    labels: str = ""  # JSON string for labels
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class AuditLog:
    """Audit log for compliance and debugging."""
    id: Optional[int] = None
    event_type: str = ""
    event_data: str = ""  # JSON string
    timestamp: str = ""
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)