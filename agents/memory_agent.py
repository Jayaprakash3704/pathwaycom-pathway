"""
Memory Agent - Reads and writes historical incidents.

The Memory Agent maintains context across incidents by storing
and retrieving historical data. It enables the system to learn
from past incidents and provide relevant context for new ones.
"""

import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib

# Import shared state type
from .observer_agent import AgentState


# =============================================================================
# INCIDENT RECORD
# =============================================================================

@dataclass
class IncidentRecord:
    """
    Complete record of an incident for historical storage.
    """
    incident_id: str
    anomaly_id: str
    anomaly_type: str
    severity: int
    source: str
    description: str
    
    # Timestamps
    detected_at: str
    resolved_at: Optional[str] = None
    
    # Agent analysis
    root_cause: str = ""
    impact: str = ""
    
    # Response
    priority: str = ""
    actions_taken: List[str] = field(default_factory=list)
    action_status: str = ""
    
    # Resolution
    resolution_notes: str = ""
    mttr_seconds: Optional[int] = None  # Mean Time To Resolution
    
    # Metadata
    similar_to: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            "incident_id": self.incident_id,
            "anomaly_id": self.anomaly_id,
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "source": self.source,
            "description": self.description,
            "detected_at": self.detected_at,
            "resolved_at": self.resolved_at,
            "root_cause": self.root_cause,
            "impact": self.impact,
            "priority": self.priority,
            "actions_taken": self.actions_taken,
            "action_status": self.action_status,
            "resolution_notes": self.resolution_notes,
            "mttr_seconds": self.mttr_seconds,
            "similar_to": self.similar_to,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "IncidentRecord":
        """Create from dictionary."""
        return cls(**data)


# =============================================================================
# IN-MEMORY INCIDENT STORE
# =============================================================================

class InMemoryIncidentStore:
    """
    Simple in-memory storage for incidents.
    
    In production, this would be backed by Pathway tables
    or an external database. This implementation provides
    the same interface for development/testing.
    """
    
    def __init__(self):
        """Initialize the in-memory store."""
        self.incidents: Dict[str, IncidentRecord] = {}
        self.by_source: Dict[str, List[str]] = defaultdict(list)
        self.by_type: Dict[str, List[str]] = defaultdict(list)
        self.by_severity: Dict[int, List[str]] = defaultdict(list)
    
    def store(self, record: IncidentRecord) -> None:
        """Store an incident record."""
        self.incidents[record.incident_id] = record
        self.by_source[record.source].append(record.incident_id)
        self.by_type[record.anomaly_type].append(record.incident_id)
        self.by_severity[record.severity].append(record.incident_id)
    
    def get(self, incident_id: str) -> Optional[IncidentRecord]:
        """Retrieve an incident by ID."""
        return self.incidents.get(incident_id)
    
    def find_similar(
        self,
        anomaly_type: str,
        source: str,
        limit: int = 5
    ) -> List[IncidentRecord]:
        """Find similar incidents based on type and source."""
        candidates = set()
        
        # Get incidents with same type
        type_matches = self.by_type.get(anomaly_type, [])
        candidates.update(type_matches[-limit:])
        
        # Get incidents from same source
        source_matches = self.by_source.get(source, [])
        candidates.update(source_matches[-limit:])
        
        # Retrieve and return records
        results = []
        for incident_id in list(candidates)[-limit:]:
            record = self.incidents.get(incident_id)
            if record:
                results.append(record)
        
        return results
    
    def get_recent(self, hours: int = 24, limit: int = 10) -> List[IncidentRecord]:
        """Get recent incidents."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()
        
        recent = [
            record for record in self.incidents.values()
            if record.detected_at >= cutoff_str
        ]
        
        # Sort by detection time, most recent first
        recent.sort(key=lambda r: r.detected_at, reverse=True)
        return recent[:limit]
    
    def get_stats(self) -> Dict:
        """Get store statistics."""
        return {
            "total_incidents": len(self.incidents),
            "by_type": {k: len(v) for k, v in self.by_type.items()},
            "by_source": {k: len(v) for k, v in self.by_source.items()},
            "by_severity": {k: len(v) for k, v in self.by_severity.items()},
        }


# Global incident store instance
_incident_store = InMemoryIncidentStore()


def get_incident_store() -> InMemoryIncidentStore:
    """Get the global incident store instance."""
    return _incident_store


# =============================================================================
# SIMILARITY SCORING
# =============================================================================

class SimilarityScorer:
    """
    Scores similarity between incidents.
    
    Uses multiple factors to determine how similar
    two incidents are.
    """
    
    @staticmethod
    def compute_similarity(
        current: AgentState,
        historical: IncidentRecord
    ) -> float:
        """
        Compute similarity score between current anomaly and historical incident.
        
        Returns a score from 0.0 (no similarity) to 1.0 (identical).
        """
        score = 0.0
        
        # Same anomaly type: +0.4
        if current.get("anomaly_type") == historical.anomaly_type:
            score += 0.4
        
        # Same source: +0.3
        if current.get("source") == historical.source:
            score += 0.3
        
        # Similar severity (within 1): +0.2
        severity_diff = abs(current.get("severity", 0) - historical.severity)
        if severity_diff <= 1:
            score += 0.2
        elif severity_diff <= 2:
            score += 0.1
        
        # Similar description (basic word overlap): +0.1
        current_words = set(current.get("description", "").lower().split())
        historical_words = set(historical.description.lower().split())
        if current_words and historical_words:
            overlap = len(current_words & historical_words)
            total = len(current_words | historical_words)
            if total > 0:
                score += 0.1 * (overlap / total)
        
        return min(1.0, score)


# =============================================================================
# MEMORY AGENT
# =============================================================================

@dataclass
class MemoryConfig:
    """Configuration for the Memory Agent."""
    max_similar_incidents: int = 5
    similarity_threshold: float = 0.3
    store_all_incidents: bool = True


class MemoryAgent:
    """
    Memory Agent - Maintains historical context.
    
    Responsibilities:
    1. Find similar past incidents for context
    2. Create and store incident records
    3. Provide insights from historical data
    4. Enable learning from past responses
    """
    
    def __init__(self, config: Optional[MemoryConfig] = None):
        """Initialize the Memory Agent."""
        self.config = config or MemoryConfig()
        self.store = get_incident_store()
        self.scorer = SimilarityScorer()
    
    def remember(self, state: AgentState) -> AgentState:
        """
        Process memory operations for the current incident.
        
        Args:
            state: Current agent state from Action
        
        Returns:
            Updated state with memory context
        """
        # Find similar incidents
        similar = self._find_similar_incidents(state)
        
        # Create incident record
        record = self._create_incident_record(state, similar)
        
        # Store if configured
        if self.config.store_all_incidents:
            self.store.store(record)
        
        # Update state
        state["current_agent"] = "memory"
        state["similar_incidents"] = [
            {"id": s.incident_id, "type": s.anomaly_type, "source": s.source}
            for s in similar
        ]
        state["incident_record"] = record.to_dict()
        
        self._log_memory(state, len(similar))
        
        return state
    
    def _find_similar_incidents(self, state: AgentState) -> List[IncidentRecord]:
        """Find incidents similar to the current anomaly."""
        anomaly_type = state.get("anomaly_type", "")
        source = state.get("source", "")
        
        # Get candidates
        candidates = self.store.find_similar(
            anomaly_type=anomaly_type,
            source=source,
            limit=self.config.max_similar_incidents * 2
        )
        
        # Score and filter
        scored = []
        for candidate in candidates:
            score = self.scorer.compute_similarity(state, candidate)
            if score >= self.config.similarity_threshold:
                scored.append((score, candidate))
        
        # Sort by score and return top matches
        scored.sort(key=lambda x: x[0], reverse=True)
        return [record for _, record in scored[:self.config.max_similar_incidents]]
    
    def _create_incident_record(
        self,
        state: AgentState,
        similar: List[IncidentRecord]
    ) -> IncidentRecord:
        """Create an incident record from the current state."""
        # Generate incident ID
        anomaly_id = state.get("anomaly_id", "unknown")
        timestamp = state.get("detected_at", datetime.utcnow().isoformat())
        hash_input = f"{anomaly_id}-{timestamp}"
        incident_id = f"INC-{hashlib.md5(hash_input.encode()).hexdigest()[:12].upper()}"
        
        # Extract actions taken
        actions_taken = state.get("actions_taken", [])
        if isinstance(actions_taken, list):
            actions_list = actions_taken
        else:
            actions_list = [str(actions_taken)]
        
        # Generate tags
        tags = self._generate_tags(state)
        
        return IncidentRecord(
            incident_id=incident_id,
            anomaly_id=anomaly_id,
            anomaly_type=state.get("anomaly_type", "unknown"),
            severity=state.get("severity", 1),
            source=state.get("source", "unknown"),
            description=state.get("description", ""),
            detected_at=timestamp,
            resolved_at=None,  # Will be updated when resolved
            root_cause=state.get("root_cause_analysis", ""),
            impact=state.get("impact_assessment", ""),
            priority=state.get("priority_level", ""),
            actions_taken=actions_list,
            action_status=state.get("action_status", ""),
            resolution_notes="",
            mttr_seconds=None,
            similar_to=[s.incident_id for s in similar],
            tags=tags,
        )
    
    def _generate_tags(self, state: AgentState) -> List[str]:
        """Generate tags for the incident."""
        tags = []
        
        # Add severity tag
        severity = state.get("severity", 1)
        tags.append(f"severity-{severity}")
        
        # Add type tag
        anomaly_type = state.get("anomaly_type", "unknown")
        tags.append(f"type-{anomaly_type}")
        
        # Add source tag
        source = state.get("source", "unknown")
        tags.append(f"source-{source}")
        
        # Add escalation tag if needed
        if state.get("escalation_required", False):
            tags.append("escalated")
        
        return tags
    
    def _log_memory(self, state: AgentState, similar_count: int) -> None:
        """Log memory operations."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "anomaly_id": state["anomaly_id"],
            "incident_id": state["incident_record"].get("incident_id"),
            "similar_found": similar_count,
            "total_stored": len(self.store.incidents),
        }
        print(f"[MEMORY] {json.dumps(log_entry)}")
    
    def get_insights(self) -> Dict:
        """Get insights from historical data."""
        stats = self.store.get_stats()
        recent = self.store.get_recent(hours=24)
        
        return {
            "store_stats": stats,
            "recent_incidents": len(recent),
            "top_sources": sorted(
                stats["by_source"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            "severity_distribution": stats["by_severity"],
        }


# =============================================================================
# LANGGRAPH NODE FUNCTION
# =============================================================================

def memory_node(state: AgentState) -> AgentState:
    """
    LangGraph node function for the Memory Agent.
    
    Args:
        state: Current workflow state from Action
    
    Returns:
        Updated state with memory context
    """
    agent = MemoryAgent()
    return agent.remember(state)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "IncidentRecord",
    "InMemoryIncidentStore",
    "get_incident_store",
    "SimilarityScorer",
    "MemoryConfig",
    "MemoryAgent",
    "memory_node",
]
