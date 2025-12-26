"""
Observer Agent - Monitors anomaly streams and triggers agent workflows.

The Observer is the entry point of the agent system. It watches for
anomaly events from the detection pipeline and initiates the
multi-agent reasoning workflow when anomalies are detected.
"""

from typing import TypedDict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field
import json


# =============================================================================
# AGENT STATE DEFINITION
# =============================================================================

class AgentState(TypedDict):
    """
    Shared state passed between agents in the workflow.
    
    This state accumulates information as it flows through
    the agent graph: Observer → Reasoning → Planning → Action → Memory
    """
    # Input from anomaly detection
    anomaly_id: str
    anomaly_type: str
    severity: int
    detected_at: str
    source: str
    description: str
    error_count: int
    context: str
    
    # Observer additions
    observation_timestamp: str
    initial_assessment: str
    should_process: bool
    
    # Reasoning additions
    root_cause_analysis: str
    impact_assessment: str
    confidence_score: float
    
    # Planning additions
    recommended_actions: List[str]
    priority_level: str
    escalation_required: bool
    
    # Action additions
    actions_taken: List[str]
    action_status: str
    action_timestamp: str
    
    # Memory additions
    similar_incidents: List[dict]
    incident_record: dict
    
    # Workflow metadata
    workflow_id: str
    current_agent: str
    error_message: Optional[str]


# =============================================================================
# OBSERVER AGENT
# =============================================================================

@dataclass
class ObserverConfig:
    """Configuration for the Observer Agent."""
    min_severity_to_process: int = 2
    always_process_critical: bool = True
    log_observations: bool = True


class ObserverAgent:
    """
    Observer Agent - Entry point of the agent workflow.
    
    Responsibilities:
    1. Receive anomaly events from the detection pipeline
    2. Perform initial assessment and filtering
    3. Decide whether to trigger the full agent workflow
    4. Initialize the shared agent state
    """
    
    def __init__(self, config: Optional[ObserverConfig] = None):
        """Initialize the Observer Agent."""
        self.config = config or ObserverConfig()
        self.observation_count = 0
        self.processed_count = 0
    
    def observe(self, anomaly_data: dict) -> AgentState:
        """
        Process an incoming anomaly and create initial agent state.
        
        Args:
            anomaly_data: Raw anomaly data from detection pipeline
        
        Returns:
            Initialized AgentState for the workflow
        """
        self.observation_count += 1
        
        # Extract anomaly fields
        anomaly_id = anomaly_data.get("anomaly_id", f"OBS-{self.observation_count}")
        severity = anomaly_data.get("severity", 1)
        anomaly_type = anomaly_data.get("anomaly_type", "unknown")
        
        # Determine if we should process this anomaly
        should_process = self._should_process_anomaly(severity, anomaly_type)
        
        # Generate initial assessment
        initial_assessment = self._generate_initial_assessment(anomaly_data)
        
        if should_process:
            self.processed_count += 1
        
        # Create the agent state
        state: AgentState = {
            # Input from anomaly detection
            "anomaly_id": anomaly_id,
            "anomaly_type": anomaly_type,
            "severity": severity,
            "detected_at": anomaly_data.get("detected_at", datetime.utcnow().isoformat()),
            "source": anomaly_data.get("source", "unknown"),
            "description": anomaly_data.get("description", ""),
            "error_count": anomaly_data.get("error_count", 0),
            "context": anomaly_data.get("context", "{}"),
            
            # Observer additions
            "observation_timestamp": datetime.utcnow().isoformat(),
            "initial_assessment": initial_assessment,
            "should_process": should_process,
            
            # Placeholders for downstream agents
            "root_cause_analysis": "",
            "impact_assessment": "",
            "confidence_score": 0.0,
            "recommended_actions": [],
            "priority_level": "",
            "escalation_required": False,
            "actions_taken": [],
            "action_status": "pending",
            "action_timestamp": "",
            "similar_incidents": [],
            "incident_record": {},
            
            # Workflow metadata
            "workflow_id": f"WF-{anomaly_id}",
            "current_agent": "observer",
            "error_message": None,
        }
        
        if self.config.log_observations:
            self._log_observation(state)
        
        return state
    
    def _should_process_anomaly(self, severity: int, anomaly_type: str) -> bool:
        """Determine if this anomaly should trigger the full workflow."""
        # Always process critical events
        if self.config.always_process_critical and anomaly_type == "critical_event":
            return True
        
        # Check severity threshold
        if severity >= self.config.min_severity_to_process:
            return True
        
        return False
    
    def _generate_initial_assessment(self, anomaly_data: dict) -> str:
        """Generate a brief initial assessment of the anomaly."""
        anomaly_type = anomaly_data.get("anomaly_type", "unknown")
        severity = anomaly_data.get("severity", 1)
        source = anomaly_data.get("source", "unknown")
        error_count = anomaly_data.get("error_count", 0)
        
        severity_label = {
            1: "LOW",
            2: "MEDIUM",
            3: "HIGH",
            4: "CRITICAL",
            5: "EMERGENCY"
        }.get(severity, "UNKNOWN")
        
        assessment_parts = [
            f"[{severity_label}] {anomaly_type.upper()} detected",
            f"Source: {source}",
            f"Error count: {error_count}",
        ]
        
        # Add type-specific observations
        if anomaly_type == "error_spike":
            assessment_parts.append("Pattern: Sudden increase in error rate")
        elif anomaly_type == "high_error_rate":
            assessment_parts.append("Pattern: Sustained high error percentage")
        elif anomaly_type == "critical_event":
            assessment_parts.append("Pattern: Critical system event requiring immediate attention")
        
        return " | ".join(assessment_parts)
    
    def _log_observation(self, state: AgentState) -> None:
        """Log the observation for debugging/monitoring."""
        log_entry = {
            "timestamp": state["observation_timestamp"],
            "anomaly_id": state["anomaly_id"],
            "severity": state["severity"],
            "should_process": state["should_process"],
            "assessment": state["initial_assessment"],
        }
        print(f"[OBSERVER] {json.dumps(log_entry)}")
    
    def get_stats(self) -> dict:
        """Get observer statistics."""
        return {
            "total_observations": self.observation_count,
            "processed_count": self.processed_count,
            "filter_rate": 1 - (self.processed_count / max(1, self.observation_count)),
        }


# =============================================================================
# LANGGRAPH NODE FUNCTION
# =============================================================================

def observer_node(state: AgentState) -> AgentState:
    """
    LangGraph node function for the Observer Agent.
    
    This is the entry point node in the agent graph.
    It receives raw anomaly data and initializes the workflow state.
    
    Args:
        state: Initial state (may be partially filled)
    
    Returns:
        Updated state with observer's contributions
    """
    # Create observer instance (in production, this could be a singleton)
    observer = ObserverAgent()
    
    # If this is a fresh state, perform observation
    if not state.get("observation_timestamp"):
        # Convert state to anomaly data format
        anomaly_data = {
            "anomaly_id": state.get("anomaly_id", ""),
            "anomaly_type": state.get("anomaly_type", ""),
            "severity": state.get("severity", 1),
            "detected_at": state.get("detected_at", ""),
            "source": state.get("source", ""),
            "description": state.get("description", ""),
            "error_count": state.get("error_count", 0),
            "context": state.get("context", "{}"),
        }
        
        # Perform observation
        new_state = observer.observe(anomaly_data)
        return new_state
    
    # State already observed, just pass through
    state["current_agent"] = "observer"
    return state


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "AgentState",
    "ObserverConfig",
    "ObserverAgent",
    "observer_node",
]
