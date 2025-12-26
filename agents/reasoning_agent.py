"""
Reasoning Agent - Interprets anomaly context using LLM.

The Reasoning Agent analyzes anomalies to understand root causes,
assess impact, and provide insights for decision-making. Uses LLM
for natural language reasoning about complex system behaviors.
"""

import os
import json
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

# Import shared state type
from .observer_agent import AgentState


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class ReasoningConfig:
    """Configuration for the Reasoning Agent."""
    use_llm: bool = True
    llm_model: str = "gpt-4o-mini"
    llm_base_url: Optional[str] = None  # For Groq: https://api.groq.com/openai/v1
    temperature: float = 0.3
    max_tokens: int = 500
    fallback_to_rules: bool = True
    
    @classmethod
    def from_env(cls) -> "ReasoningConfig":
        """Create config from environment variables."""
        return cls(
            use_llm=os.getenv("USE_LLM", "true").lower() == "true",
            llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            llm_base_url=os.getenv("LLM_BASE_URL"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "500")),
            fallback_to_rules=True,
        )


# =============================================================================
# REASONING TEMPLATES
# =============================================================================

ANALYSIS_PROMPT_TEMPLATE = """You are an expert Site Reliability Engineer (SRE) analyzing a system anomaly.

ANOMALY DETAILS:
- Type: {anomaly_type}
- Severity: {severity}/5
- Source: {source}
- Description: {description}
- Error Count: {error_count}
- Initial Assessment: {initial_assessment}
- Context: {context}

Based on this information, provide:
1. ROOT CAUSE ANALYSIS: What is the most likely cause of this anomaly?
2. IMPACT ASSESSMENT: What systems/users might be affected?
3. CONFIDENCE SCORE: How confident are you in this analysis (0.0-1.0)?

Respond in JSON format:
{{
    "root_cause_analysis": "...",
    "impact_assessment": "...",
    "confidence_score": 0.X
}}
"""


# =============================================================================
# RULE-BASED REASONING (FALLBACK)
# =============================================================================

class RuleBasedReasoner:
    """
    Rule-based reasoning engine for when LLM is unavailable.
    
    Provides deterministic analysis based on anomaly patterns.
    """
    
    # Knowledge base of common patterns
    PATTERNS = {
        "error_spike": {
            "causes": [
                "Sudden traffic spike overwhelming service capacity",
                "Deployment of buggy code",
                "External dependency failure",
                "Database connection pool exhaustion",
            ],
            "impacts": [
                "Degraded user experience",
                "Increased latency for all requests",
                "Potential data inconsistency",
            ],
        },
        "high_error_rate": {
            "causes": [
                "Persistent configuration issue",
                "Resource exhaustion (memory, CPU, connections)",
                "Cascading failure from upstream service",
                "Data corruption or schema mismatch",
            ],
            "impacts": [
                "Service partially unavailable",
                "Business transactions failing",
                "Customer complaints likely",
            ],
        },
        "critical_event": {
            "causes": [
                "System crash or unhandled exception",
                "Security incident or breach attempt",
                "Complete service failure",
                "Infrastructure issue (disk, network, hardware)",
            ],
            "impacts": [
                "Service completely unavailable",
                "Potential data loss",
                "Immediate customer impact",
                "SLA breach likely",
            ],
        },
    }
    
    # Service-specific knowledge
    SERVICE_HINTS = {
        "api-gateway": "Entry point for all requests - impact is widespread",
        "auth-service": "Authentication failures affect all authenticated operations",
        "user-service": "User data operations impacted",
        "payment-service": "Financial transactions at risk - high priority",
        "notification-service": "User communications delayed or lost",
        "database-proxy": "Database access impacted across multiple services",
        "cache-layer": "Increased database load, higher latency",
        "load-balancer": "Traffic distribution affected, possible outage",
    }
    
    def analyze(self, state: AgentState) -> dict:
        """
        Perform rule-based analysis of the anomaly.
        
        Args:
            state: Current agent state with anomaly details
        
        Returns:
            Analysis results dictionary
        """
        anomaly_type = state.get("anomaly_type", "unknown")
        source = state.get("source", "unknown")
        severity = state.get("severity", 1)
        error_count = state.get("error_count", 0)
        
        # Get pattern-specific analysis
        pattern = self.PATTERNS.get(anomaly_type, {
            "causes": ["Unknown anomaly pattern - manual investigation required"],
            "impacts": ["Impact unclear - monitor closely"],
        })
        
        # Select most likely cause based on context
        cause_index = min(severity - 1, len(pattern["causes"]) - 1)
        primary_cause = pattern["causes"][max(0, cause_index)]
        
        # Get service-specific hint
        service_hint = self.SERVICE_HINTS.get(source, "Standard service impact")
        
        # Build root cause analysis
        root_cause = f"{primary_cause}. {service_hint}."
        
        # Build impact assessment
        impact_parts = pattern["impacts"][:min(severity, len(pattern["impacts"]))]
        impact = ". ".join(impact_parts) + "."
        
        # Calculate confidence based on specificity
        confidence = 0.6  # Base confidence for rule-based
        if anomaly_type in self.PATTERNS:
            confidence += 0.1
        if source in self.SERVICE_HINTS:
            confidence += 0.1
        if error_count > 10:
            confidence += 0.1  # More data = more confidence
        
        confidence = min(0.9, confidence)  # Cap at 0.9 for rule-based
        
        return {
            "root_cause_analysis": root_cause,
            "impact_assessment": impact,
            "confidence_score": confidence,
        }


# =============================================================================
# LLM-BASED REASONING
# =============================================================================

class LLMReasoner:
    """
    LLM-powered reasoning engine using OpenAI.
    
    Provides sophisticated natural language analysis of anomalies.
    """
    
    def __init__(self, config: ReasoningConfig):
        """Initialize the LLM reasoner."""
        self.config = config
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
                kwargs = {"api_key": api_key}
                if self.config.llm_base_url:
                    kwargs["base_url"] = self.config.llm_base_url
                self._client = OpenAI(**kwargs)
            except Exception as e:
                print(f"[REASONING] Failed to initialize OpenAI client: {e}")
                return None
        return self._client
    
    def analyze(self, state: AgentState) -> Optional[dict]:
        """
        Perform LLM-based analysis of the anomaly.
        
        Args:
            state: Current agent state with anomaly details
        
        Returns:
            Analysis results dictionary or None if failed
        """
        if not self.client:
            return None
        
        # Build the prompt
        prompt = ANALYSIS_PROMPT_TEMPLATE.format(
            anomaly_type=state.get("anomaly_type", "unknown"),
            severity=state.get("severity", 1),
            source=state.get("source", "unknown"),
            description=state.get("description", ""),
            error_count=state.get("error_count", 0),
            initial_assessment=state.get("initial_assessment", ""),
            context=state.get("context", "{}"),
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=[
                    {"role": "system", "content": "You are an expert SRE analyzing system anomalies."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                response_format={"type": "json_object"},
            )
            
            # Parse the response
            content = response.choices[0].message.content
            result = json.loads(content)
            
            # Validate and normalize
            return {
                "root_cause_analysis": result.get("root_cause_analysis", "Analysis unavailable"),
                "impact_assessment": result.get("impact_assessment", "Impact unknown"),
                "confidence_score": float(result.get("confidence_score", 0.5)),
            }
            
        except Exception as e:
            print(f"[REASONING] LLM analysis failed: {e}")
            return None


# =============================================================================
# REASONING AGENT
# =============================================================================

class ReasoningAgent:
    """
    Reasoning Agent - Analyzes anomalies using LLM or rule-based reasoning.
    
    Responsibilities:
    1. Analyze anomaly context for root cause
    2. Assess potential impact on systems/users
    3. Provide confidence score for the analysis
    """
    
    def __init__(self, config: Optional[ReasoningConfig] = None):
        """Initialize the Reasoning Agent."""
        self.config = config or ReasoningConfig.from_env()
        self.llm_reasoner = LLMReasoner(self.config) if self.config.use_llm else None
        self.rule_reasoner = RuleBasedReasoner()
        self.analysis_count = 0
    
    def reason(self, state: AgentState) -> AgentState:
        """
        Analyze the anomaly and update state with reasoning results.
        
        Args:
            state: Current agent state from Observer
        
        Returns:
            Updated state with reasoning results
        """
        self.analysis_count += 1
        
        # Skip processing if observer decided not to
        if not state.get("should_process", True):
            state["current_agent"] = "reasoning"
            state["root_cause_analysis"] = "Skipped - low priority anomaly"
            state["impact_assessment"] = "Minimal impact expected"
            state["confidence_score"] = 0.9
            return state
        
        # Try LLM-based reasoning first
        analysis = None
        if self.config.use_llm and self.llm_reasoner:
            analysis = self.llm_reasoner.analyze(state)
        
        # Fall back to rule-based if LLM fails
        if analysis is None and self.config.fallback_to_rules:
            analysis = self.rule_reasoner.analyze(state)
        
        # If all else fails, provide minimal analysis
        if analysis is None:
            analysis = {
                "root_cause_analysis": "Unable to determine root cause - manual investigation required",
                "impact_assessment": "Impact assessment unavailable",
                "confidence_score": 0.1,
            }
        
        # Update state
        state["current_agent"] = "reasoning"
        state["root_cause_analysis"] = analysis["root_cause_analysis"]
        state["impact_assessment"] = analysis["impact_assessment"]
        state["confidence_score"] = analysis["confidence_score"]
        
        self._log_reasoning(state)
        
        return state
    
    def _log_reasoning(self, state: AgentState) -> None:
        """Log the reasoning results."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "anomaly_id": state["anomaly_id"],
            "root_cause": state["root_cause_analysis"][:100] + "...",
            "confidence": state["confidence_score"],
        }
        print(f"[REASONING] {json.dumps(log_entry)}")


# =============================================================================
# LANGGRAPH NODE FUNCTION
# =============================================================================

def reasoning_node(state: AgentState) -> AgentState:
    """
    LangGraph node function for the Reasoning Agent.
    
    Args:
        state: Current workflow state from Observer
    
    Returns:
        Updated state with reasoning results
    """
    agent = ReasoningAgent()
    return agent.reason(state)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "ReasoningConfig",
    "RuleBasedReasoner",
    "LLMReasoner",
    "ReasoningAgent",
    "reasoning_node",
]
