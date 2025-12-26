"""
Anomaly Detector Pipeline - Real-time pattern detection using Pathway.

This module implements windowed aggregations and pattern matching to detect
anomalous behavior in log streams, such as error spikes, unusual patterns,
and threshold violations.
"""

import pathway as pw
from datetime import datetime, timedelta
from typing import Callable, Any
from dataclasses import dataclass
from enum import Enum


# =============================================================================
# ANOMALY TYPES AND SCHEMAS
# =============================================================================

class AnomalyType(str, Enum):
    """Types of anomalies that can be detected."""
    ERROR_SPIKE = "error_spike"
    HIGH_ERROR_RATE = "high_error_rate"
    SERVICE_DEGRADATION = "service_degradation"
    CRITICAL_EVENT = "critical_event"
    PATTERN_MATCH = "pattern_match"


class AnomalySchema(pw.Schema):
    """Schema for detected anomaly events."""
    anomaly_id: str
    anomaly_type: str
    severity: int  # 1-5 scale
    detected_at: str
    source: str
    description: str
    error_count: int
    window_duration_seconds: int
    context: str  # JSON-encoded context data


# =============================================================================
# WINDOWED AGGREGATIONS
# =============================================================================

@dataclass
class WindowConfig:
    """Configuration for time-based windows."""
    duration_seconds: int = 60
    slide_seconds: int = 10


def compute_error_counts_by_source(
    logs: pw.Table,
    window_config: WindowConfig = WindowConfig()
) -> pw.Table:
    """
    Compute error counts per source within sliding windows.
    
    Args:
        logs: Enriched log table with severity_score and is_error fields
        window_config: Window configuration
    
    Returns:
        Table with error counts per source per window
    """
    # Filter to errors only
    errors = logs.filter(logs.is_error == True)
    
    # Group by source and count
    error_counts = errors.groupby(errors.source).reduce(
        source=pw.this.source,
        error_count=pw.reducers.count(),
        max_severity=pw.reducers.max(pw.this.severity_score),
        latest_timestamp=pw.reducers.max(pw.this.timestamp),
        sample_messages=pw.reducers.tuple(pw.this.message),
    )
    
    return error_counts


def compute_overall_error_rate(logs: pw.Table) -> pw.Table:
    """
    Compute the overall error rate across all logs.
    
    Returns a single-row table with current error statistics.
    """
    stats = logs.reduce(
        total_count=pw.reducers.count(),
        error_count=pw.reducers.sum(
            pw.apply(lambda is_err: 1 if is_err else 0, logs.is_error)
        ),
        critical_count=pw.reducers.sum(
            pw.apply(lambda lvl: 1 if lvl == "CRITICAL" else 0, logs.level)
        ),
        max_severity=pw.reducers.max(logs.severity_score),
    )
    
    return stats


def compute_error_rate_by_service(logs: pw.Table) -> pw.Table:
    """
    Compute error rates grouped by service/source.
    
    Helps identify which services are experiencing issues.
    """
    by_service = logs.groupby(logs.source).reduce(
        source=pw.this.source,
        total_logs=pw.reducers.count(),
        error_logs=pw.reducers.sum(
            pw.apply(lambda is_err: 1 if is_err else 0, pw.this.is_error)
        ),
        critical_logs=pw.reducers.sum(
            pw.apply(lambda lvl: 1 if lvl == "CRITICAL" else 0, pw.this.level)
        ),
    )
    
    # Add error rate calculation
    return by_service.select(
        *by_service,
        error_rate=pw.apply(
            lambda total, errors: errors / total if total > 0 else 0.0,
            by_service.total_logs,
            by_service.error_logs
        ),
    )


# =============================================================================
# ANOMALY DETECTION RULES
# =============================================================================

class AnomalyDetector:
    """
    Stateless anomaly detection using threshold-based rules.
    
    Applies multiple detection strategies to identify anomalies
    in real-time log streams.
    """
    
    def __init__(
        self,
        error_spike_threshold: int = 5,
        error_rate_threshold: float = 0.3,
        critical_threshold: int = 1,
    ):
        """
        Initialize anomaly detector with thresholds.
        
        Args:
            error_spike_threshold: Number of errors to trigger spike detection
            error_rate_threshold: Error rate (0-1) to trigger high error rate
            critical_threshold: Number of critical events to trigger alert
        """
        self.error_spike_threshold = error_spike_threshold
        self.error_rate_threshold = error_rate_threshold
        self.critical_threshold = critical_threshold
        self._anomaly_counter = 0
    
    def _generate_anomaly_id(self) -> str:
        """Generate a unique anomaly ID."""
        self._anomaly_counter += 1
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"ANOMALY-{timestamp}-{self._anomaly_counter:06d}"


def detect_error_spikes(
    error_counts: pw.Table,
    threshold: int = 5
) -> pw.Table:
    """
    Detect sources experiencing error spikes.
    
    An error spike is when the error count exceeds the threshold
    within the aggregation window.
    
    Args:
        error_counts: Table with error counts per source
        threshold: Minimum errors to consider a spike
    
    Returns:
        Table of detected error spike anomalies
    """
    # Filter to sources exceeding threshold
    spikes = error_counts.filter(error_counts.error_count >= threshold)
    
    # Transform to anomaly format
    anomalies = spikes.select(
        anomaly_id=pw.apply(
            lambda src, ts: f"SPIKE-{src}-{ts[:19].replace(':', '').replace('-', '')}",
            spikes.source,
            spikes.latest_timestamp
        ),
        anomaly_type=pw.apply(lambda _: AnomalyType.ERROR_SPIKE.value, spikes.source),
        severity=pw.apply(
            lambda count, max_sev: min(5, max(3, count // 3 + max_sev - 2)),
            spikes.error_count,
            spikes.max_severity
        ),
        detected_at=spikes.latest_timestamp,
        source=spikes.source,
        description=pw.apply(
            lambda src, count: f"Error spike detected in {src}: {count} errors in window",
            spikes.source,
            spikes.error_count
        ),
        error_count=spikes.error_count,
        window_duration_seconds=pw.apply(lambda _: 60, spikes.source),  # Default window
        context=pw.apply(
            lambda msgs: str(list(msgs)[:5]) if msgs else "[]",
            spikes.sample_messages
        ),
    )
    
    return anomalies


def detect_high_error_rate(
    service_stats: pw.Table,
    threshold: float = 0.3
) -> pw.Table:
    """
    Detect services with high error rates.
    
    Args:
        service_stats: Table with error rates by service
        threshold: Error rate (0-1) to trigger detection
    
    Returns:
        Table of high error rate anomalies
    """
    high_rate = service_stats.filter(service_stats.error_rate >= threshold)
    
    anomalies = high_rate.select(
        anomaly_id=pw.apply(
            lambda src: f"RATE-{src}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            high_rate.source
        ),
        anomaly_type=pw.apply(lambda _: AnomalyType.HIGH_ERROR_RATE.value, high_rate.source),
        severity=pw.apply(
            lambda rate: min(5, int(rate * 10) + 2),
            high_rate.error_rate
        ),
        detected_at=pw.apply(lambda _: datetime.utcnow().isoformat(), high_rate.source),
        source=high_rate.source,
        description=pw.apply(
            lambda src, rate: f"High error rate in {src}: {rate:.1%} of requests failing",
            high_rate.source,
            high_rate.error_rate
        ),
        error_count=high_rate.error_logs,
        window_duration_seconds=pw.apply(lambda _: 60, high_rate.source),
        context=pw.apply(
            lambda total, errs: f'{{"total": {total}, "errors": {errs}}}',
            high_rate.total_logs,
            high_rate.error_logs
        ),
    )
    
    return anomalies


def detect_critical_events(logs: pw.Table) -> pw.Table:
    """
    Detect critical-level log events immediately.
    
    Critical events are always treated as anomalies requiring
    immediate attention.
    
    Args:
        logs: Raw or enriched log table
    
    Returns:
        Table of critical event anomalies
    """
    critical = logs.filter(logs.level == "CRITICAL")
    
    anomalies = critical.select(
        anomaly_id=pw.apply(
            lambda req_id, ts: f"CRIT-{req_id or 'unknown'}-{ts[:19].replace(':', '').replace('-', '')}",
            critical.request_id,
            critical.timestamp
        ),
        anomaly_type=pw.apply(lambda _: AnomalyType.CRITICAL_EVENT.value, critical.level),
        severity=pw.apply(lambda _: 5, critical.level),  # Always max severity
        detected_at=critical.timestamp,
        source=critical.source,
        description=pw.apply(
            lambda src, msg: f"CRITICAL event from {src}: {msg}",
            critical.source,
            critical.message
        ),
        error_count=pw.apply(lambda _: 1, critical.level),
        window_duration_seconds=pw.apply(lambda _: 0, critical.level),  # Instant
        context=pw.apply(
            lambda msg, req_id: f'{{"message": "{msg}", "request_id": "{req_id or "N/A"}"}}',
            critical.message,
            critical.request_id
        ),
    )
    
    return anomalies


# =============================================================================
# COMBINED ANOMALY PIPELINE
# =============================================================================

def create_anomaly_detection_pipeline(
    enriched_logs: pw.Table,
    error_spike_threshold: int = 5,
    error_rate_threshold: float = 0.3,
) -> pw.Table:
    """
    Create a complete anomaly detection pipeline.
    
    Combines multiple detection strategies and merges results
    into a single anomaly stream.
    
    Args:
        enriched_logs: Enriched log table from log_stream module
        error_spike_threshold: Threshold for error spike detection
        error_rate_threshold: Threshold for high error rate detection
    
    Returns:
        Unified table of all detected anomalies
    """
    # Compute aggregations
    error_counts = compute_error_counts_by_source(enriched_logs)
    service_stats = compute_error_rate_by_service(enriched_logs)
    
    # Run detectors
    spike_anomalies = detect_error_spikes(error_counts, error_spike_threshold)
    rate_anomalies = detect_high_error_rate(service_stats, error_rate_threshold)
    critical_anomalies = detect_critical_events(enriched_logs)
    
    # Combine all anomalies using concat
    all_anomalies = pw.Table.concat_reindex(
        spike_anomalies,
        rate_anomalies,
        critical_anomalies,
    )
    
    return all_anomalies


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "AnomalyType",
    "AnomalySchema",
    "WindowConfig",
    "AnomalyDetector",
    "compute_error_counts_by_source",
    "compute_overall_error_rate",
    "compute_error_rate_by_service",
    "detect_error_spikes",
    "detect_high_error_rate",
    "detect_critical_events",
    "create_anomaly_detection_pipeline",
]
