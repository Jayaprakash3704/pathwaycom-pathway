"""
Main Entry Point - Real-Time Streaming Pipeline with Agent Orchestration

Backend-only, continuous system built on Pathway. Uses LangGraph for
agent orchestration and stores all outputs in Pathway tables.

Run with: python main.py
"""

import os
import sys
import json
import signal
import threading
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

# Third-party imports
try:
    import pathway as pw
    from dotenv import load_dotenv
    from langgraph.graph import StateGraph, END
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install -r requirements.txt")
    sys.exit(1)

# Local imports
# NOTE: Pathway-heavy modules are imported lazily inside create_pipeline()
from agents.observer_agent import observer_node, AgentState
from agents.reasoning_agent import reasoning_node
from agents.planning_agent import planning_node
from agents.action_agent import action_node
from agents.memory_agent import memory_node
# NOTE: Pathway incident_store is imported lazily inside create_pipeline()


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class PipelineConfig:
    """Configuration for the streaming pipeline."""
    # Log stream settings
    logs_per_second: float = 5.0
    error_spike_probability: float = 0.15
    
    # Anomaly detection settings
    error_spike_threshold: int = 5
    error_rate_threshold: float = 0.3
    
    # Agent settings
    use_llm: bool = True
    dry_run_actions: bool = False
    
    # Output settings
    output_dir: str = "./output"
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls) -> "PipelineConfig":
        """Create config from environment variables."""
        return cls(
            logs_per_second=float(os.getenv("LOGS_PER_SECOND", "5.0")),
            error_spike_probability=float(os.getenv("ERROR_SPIKE_PROB", "0.15")),
            error_spike_threshold=int(os.getenv("ANOMALY_THRESHOLD", "5")),
            error_rate_threshold=float(os.getenv("ERROR_RATE_THRESHOLD", "0.3")),
            use_llm=os.getenv("USE_LLM", "true").lower() == "true",
            dry_run_actions=os.getenv("DRY_RUN", "false").lower() == "true",
            output_dir=os.getenv("OUTPUT_DIR", "./output"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


# =============================================================================
# AGENT WORKFLOW GRAPH
# =============================================================================

def build_agent_graph():
    """Build LangGraph StateGraph for the 5-agent workflow."""
    graph = StateGraph(AgentState)
    graph.add_node("observer", observer_node)
    graph.add_node("reasoning", reasoning_node)
    graph.add_node("planning", planning_node)
    graph.add_node("action", action_node)
    graph.add_node("memory", memory_node)

    graph.set_entry_point("observer")
    graph.add_edge("observer", "reasoning")
    graph.add_edge("reasoning", "planning")
    graph.add_edge("planning", "action")
    graph.add_edge("action", "memory")
    graph.add_edge("memory", END)

    return graph.compile()


# =============================================================================
# PATHWAY INTEGRATION
# =============================================================================

_compiled_graph = None

def _ensure_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_agent_graph()
    return _compiled_graph


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def create_pipeline(config: PipelineConfig) -> None:
    """
    Create and run the complete streaming pipeline.
    
    This wires together all components:
    1. Log ingestion
    2. Anomaly detection
    3. Agent processing
    4. Incident storage
    """
    print("\n" + "="*60)
    print("  PATHWAY REAL-TIME INCIDENT DETECTION SYSTEM")
    print("="*60)
    print(f"\nConfiguration:")
    print(f"  • Logs/second: {config.logs_per_second}")
    print(f"  • Error spike probability: {config.error_spike_probability}")
    print(f"  • Anomaly threshold: {config.error_spike_threshold}")
    print(f"  • LLM enabled: {config.use_llm}")
    print(f"  • Dry run: {config.dry_run_actions}")
    print("\n" + "="*60 + "\n")
    
    # Create output directory
    os.makedirs(config.output_dir, exist_ok=True)
    
    # ===========================================
    # Lazy import Pathway pipeline modules (avoid import in demo mode)
    from pipelines.log_stream import (
        create_log_stream,
        enrich_log_stream,
    )
    from pipelines.anomaly_detector import (
        create_anomaly_detection_pipeline,
    )
    from state.incident_store import (
        IncidentSchema,
        PathwayIncidentStore,
        agent_state_to_incident_row,
    )

    # STEP 1: Create Log Stream
    # ===========================================
    print("[PIPELINE] Creating log stream...")
    log_stream = create_log_stream(
        logs_per_second=config.logs_per_second,
        error_spike_prob=config.error_spike_probability,
    )
    
    # Enrich logs with computed fields
    enriched_logs = enrich_log_stream(log_stream)
    print("[PIPELINE] Log stream ready ✓")
    
    # ===========================================
    # STEP 2: Create Anomaly Detection Pipeline
    # ===========================================
    print("[PIPELINE] Creating anomaly detector...")
    anomalies = create_anomaly_detection_pipeline(
        enriched_logs,
        error_spike_threshold=config.error_spike_threshold,
        error_rate_threshold=config.error_rate_threshold,
    )
    print("[PIPELINE] Anomaly detector ready ✓")
    
    # ===========================================
    # STEP 3: Process Anomalies Through Agents via LangGraph
    # ===========================================
    print("[PIPELINE] Initializing LangGraph agent workflow...")

    def run_agents(
        anomaly_id: str,
        anomaly_type: str,
        severity: int,
        detected_at: str,
        source: str,
        description: str,
        error_count: int,
        context: str,
    ) -> dict:
        graph = _ensure_graph()
        initial_state: AgentState = {
            "anomaly_id": anomaly_id,
            "anomaly_type": anomaly_type,
            "severity": severity,
            "detected_at": detected_at,
            "source": source,
            "description": description,
            "error_count": error_count,
            "context": context,
        }
        final_state: AgentState = graph.invoke(initial_state)
        return agent_state_to_incident_row(final_state)

    processed = anomalies.select(
        incident=pw.apply(
            run_agents,
            anomalies.anomaly_id,
            anomalies.anomaly_type,
            anomalies.severity,
            anomalies.detected_at,
            anomalies.source,
            anomalies.description,
            anomalies.error_count,
            anomalies.context,
        )
    )

    # Map dict to IncidentSchema columns to form a Pathway table
    incidents = processed.select(
        incident_id=pw.apply(lambda d: d["incident_id"], processed.incident),
        anomaly_id=pw.apply(lambda d: d["anomaly_id"], processed.incident),
        anomaly_type=pw.apply(lambda d: d["anomaly_type"], processed.incident),
        severity=pw.apply(lambda d: d["severity"], processed.incident),
        source=pw.apply(lambda d: d["source"], processed.incident),
        description=pw.apply(lambda d: d["description"], processed.incident),
        detected_at=pw.apply(lambda d: d["detected_at"], processed.incident),
        root_cause=pw.apply(lambda d: d["root_cause"], processed.incident),
        impact=pw.apply(lambda d: d["impact"], processed.incident),
        priority=pw.apply(lambda d: d["priority"], processed.incident),
        actions_taken=pw.apply(lambda d: d["actions_taken"], processed.incident),
        action_status=pw.apply(lambda d: d["action_status"], processed.incident),
        similar_to=pw.apply(lambda d: d["similar_to"], processed.incident),
        tags=pw.apply(lambda d: d["tags"], processed.incident),
        created_at=pw.apply(lambda d: d["created_at"], processed.incident),
    ).with_schema(IncidentSchema)

    # Create store and compute summaries – all in Pathway tables
    store = PathwayIncidentStore()
    incident_table = store.create_from_stream(incidents)
    summaries = store.compute_summaries(incident_table)
    severity_dist = store.compute_severity_distribution(incident_table)
    type_dist = store.compute_type_distribution(incident_table)

    print("[PIPELINE] Agent workflow wired to Pathway tables ✓")
    
    # ===========================================
    # STEP 5: Run the Pipeline
    # ===========================================
    print("\n" + "="*60)
    print("  STARTING REAL-TIME PIPELINE")
    print("  Press Ctrl+C to stop")
    print("="*60 + "\n")
    
    # Run Pathway (continuous)
    pw.run()


# =============================================================================
# DEMO MODE (Without Full Pathway)
# =============================================================================

def run_demo_mode(config: PipelineConfig, duration_seconds: int = 30) -> None:
    """
    Run a demonstration of the agent workflow without Pathway streaming.
    
    Useful for testing agents without full Pathway dependencies.
    
    Args:
        config: Pipeline configuration
        duration_seconds: How long to run the demo
    """
    import time
    
    print("\n" + "="*60)
    print("  DEMO MODE - Agent Workflow Demonstration")
    print("="*60)
    print(f"\nRunning for {duration_seconds} seconds...")
    print("Generating mock logs and anomalies...\n")
    
    # Lightweight mock log generator (no Pathway dependency)
    import random
    from datetime import datetime

    sources = [
        "api-gateway",
        "auth-service",
        "user-service",
        "payment-service",
        "notification-service",
        "database-proxy",
        "cache-layer",
        "load-balancer",
    ]

    def generate_log():
        r = random.random()
        if r < 0.70:
            level = "INFO"
        elif r < 0.90:
            level = "WARNING"
        elif r < 0.98:
            level = "ERROR"
        else:
            level = "CRITICAL"
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": "Synthetic log entry",
            "source": random.choice(sources),
            "request_id": f"req_{random.randint(1,999999):08d}",
        }
    graph = _ensure_graph()
    
    # Counters
    logs_generated = 0
    anomalies_detected = 0
    error_buffer = []
    start_time = time.time()
    
    # Simple anomaly detection logic
    def check_for_anomalies(log: Dict) -> Optional[Dict]:
        """Simple anomaly check for demo."""
        error_buffer.append(log)
        
        # Keep last 10 logs
        if len(error_buffer) > 10:
            error_buffer.pop(0)
        
        # Check for error spike
        errors = [l for l in error_buffer if l["level"] in ("ERROR", "CRITICAL")]
        
        if len(errors) >= 5:
            error_buffer.clear()
            return {
                "anomaly_id": f"DEMO-SPIKE-{anomalies_detected}",
                "anomaly_type": "error_spike",
                "severity": min(5, len(errors)),
                "detected_at": datetime.utcnow().isoformat(),
                "source": errors[-1]["source"],
                "description": f"Error spike: {len(errors)} errors in last 10 logs",
                "error_count": len(errors),
                "context": json.dumps({"error_messages": [e["message"] for e in errors[:3]]}),
            }
        
        # Check for critical event
        if log["level"] == "CRITICAL":
            return {
                "anomaly_id": f"DEMO-CRIT-{anomalies_detected}",
                "anomaly_type": "critical_event",
                "severity": 5,
                "detected_at": datetime.utcnow().isoformat(),
                "source": log["source"],
                "description": f"Critical event: {log['message']}",
                "error_count": 1,
                "context": json.dumps({"message": log["message"]}),
            }
        
        return None
    
    # Main demo loop
    try:
        while time.time() - start_time < duration_seconds:
            # Generate a log
            log = generate_log()
            logs_generated += 1
            
            # Check for anomalies
            anomaly = check_for_anomalies(log)
            
            if anomaly:
                anomalies_detected += 1
                print(f"\n🚨 Anomaly detected! Running agent workflow...")
                final_state = graph.invoke(anomaly)
                print(f"Priority: {final_state.get('priority_level')} | Actions: {len(final_state.get('actions_taken', []))}")
            
            # Rate limiting
            time.sleep(0.2)
            
            # Progress indicator
            if logs_generated % 10 == 0:
                elapsed = int(time.time() - start_time)
                print(f"[DEMO] {elapsed}s elapsed | Logs: {logs_generated} | Anomalies: {anomalies_detected}")
    
    except KeyboardInterrupt:
        print("\n\nDemo stopped by user.")
    
    # Print summary
    print("\n" + "="*60)
    print("  DEMO SUMMARY")
    print("="*60)
    print(f"\nLogs generated: {logs_generated}")
    print(f"Anomalies detected: {anomalies_detected}")
    print(f"\nWorkflow stats:")
    print("  • Workflows executed: (demo mode, not tracked)")
    
    print("\n" + "="*60 + "\n")


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()
    
    # Parse configuration
    config = PipelineConfig.from_env()
    
    # Check for demo mode
    if "--demo" in sys.argv or os.getenv("DEMO_MODE", "false").lower() == "true":
        duration = 30
        for arg in sys.argv:
            if arg.startswith("--duration="):
                duration = int(arg.split("=")[1])
        run_demo_mode(config, duration_seconds=duration)
    else:
        # Run full Pathway pipeline
        try:
            create_pipeline(config)
        except KeyboardInterrupt:
            print("\n\nPipeline stopped by user.")
            print("Shutting down gracefully...")
            sys.exit(0)
        except Exception as e:
            print(f"\n\nPipeline error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
