"""
Planning Agent - Decides response actions based on severity and history.

The Planning Agent takes the reasoning results and determines the
appropriate response strategy. It considers severity, historical patterns,
and available remediation options to create an action plan.

Additionally, when configured, it can leverage OpenAI (gpt-4o-mini)
to refine or propose actions. It will automatically fall back to
deterministic playbooks when LLM confidence is low or unavailable.
"""

import json
import os
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# Import shared state type
from .observer_agent import AgentState


# =============================================================================
# PRIORITY LEVELS
# =============================================================================

class PriorityLevel(str, Enum):
    """Priority levels for incident response."""
    P1_CRITICAL = "P1-CRITICAL"  # Immediate response, all hands
    P2_HIGH = "P2-HIGH"          # Urgent, dedicated responder
    P3_MEDIUM = "P3-MEDIUM"      # Standard response, queue
    P4_LOW = "P4-LOW"            # Best effort, batch
    P5_INFO = "P5-INFO"          # Informational, no action


# =============================================================================
# ACTION TYPES
# =============================================================================

class ActionType(str, Enum):
    """Types of response actions available."""
    ALERT_ONCALL = "alert_oncall"
    NOTIFY_TEAM = "notify_team"
    AUTO_SCALE = "auto_scale"
    RESTART_SERVICE = "restart_service"
    ROLLBACK_DEPLOY = "rollback_deploy"
    ENABLE_CIRCUIT_BREAKER = "enable_circuit_breaker"
    INCREASE_LOGGING = "increase_logging"
    CREATE_TICKET = "create_ticket"
    ESCALATE_MANAGEMENT = "escalate_management"
    NO_ACTION = "no_action"


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class PlanningConfig:
    """Configuration for the Planning Agent."""
    auto_escalate_severity: int = 4
    require_approval_for: List[str] = field(default_factory=lambda: [
        ActionType.ROLLBACK_DEPLOY.value,
        ActionType.RESTART_SERVICE.value,
    ])
    max_actions_per_plan: int = 5
    use_llm: bool = True
    llm_model: str = "gpt-4o-mini"
    llm_base_url: Optional[str] = None  # For Groq: https://api.groq.com/openai/v1
    llm_temperature: float = 0.2
    llm_max_tokens: int = 400
    llm_confidence_threshold: float = 0.6  # below this, use rules
    
    @classmethod
    def from_env(cls) -> "PlanningConfig":
        """Create config from environment variables."""
        return cls(
            auto_escalate_severity=int(os.getenv("AUTO_ESCALATE_SEVERITY", "4")),
            max_actions_per_plan=int(os.getenv("MAX_ACTIONS_PER_PLAN", "5")),
            use_llm=os.getenv("USE_LLM", "true").lower() == "true",
            llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            llm_base_url=os.getenv("LLM_BASE_URL"),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
            llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "400")),
            llm_confidence_threshold=float(os.getenv("PLANNING_CONFIDENCE_THRESHOLD", "0.6")),
        )


# =============================================================================
# ACTION PLAYBOOKS
# =============================================================================

class ActionPlaybook:
    """
    Predefined response playbooks for different anomaly scenarios.
    
    Maps anomaly types and severity levels to recommended actions.
    """
    
    PLAYBOOKS = {
        "error_spike": {
            5: [
                ActionType.ALERT_ONCALL,
                ActionType.ENABLE_CIRCUIT_BREAKER,
                ActionType.INCREASE_LOGGING,
                ActionType.ESCALATE_MANAGEMENT,
            ],
            4: [
                ActionType.ALERT_ONCALL,
                ActionType.ENABLE_CIRCUIT_BREAKER,
                ActionType.INCREASE_LOGGING,
            ],
            3: [
                ActionType.NOTIFY_TEAM,
                ActionType.INCREASE_LOGGING,
                ActionType.CREATE_TICKET,
            ],
            2: [
                ActionType.CREATE_TICKET,
                ActionType.INCREASE_LOGGING,
            ],
            1: [
                ActionType.NO_ACTION,
            ],
        },
        "high_error_rate": {
            5: [
                ActionType.ALERT_ONCALL,
                ActionType.AUTO_SCALE,
                ActionType.ENABLE_CIRCUIT_BREAKER,
                ActionType.ESCALATE_MANAGEMENT,
            ],
            4: [
                ActionType.ALERT_ONCALL,
                ActionType.AUTO_SCALE,
                ActionType.CREATE_TICKET,
            ],
            3: [
                ActionType.NOTIFY_TEAM,
                ActionType.AUTO_SCALE,
                ActionType.CREATE_TICKET,
            ],
            2: [
                ActionType.CREATE_TICKET,
            ],
            1: [
                ActionType.NO_ACTION,
            ],
        },
        "critical_event": {
            5: [
                ActionType.ALERT_ONCALL,
                ActionType.RESTART_SERVICE,
                ActionType.ROLLBACK_DEPLOY,
                ActionType.ESCALATE_MANAGEMENT,
            ],
            4: [
                ActionType.ALERT_ONCALL,
                ActionType.RESTART_SERVICE,
                ActionType.CREATE_TICKET,
            ],
            3: [
                ActionType.ALERT_ONCALL,
                ActionType.CREATE_TICKET,
            ],
            2: [
                ActionType.NOTIFY_TEAM,
                ActionType.CREATE_TICKET,
            ],
            1: [
                ActionType.CREATE_TICKET,
            ],
        },
    }
    
    # Default playbook for unknown anomaly types
    DEFAULT_PLAYBOOK = {
        5: [ActionType.ALERT_ONCALL, ActionType.CREATE_TICKET],
        4: [ActionType.NOTIFY_TEAM, ActionType.CREATE_TICKET],
        3: [ActionType.CREATE_TICKET],
        2: [ActionType.CREATE_TICKET],
        1: [ActionType.NO_ACTION],
    }
    
    @classmethod
    def get_actions(cls, anomaly_type: str, severity: int) -> List[ActionType]:
        """Get recommended actions for an anomaly type and severity."""
        playbook = cls.PLAYBOOKS.get(anomaly_type, cls.DEFAULT_PLAYBOOK)
        # Clamp severity to valid range
        severity = max(1, min(5, severity))
        return playbook.get(severity, [ActionType.NO_ACTION])


# =============================================================================
# SERVICE-SPECIFIC MODIFIERS
# =============================================================================

class ServiceModifier:
    """
    Applies service-specific modifications to action plans.
    
    Different services may require different response strategies.
    """
    
    # Services that require extra caution
    CRITICAL_SERVICES = {
        "payment-service",
        "auth-service",
        "database-proxy",
    }
    
    # Services that can auto-heal
    AUTO_HEAL_SERVICES = {
        "cache-layer",
        "notification-service",
    }
    
    @classmethod
    def modify_plan(
        cls,
        actions: List[ActionType],
        source: str,
        severity: int
    ) -> tuple[List[ActionType], bool]:
        """
        Modify action plan based on service characteristics.
        
        Returns:
            Tuple of (modified actions, escalation_required)
        """
        escalation_required = False
        
        # Critical services always escalate at severity 3+
        if source in cls.CRITICAL_SERVICES and severity >= 3:
            if ActionType.ESCALATE_MANAGEMENT not in actions:
                actions = actions + [ActionType.ESCALATE_MANAGEMENT]
            escalation_required = True
        
        # Auto-heal services can try restart first
        if source in cls.AUTO_HEAL_SERVICES and severity <= 3:
            if ActionType.RESTART_SERVICE not in actions:
                actions = [ActionType.RESTART_SERVICE] + actions
        
        return actions, escalation_required


# =============================================================================
# LLM-ASSISTED PLANNING
# =============================================================================

class LLMPlanner:
    """
    Optional LLM-assisted planner using OpenAI.

    Produces a set of recommended actions and priority label
    based on anomaly context and reasoning outputs.
    """

    PROMPT_TEMPLATE = (
        "You are an SRE planning incident response. Given the anomaly and "
        "reasoning context, propose an action plan and incident priority.\n\n"
        "Return JSON with keys: actions (array of action_type strings "
        "from the known set), priority (one of ['P1-CRITICAL','P2-HIGH',"
        "'P3-MEDIUM','P4-LOW','P5-INFO']). Keep the plan concise.\n\n"
        "Known action types: ['alert_oncall','notify_team','auto_scale',"
        "'restart_service','rollback_deploy','enable_circuit_breaker',"
        "'increase_logging','create_ticket','escalate_management','no_action'].\n\n"
        "Context:\nType: {anomaly_type}\nSeverity: {severity}\nSource: {source}\nRootCause: {root_cause}\nImpact: {impact}\nConfidence: {confidence}\nDescription: {description}\n"
    )

    def __init__(self, config: PlanningConfig):
        self.config = config
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
                kwargs = {"api_key": api_key}
                if self.config.llm_base_url:
                    kwargs["base_url"] = self.config.llm_base_url
                self._client = OpenAI(**kwargs)
            except Exception as e:
                print(f"[PLANNING] Failed to init OpenAI client: {e}")
                return None
        return self._client

    def plan(self, state: AgentState) -> Optional[tuple[List[ActionType], PriorityLevel]]:
        """
        Use LLM to propose actions and priority.

        Returns None on failure to force rule-based fallback.
        """
        if not self.client:
            return None

        prompt = self.PROMPT_TEMPLATE.format(
            anomaly_type=state.get("anomaly_type", "unknown"),
            severity=state.get("severity", 1),
            source=state.get("source", "unknown"),
            root_cause=state.get("root_cause_analysis", ""),
            impact=state.get("impact_assessment", ""),
            confidence=state.get("confidence_score", 0.5),
            description=state.get("description", ""),
        )

        try:
            response = self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=[
                    {"role": "system", "content": "You are a careful SRE planning concrete actions."},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.config.llm_temperature,
                max_tokens=self.config.llm_max_tokens,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            data = json.loads(content)

            # Parse actions
            raw_actions = data.get("actions", [])
            actions: List[ActionType] = []
            for a in raw_actions:
                try:
                    actions.append(ActionType(a))
                except Exception:
                    # Ignore unknown actions suggested by model
                    pass

            # Parse priority
            prio_str = data.get("priority", PriorityLevel.P3_MEDIUM.value)
            try:
                priority = PriorityLevel(prio_str)
            except Exception:
                priority = PriorityLevel.P3_MEDIUM

            if not actions:
                return None

            return actions, priority
        except Exception as e:
            print(f"[PLANNING] LLM planning failed: {e}")
            return None


# =============================================================================
# PLANNING AGENT
# =============================================================================

class PlanningAgent:
    """
    Planning Agent - Creates response action plans.
    
    Responsibilities:
    1. Determine priority level based on severity and context
    2. Select appropriate actions from playbooks
    3. Apply service-specific modifications
    4. Decide on escalation requirements
    """
    
    def __init__(self, config: Optional[PlanningConfig] = None):
        """Initialize the Planning Agent."""
        self.config = config or PlanningConfig.from_env()
        self.plans_created = 0
        self.llm_planner = LLMPlanner(self.config) if self.config.use_llm else None
    
    def plan(self, state: AgentState) -> AgentState:
        """
        Create an action plan based on reasoning results.
        
        Args:
            state: Current agent state from Reasoning
        
        Returns:
            Updated state with planning decisions
        """
        self.plans_created += 1
        
        # Skip if observer decided not to process
        if not state.get("should_process", True):
            state["current_agent"] = "planning"
            state["recommended_actions"] = []
            state["priority_level"] = PriorityLevel.P5_INFO.value
            state["escalation_required"] = False
            return state
        
        severity = state.get("severity", 1)
        anomaly_type = state.get("anomaly_type", "unknown")
        source = state.get("source", "unknown")
        confidence = state.get("confidence_score", 0.5)
        
        # Determine base priority from severity/confidence
        priority = self._determine_priority(severity, confidence)

        # If LLM enabled and confidence high enough, try LLM plan first
        actions: List[ActionType] = []
        if self.llm_planner and confidence >= self.config.llm_confidence_threshold:
            llm_result = self.llm_planner.plan(state)
            if llm_result:
                actions, priority = llm_result

        # Fallback to deterministic playbooks if LLM unavailable/weak
        if not actions:
            actions = ActionPlaybook.get_actions(anomaly_type, severity)
        
        # Apply service-specific modifications
        actions, escalation_required = ServiceModifier.modify_plan(
            actions, source, severity
        )
        
        # Check if auto-escalation threshold met
        if severity >= self.config.auto_escalate_severity:
            escalation_required = True
        
        # Limit number of actions
        actions = actions[:self.config.max_actions_per_plan]
        
        # Convert to string list for state
        action_strings = [a.value for a in actions]
        
        # Update state
        state["current_agent"] = "planning"
        state["recommended_actions"] = action_strings
        state["priority_level"] = priority.value
        state["escalation_required"] = escalation_required
        
        self._log_plan(state)
        
        return state
    
    def _determine_priority(self, severity: int, confidence: float) -> PriorityLevel:
        """Determine incident priority from severity and confidence."""
        # Adjust effective severity by confidence
        effective_severity = severity * confidence
        
        if effective_severity >= 4.5:
            return PriorityLevel.P1_CRITICAL
        elif effective_severity >= 3.5:
            return PriorityLevel.P2_HIGH
        elif effective_severity >= 2.5:
            return PriorityLevel.P3_MEDIUM
        elif effective_severity >= 1.5:
            return PriorityLevel.P4_LOW
        else:
            return PriorityLevel.P5_INFO
    
    def _log_plan(self, state: AgentState) -> None:
        """Log the planning results."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "anomaly_id": state["anomaly_id"],
            "priority": state["priority_level"],
            "actions": state["recommended_actions"],
            "escalation": state["escalation_required"],
        }
        print(f"[PLANNING] {json.dumps(log_entry)}")


# =============================================================================
# LANGGRAPH NODE FUNCTION
# =============================================================================

def planning_node(state: AgentState) -> AgentState:
    """
    LangGraph node function for the Planning Agent.
    
    Args:
        state: Current workflow state from Reasoning
    
    Returns:
        Updated state with action plan
    """
    agent = PlanningAgent()
    return agent.plan(state)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "PriorityLevel",
    "ActionType",
    "PlanningConfig",
    "ActionPlaybook",
    "ServiceModifier",
    "PlanningAgent",
    "planning_node",
]
