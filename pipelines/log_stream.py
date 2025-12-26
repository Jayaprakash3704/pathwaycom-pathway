"""
Log Stream Pipeline - Real-time log ingestion using Pathway.

This module provides continuous log stream ingestion with a mock generator
for simulating live system logs. Uses Pathway's streaming capabilities
to process logs in real-time.
"""

import pathway as pw
import random
import time
from datetime import datetime
from typing import Optional
from dataclasses import dataclass


# =============================================================================
# LOG SCHEMA DEFINITION
# =============================================================================

class LogSchema(pw.Schema):
    """Schema for incoming log events."""
    timestamp: str
    level: str  # INFO, WARNING, ERROR, CRITICAL
    message: str
    source: str
    request_id: Optional[str]


# =============================================================================
# MOCK LOG GENERATOR
# =============================================================================

class MockLogGenerator:
    """
    Generates realistic mock log entries simulating a live system.
    
    Produces a mix of normal operations and occasional error spikes
    to trigger anomaly detection.
    """
    
    # Log templates by level
    LOG_TEMPLATES = {
        "INFO": [
            "Request processed successfully",
            "User authenticated",
            "Cache hit for key {key}",
            "Database query completed in {ms}ms",
            "Service health check passed",
            "Session started for user {user}",
            "API response sent: 200 OK",
        ],
        "WARNING": [
            "High memory usage detected: {pct}%",
            "Slow query detected: {ms}ms",
            "Rate limit approaching for client {client}",
            "Retry attempt {n} for external service",
            "Connection pool running low",
            "Cache miss for frequently accessed key",
        ],
        "ERROR": [
            "Database connection failed",
            "External API timeout after {ms}ms",
            "Authentication failed for user {user}",
            "Invalid request payload received",
            "Service unavailable: {service}",
            "Disk space critically low",
            "Memory allocation failed",
        ],
        "CRITICAL": [
            "System crash detected",
            "Data corruption in table {table}",
            "Security breach attempt detected",
            "Complete service outage",
            "Database cluster failover triggered",
        ]
    }
    
    SOURCES = [
        "api-gateway",
        "auth-service",
        "user-service",
        "payment-service",
        "notification-service",
        "database-proxy",
        "cache-layer",
        "load-balancer",
    ]
    
    def __init__(self, error_spike_probability: float = 0.1):
        """
        Initialize the mock log generator.
        
        Args:
            error_spike_probability: Chance of generating an error spike (0.0-1.0)
        """
        self.error_spike_probability = error_spike_probability
        self.request_counter = 0
        self._in_error_spike = False
        self._spike_remaining = 0
    
    def _format_template(self, template: str) -> str:
        """Fill in template placeholders with random values."""
        replacements = {
            "{key}": f"cache_key_{random.randint(1000, 9999)}",
            "{ms}": str(random.randint(50, 5000)),
            "{user}": f"user_{random.randint(1, 1000)}",
            "{pct}": str(random.randint(80, 99)),
            "{client}": f"client_{random.randint(1, 100)}",
            "{n}": str(random.randint(1, 5)),
            "{service}": random.choice(self.SOURCES),
            "{table}": f"table_{random.choice(['users', 'orders', 'sessions', 'logs'])}",
        }
        
        result = template
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)
        return result
    
    def _select_level(self) -> str:
        """Select log level with realistic distribution, accounting for error spikes."""
        
        # Check if we should start an error spike
        if not self._in_error_spike and random.random() < self.error_spike_probability:
            self._in_error_spike = True
            self._spike_remaining = random.randint(5, 15)  # Spike lasts 5-15 logs
        
        # During error spike, heavily favor errors
        if self._in_error_spike:
            self._spike_remaining -= 1
            if self._spike_remaining <= 0:
                self._in_error_spike = False
            
            # 70% ERROR, 20% CRITICAL, 10% WARNING during spike
            r = random.random()
            if r < 0.7:
                return "ERROR"
            elif r < 0.9:
                return "CRITICAL"
            else:
                return "WARNING"
        
        # Normal distribution: 70% INFO, 20% WARNING, 8% ERROR, 2% CRITICAL
        r = random.random()
        if r < 0.70:
            return "INFO"
        elif r < 0.90:
            return "WARNING"
        elif r < 0.98:
            return "ERROR"
        else:
            return "CRITICAL"
    
    def generate_log(self) -> dict:
        """Generate a single log entry."""
        self.request_counter += 1
        
        level = self._select_level()
        template = random.choice(self.LOG_TEMPLATES[level])
        message = self._format_template(template)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "source": random.choice(self.SOURCES),
            "request_id": f"req_{self.request_counter:08d}",
        }


# =============================================================================
# PATHWAY LOG STREAM INPUT
# =============================================================================

class LogStreamSubject(pw.io.python.ConnectorSubject):
    """
    Pathway connector subject for streaming mock logs.
    
    This runs in a separate thread and continuously generates
    log entries at a configurable rate.
    """
    
    def __init__(self, logs_per_second: float = 5.0, error_spike_prob: float = 0.1):
        """
        Initialize the log stream subject.
        
        Args:
            logs_per_second: Rate of log generation
            error_spike_prob: Probability of error spike occurrence
        """
        super().__init__()
        self.logs_per_second = logs_per_second
        self.generator = MockLogGenerator(error_spike_probability=error_spike_prob)
        self._running = True
    
    def run(self):
        """Main loop that generates logs continuously."""
        interval = 1.0 / self.logs_per_second
        
        while self._running:
            log_entry = self.generator.generate_log()
            
            # Send to Pathway stream
            self.next(
                timestamp=log_entry["timestamp"],
                level=log_entry["level"],
                message=log_entry["message"],
                source=log_entry["source"],
                request_id=log_entry["request_id"],
            )
            
            time.sleep(interval)
    
    def stop(self):
        """Stop the log generation."""
        self._running = False


def create_log_stream(
    logs_per_second: float = 5.0,
    error_spike_prob: float = 0.1
) -> pw.Table:
    """
    Create a Pathway table streaming mock log data.
    
    Args:
        logs_per_second: Rate of log generation
        error_spike_prob: Probability of error spikes (for testing anomaly detection)
    
    Returns:
        Pathway Table with streaming log data
    """
    subject = LogStreamSubject(
        logs_per_second=logs_per_second,
        error_spike_prob=error_spike_prob
    )
    
    return pw.io.python.read(
        subject,
        schema=LogSchema,
        autocommit_duration_ms=100,  # Commit every 100ms for real-time feel
    )


# =============================================================================
# LOG STREAM TRANSFORMATIONS
# =============================================================================

def enrich_log_stream(logs: pw.Table) -> pw.Table:
    """
    Enrich log entries with additional computed fields.
    
    Adds:
        - severity_score: Numeric severity (1-4)
        - is_error: Boolean flag for error-level logs
    """
    severity_map = {
        "INFO": 1,
        "WARNING": 2,
        "ERROR": 3,
        "CRITICAL": 4,
    }
    
    return logs.select(
        *logs,
        severity_score=pw.apply(lambda lvl: severity_map.get(lvl, 1), logs.level),
        is_error=pw.apply(lambda lvl: lvl in ("ERROR", "CRITICAL"), logs.level),
    )


def filter_errors_only(logs: pw.Table) -> pw.Table:
    """Filter to keep only ERROR and CRITICAL level logs."""
    return logs.filter(
        pw.apply(lambda lvl: lvl in ("ERROR", "CRITICAL"), logs.level)
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "LogSchema",
    "MockLogGenerator",
    "LogStreamSubject",
    "create_log_stream",
    "enrich_log_stream",
    "filter_errors_only",
]
