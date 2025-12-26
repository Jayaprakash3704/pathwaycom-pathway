"""
Incident Store - Stateful memory via Pathway tables.

This module provides a Pathway-native incident storage solution
that maintains state across streaming computations. It enables
real-time querying of historical incidents within the Pathway
dataflow graph.
"""

import pathway as pw
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass
import json


# =============================================================================
# PATHWAY SCHEMAS
# =============================================================================

class IncidentSchema(pw.Schema):
    """Schema for incident records in Pathway tables."""
    incident_id: str
    anomaly_id: str
    anomaly_type: str
    severity: int
    source: str
    description: str
    detected_at: str
    root_cause: str
    impact: str
    priority: str
    actions_taken: str  # JSON-encoded list
    action_status: str
    similar_to: str  # JSON-encoded list
    tags: str  # JSON-encoded list
    created_at: str


class IncidentSummarySchema(pw.Schema):
    """Schema for incident summary/stats."""
    source: str
    total_incidents: int
    avg_severity: float
    last_incident_at: str


# =============================================================================
# PATHWAY INCIDENT TABLE BUILDER
# =============================================================================

class PathwayIncidentStore:
    """
    Pathway-based incident storage.
    
    Uses Pathway tables for real-time incident tracking
    that integrates with the streaming pipeline.
    """
    
    def __init__(self):
        """Initialize the Pathway incident store."""
        self._incidents_table: Optional[pw.Table] = None
        self._summary_table: Optional[pw.Table] = None
    
    @property
    def incidents(self) -> Optional[pw.Table]:
        """Get the incidents table."""
        return self._incidents_table
    
    @property
    def summary(self) -> Optional[pw.Table]:
        """Get the summary table."""
        return self._summary_table
    
    def create_from_stream(self, incident_stream: pw.Table) -> pw.Table:
        """
        Create incident table from a stream of incident data.
        
        Args:
            incident_stream: Stream of incident records
        
        Returns:
            Pathway table with all incidents
        """
        self._incidents_table = incident_stream
        return self._incidents_table
    
    def compute_summaries(self, incidents: pw.Table) -> pw.Table:
        """
        Compute incident summaries by source.
        
        Args:
            incidents: Table of incidents
        
        Returns:
            Summary table with aggregations per source
        """
        self._summary_table = incidents.groupby(incidents.source).reduce(
            source=pw.this.source,
            total_incidents=pw.reducers.count(),
            avg_severity=pw.reducers.avg(pw.this.severity),
            last_incident_at=pw.reducers.max(pw.this.detected_at),
        )
        return self._summary_table
    
    def compute_severity_distribution(self, incidents: pw.Table) -> pw.Table:
        """
        Compute incident distribution by severity.
        
        Args:
            incidents: Table of incidents
        
        Returns:
            Table with counts per severity level
        """
        return incidents.groupby(incidents.severity).reduce(
            severity=pw.this.severity,
            count=pw.reducers.count(),
        )
    
    def compute_type_distribution(self, incidents: pw.Table) -> pw.Table:
        """
        Compute incident distribution by anomaly type.
        
        Args:
            incidents: Table of incidents
        
        Returns:
            Table with counts per anomaly type
        """
        return incidents.groupby(incidents.anomaly_type).reduce(
            anomaly_type=pw.this.anomaly_type,
            count=pw.reducers.count(),
            avg_severity=pw.reducers.avg(pw.this.severity),
        )


# =============================================================================
# INCIDENT RECORD CONVERTER
# =============================================================================

def agent_state_to_incident_row(state: Dict) -> Dict:
    """
    Convert agent state to incident row format.
    
    Args:
        state: AgentState dictionary from memory agent
    
    Returns:
        Dictionary matching IncidentSchema
    """
    incident_record = state.get("incident_record", {})
    
    return {
        "incident_id": incident_record.get("incident_id", ""),
        "anomaly_id": state.get("anomaly_id", ""),
        "anomaly_type": state.get("anomaly_type", ""),
        "severity": state.get("severity", 1),
        "source": state.get("source", ""),
        "description": state.get("description", ""),
        "detected_at": state.get("detected_at", datetime.utcnow().isoformat()),
        "root_cause": state.get("root_cause_analysis", ""),
        "impact": state.get("impact_assessment", ""),
        "priority": state.get("priority_level", ""),
        "actions_taken": json.dumps(state.get("actions_taken", [])),
        "action_status": state.get("action_status", ""),
        "similar_to": json.dumps([
            s.get("id", "") for s in state.get("similar_incidents", [])
        ]),
        "tags": json.dumps(incident_record.get("tags", [])),
        "created_at": datetime.utcnow().isoformat(),
    }


# =============================================================================
# STREAMING INCIDENT SINK
# =============================================================================

class IncidentStreamSink:
    """
    Sink for streaming incident data to storage.
    
    Collects processed incidents and can output to
    various destinations (files, databases, etc.)
    """
    
    def __init__(self, output_path: Optional[str] = None):
        """
        Initialize the incident sink.
        
        Args:
            output_path: Optional path for file-based output
        """
        self.output_path = output_path
        self.incident_count = 0
    
    def create_file_sink(self, incidents: pw.Table) -> None:
        """
        Create a file sink for incidents.
        
        Args:
            incidents: Pathway table of incidents
        """
        if self.output_path:
            pw.io.csv.write(incidents, self.output_path)
    
    def create_json_sink(self, incidents: pw.Table, path: str) -> None:
        """
        Create a JSON Lines sink for incidents.
        
        Args:
            incidents: Pathway table of incidents
            path: Output file path
        """
        pw.io.jsonlines.write(incidents, path)


# =============================================================================
# REAL-TIME INCIDENT QUERIES
# =============================================================================

def filter_high_severity(incidents: pw.Table, min_severity: int = 4) -> pw.Table:
    """Filter to high severity incidents only."""
    return incidents.filter(incidents.severity >= min_severity)


def filter_by_source(incidents: pw.Table, source: str) -> pw.Table:
    """Filter incidents by source service."""
    return incidents.filter(incidents.source == source)


def filter_by_type(incidents: pw.Table, anomaly_type: str) -> pw.Table:
    """Filter incidents by anomaly type."""
    return incidents.filter(incidents.anomaly_type == anomaly_type)


def filter_escalated(incidents: pw.Table) -> pw.Table:
    """Filter to escalated incidents only."""
    return incidents.filter(
        pw.apply(
            lambda tags: "escalated" in tags,
            incidents.tags
        )
    )


# =============================================================================
# INCIDENT STORE FACTORY
# =============================================================================

def create_incident_store() -> PathwayIncidentStore:
    """Create a new Pathway incident store instance."""
    return PathwayIncidentStore()


# =============================================================================
# INCIDENT OUTPUT FORMATTERS
# =============================================================================

def format_incident_for_logging(row: Dict) -> str:
    """Format an incident row for console logging."""
    return (
        f"[{row.get('priority', 'UNKNOWN')}] "
        f"{row.get('incident_id', 'N/A')} | "
        f"{row.get('source', 'unknown')}: "
        f"{row.get('anomaly_type', 'unknown')} "
        f"(severity: {row.get('severity', 0)})"
    )


def format_incident_summary(summary_row: Dict) -> str:
    """Format a summary row for reporting."""
    return (
        f"Source: {summary_row.get('source', 'unknown')} | "
        f"Total: {summary_row.get('total_incidents', 0)} | "
        f"Avg Severity: {summary_row.get('avg_severity', 0):.1f} | "
        f"Last: {summary_row.get('last_incident_at', 'N/A')}"
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "IncidentSchema",
    "IncidentSummarySchema",
    "PathwayIncidentStore",
    "agent_state_to_incident_row",
    "IncidentStreamSink",
    "filter_high_severity",
    "filter_by_source",
    "filter_by_type",
    "filter_escalated",
    "create_incident_store",
    "format_incident_for_logging",
    "format_incident_summary",
]
