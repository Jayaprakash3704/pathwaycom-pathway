"""
Action Agent - Executes response actions (simulated).

The Action Agent takes the action plan from Planning and executes
the recommended responses. In this implementation, actions are
simulated but structured for real integration.
"""

import json
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import time

# Import shared state type
from .observer_agent import AgentState
from .planning_agent import ActionType


# =============================================================================
# ACTION STATUS
# =============================================================================

class ActionStatus(str, Enum):
    """Status of action execution."""
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


# =============================================================================
# ACTION RESULT
# =============================================================================

@dataclass
class ActionResult:
    """Result of executing a single action."""
    action_type: str
    status: ActionStatus
    message: str
    timestamp: str
    duration_ms: int = 0
    details: Dict = field(default_factory=dict)


# =============================================================================
# ACTION EXECUTORS (SIMULATED)
# =============================================================================

class ActionExecutors:
    """
    Simulated action executors.
    
    In production, these would integrate with:
    - PagerDuty / Opsgenie for alerts
    - Slack / Teams for notifications
    - Kubernetes for scaling/restarts
    - CI/CD systems for rollbacks
    - Jira / ServiceNow for tickets
    """
    
    @staticmethod
    def alert_oncall(context: Dict) -> ActionResult:
        """Simulate alerting on-call engineer."""
        start = time.time()
        # Simulated alert
        message = f"[SIMULATED] Paging on-call for incident: {context.get('anomaly_id')}"
        duration = int((time.time() - start) * 1000) + 50  # Add simulated latency
        
        return ActionResult(
            action_type=ActionType.ALERT_ONCALL.value,
            status=ActionStatus.SUCCESS,
            message=message,
            timestamp=datetime.utcnow().isoformat(),
            duration_ms=duration,
            details={"channel": "pagerduty", "recipient": "oncall-sre"}
        )
    
    @staticmethod
    def notify_team(context: Dict) -> ActionResult:
        """Simulate team notification."""
        start = time.time()
        severity = context.get('severity', 1)
        channel = "#incidents-p1" if severity >= 4 else "#incidents-general"
        message = f"[SIMULATED] Slack notification sent to {channel}"
        duration = int((time.time() - start) * 1000) + 30
        
        return ActionResult(
            action_type=ActionType.NOTIFY_TEAM.value,
            status=ActionStatus.SUCCESS,
            message=message,
            timestamp=datetime.utcnow().isoformat(),
            duration_ms=duration,
            details={"channel": channel, "platform": "slack"}
        )
    
    @staticmethod
    def auto_scale(context: Dict) -> ActionResult:
        """Simulate auto-scaling service."""
        start = time.time()
        source = context.get('source', 'unknown-service')
        message = f"[SIMULATED] Auto-scale triggered for {source}: +2 replicas"
        duration = int((time.time() - start) * 1000) + 200
        
        return ActionResult(
            action_type=ActionType.AUTO_SCALE.value,
            status=ActionStatus.SUCCESS,
            message=message,
            timestamp=datetime.utcnow().isoformat(),
            duration_ms=duration,
            details={"service": source, "new_replicas": 4, "previous_replicas": 2}
        )
    
    @staticmethod
    def restart_service(context: Dict) -> ActionResult:
        """Simulate service restart."""
        start = time.time()
        source = context.get('source', 'unknown-service')
        message = f"[SIMULATED] Rolling restart initiated for {source}"
        duration = int((time.time() - start) * 1000) + 500
        
        return ActionResult(
            action_type=ActionType.RESTART_SERVICE.value,
            status=ActionStatus.SUCCESS,
            message=message,
            timestamp=datetime.utcnow().isoformat(),
            duration_ms=duration,
            details={"service": source, "strategy": "rolling", "pods_restarted": 3}
        )
    
    @staticmethod
    def rollback_deploy(context: Dict) -> ActionResult:
        """Simulate deployment rollback."""
        start = time.time()
        source = context.get('source', 'unknown-service')
        message = f"[SIMULATED] Rollback initiated for {source} to previous version"
        duration = int((time.time() - start) * 1000) + 1000
        
        return ActionResult(
            action_type=ActionType.ROLLBACK_DEPLOY.value,
            status=ActionStatus.SUCCESS,
            message=message,
            timestamp=datetime.utcnow().isoformat(),
            duration_ms=duration,
            details={"service": source, "from_version": "v2.1.0", "to_version": "v2.0.9"}
        )
    
    @staticmethod
    def enable_circuit_breaker(context: Dict) -> ActionResult:
        """Simulate enabling circuit breaker."""
        start = time.time()
        source = context.get('source', 'unknown-service')
        message = f"[SIMULATED] Circuit breaker enabled for {source}"
        duration = int((time.time() - start) * 1000) + 20
        
        return ActionResult(
            action_type=ActionType.ENABLE_CIRCUIT_BREAKER.value,
            status=ActionStatus.SUCCESS,
            message=message,
            timestamp=datetime.utcnow().isoformat(),
            duration_ms=duration,
            details={"service": source, "threshold": "50%", "timeout": "30s"}
        )
    
    @staticmethod
    def increase_logging(context: Dict) -> ActionResult:
        """Simulate increasing log verbosity."""
        start = time.time()
        source = context.get('source', 'unknown-service')
        message = f"[SIMULATED] Log level increased to DEBUG for {source}"
        duration = int((time.time() - start) * 1000) + 10
        
        return ActionResult(
            action_type=ActionType.INCREASE_LOGGING.value,
            status=ActionStatus.SUCCESS,
            message=message,
            timestamp=datetime.utcnow().isoformat(),
            duration_ms=duration,
            details={"service": source, "previous_level": "INFO", "new_level": "DEBUG"}
        )
    
    @staticmethod
    def create_ticket(context: Dict) -> ActionResult:
        """Simulate creating incident ticket."""
        start = time.time()
        anomaly_id = context.get('anomaly_id', 'unknown')
        ticket_id = f"INC-{anomaly_id[-8:]}"
        message = f"[SIMULATED] Incident ticket created: {ticket_id}"
        duration = int((time.time() - start) * 1000) + 100
        
        return ActionResult(
            action_type=ActionType.CREATE_TICKET.value,
            status=ActionStatus.SUCCESS,
            message=message,
            timestamp=datetime.utcnow().isoformat(),
            duration_ms=duration,
            details={"ticket_id": ticket_id, "system": "jira", "project": "INCIDENTS"}
        )
    
    @staticmethod
    def escalate_management(context: Dict) -> ActionResult:
        """Simulate management escalation."""
        start = time.time()
        severity = context.get('severity', 1)
        message = f"[SIMULATED] Escalated to management: P{6-severity} incident"
        duration = int((time.time() - start) * 1000) + 50
        
        return ActionResult(
            action_type=ActionType.ESCALATE_MANAGEMENT.value,
            status=ActionStatus.SUCCESS,
            message=message,
            timestamp=datetime.utcnow().isoformat(),
            duration_ms=duration,
            details={"notified": ["engineering-manager", "vp-engineering"], "channel": "email"}
        )
    
    @staticmethod
    def no_action(context: Dict) -> ActionResult:
        """No action required."""
        return ActionResult(
            action_type=ActionType.NO_ACTION.value,
            status=ActionStatus.SKIPPED,
            message="No action required for this anomaly",
            timestamp=datetime.utcnow().isoformat(),
            duration_ms=0,
            details={}
        )


# =============================================================================
# ACTION REGISTRY
# =============================================================================

ACTION_REGISTRY: Dict[str, Callable] = {
    ActionType.ALERT_ONCALL.value: ActionExecutors.alert_oncall,
    ActionType.NOTIFY_TEAM.value: ActionExecutors.notify_team,
    ActionType.AUTO_SCALE.value: ActionExecutors.auto_scale,
    ActionType.RESTART_SERVICE.value: ActionExecutors.restart_service,
    ActionType.ROLLBACK_DEPLOY.value: ActionExecutors.rollback_deploy,
    ActionType.ENABLE_CIRCUIT_BREAKER.value: ActionExecutors.enable_circuit_breaker,
    ActionType.INCREASE_LOGGING.value: ActionExecutors.increase_logging,
    ActionType.CREATE_TICKET.value: ActionExecutors.create_ticket,
    ActionType.ESCALATE_MANAGEMENT.value: ActionExecutors.escalate_management,
    ActionType.NO_ACTION.value: ActionExecutors.no_action,
}


# =============================================================================
# ACTION AGENT
# =============================================================================

@dataclass
class ActionConfig:
    """Configuration for the Action Agent."""
    dry_run: bool = False  # If True, log but don't execute
    parallel_execution: bool = False  # Execute actions in parallel
    stop_on_failure: bool = False  # Stop if any action fails


class ActionAgent:
    """
    Action Agent - Executes planned response actions.
    
    Responsibilities:
    1. Execute each action in the plan
    2. Track action results and status
    3. Handle failures gracefully
    4. Log all action outcomes
    """
    
    def __init__(self, config: Optional[ActionConfig] = None):
        """Initialize the Action Agent."""
        self.config = config or ActionConfig()
        self.total_actions_executed = 0
    
    def act(self, state: AgentState) -> AgentState:
        """
        Execute the planned actions.
        
        Args:
            state: Current agent state from Planning
        
        Returns:
            Updated state with action results
        """
        # Skip if not processing
        if not state.get("should_process", True):
            state["current_agent"] = "action"
            state["actions_taken"] = []
            state["action_status"] = ActionStatus.SKIPPED.value
            state["action_timestamp"] = datetime.utcnow().isoformat()
            return state
        
        recommended_actions = state.get("recommended_actions", [])
        
        if not recommended_actions:
            state["current_agent"] = "action"
            state["actions_taken"] = []
            state["action_status"] = ActionStatus.SKIPPED.value
            state["action_timestamp"] = datetime.utcnow().isoformat()
            return state
        
        # Build execution context
        context = {
            "anomaly_id": state.get("anomaly_id"),
            "anomaly_type": state.get("anomaly_type"),
            "severity": state.get("severity"),
            "source": state.get("source"),
            "description": state.get("description"),
            "priority_level": state.get("priority_level"),
        }
        
        # Execute actions
        results = self._execute_actions(recommended_actions, context)
        
        # Summarize results
        actions_taken = [
            f"{r.action_type}: {r.status.value} - {r.message}"
            for r in results
        ]
        
        # Determine overall status
        failed = any(r.status == ActionStatus.FAILED for r in results)
        overall_status = ActionStatus.FAILED if failed else ActionStatus.SUCCESS
        
        # Update state
        state["current_agent"] = "action"
        state["actions_taken"] = actions_taken
        state["action_status"] = overall_status.value
        state["action_timestamp"] = datetime.utcnow().isoformat()
        
        self._log_actions(state, results)
        
        return state
    
    def _execute_actions(
        self,
        actions: List[str],
        context: Dict
    ) -> List[ActionResult]:
        """Execute a list of actions and return results."""
        results = []
        
        for action_type in actions:
            executor = ACTION_REGISTRY.get(action_type)
            
            if executor is None:
                # Unknown action type
                result = ActionResult(
                    action_type=action_type,
                    status=ActionStatus.FAILED,
                    message=f"Unknown action type: {action_type}",
                    timestamp=datetime.utcnow().isoformat(),
                )
            elif self.config.dry_run:
                # Dry run mode - don't actually execute
                result = ActionResult(
                    action_type=action_type,
                    status=ActionStatus.SKIPPED,
                    message=f"[DRY RUN] Would execute: {action_type}",
                    timestamp=datetime.utcnow().isoformat(),
                )
            else:
                try:
                    result = executor(context)
                    self.total_actions_executed += 1
                except Exception as e:
                    result = ActionResult(
                        action_type=action_type,
                        status=ActionStatus.FAILED,
                        message=f"Execution failed: {str(e)}",
                        timestamp=datetime.utcnow().isoformat(),
                    )
            
            results.append(result)
            
            # Stop on failure if configured
            if self.config.stop_on_failure and result.status == ActionStatus.FAILED:
                break
        
        return results
    
    def _log_actions(self, state: AgentState, results: List[ActionResult]) -> None:
        """Log action execution results."""
        log_entry = {
            "timestamp": state["action_timestamp"],
            "anomaly_id": state["anomaly_id"],
            "total_actions": len(results),
            "successful": sum(1 for r in results if r.status == ActionStatus.SUCCESS),
            "failed": sum(1 for r in results if r.status == ActionStatus.FAILED),
            "overall_status": state["action_status"],
        }
        print(f"[ACTION] {json.dumps(log_entry)}")


# =============================================================================
# LANGGRAPH NODE FUNCTION
# =============================================================================

def action_node(state: AgentState) -> AgentState:
    """
    LangGraph node function for the Action Agent.
    
    Args:
        state: Current workflow state from Planning
    
    Returns:
        Updated state with action results
    """
    agent = ActionAgent()
    return agent.act(state)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "ActionStatus",
    "ActionResult",
    "ActionExecutors",
    "ACTION_REGISTRY",
    "ActionConfig",
    "ActionAgent",
    "action_node",
]
