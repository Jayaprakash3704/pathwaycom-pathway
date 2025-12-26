# Pathway Real-Time Incident Response Backend

Backend-only system for continuous log ingestion, anomaly detection, and autonomous incident reasoning/response. Built on Pathway for streaming/state, orchestrated by LangGraph agents, and using LLM-powered analysis (OpenAI, Groq, or compatible providers) with deterministic fallbacks.

— No UI, no prompts, no chat. Pure backend streaming.

> **Interface Layer**: For human oversight, explanations, and incident management, see the companion repository: [pathwaycom-llm-app](https://github.com/Jayaprakash3704/pathwaycom-llm-app)

## Problem Statement

Operational systems generate high-velocity logs. Static threshold monitors either miss emerging issues or spam false positives. During an incident, humans must correlate signals, assess impact, choose actions, and remember outcomes — all under time pressure.

## Why Static Monitoring Falls Short

- Fixed thresholds ignore context and drift.
- No cross-signal reasoning or prioritization.
- Alerts don’t translate into actionable steps.
- Poor memory of what worked previously and why.

## Why Agentic AI Here

We need a continuous loop that observes signals, reasons about root causes, plans actions, executes responses, and remembers outcomes. This is not prompt-chaining; it’s an explicit, stateful workflow with clear responsibilities and deterministic fallbacks.

## Role of Pathway

- Streaming-first: processes events as they arrive.
- Incremental computation: re-computes only what changes.
- Native state tables: incidents and summaries live inside the dataflow.
- Simple Python API backed by a high-performance Rust engine.

## Architecture

```
logs → ingestion → enrichment → anomaly detection → LangGraph agents → incident tables
```

Agents (LangGraph StateGraph):
- Observer: monitors anomaly events and initializes state.
- Reasoning: LLM-based root cause + impact (rule fallback).
- Planning: selects actions and priority (LLM-assisted; rule fallback).
- Action: executes responses (simulated executors only).
- Memory: records outcomes and similarity context.

All outputs are stored in Pathway tables. No files, no Kafka, no UI.

## Repository Layout

```
pipelines/
	log_stream.py          # pw.io.python.read() + enrichment
	anomaly_detector.py    # counts/rates + critical events
agents/
	observer_agent.py      # entrypoint
	reasoning_agent.py     # LLM + rule fallback
	planning_agent.py      # LLM-assisted planning + playbooks
	action_agent.py        # simulated executors
	memory_agent.py        # historical context
state/
	incident_store.py      # Pathway tables + summaries
main.py                  # wires pipeline → agents → tables
requirements.txt
README.md
```

## Run

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Configure environment (copy .env.example to .env)
# Set your LLM provider key:
$env:OPENAI_API_KEY = "sk-..."  # For OpenAI
# OR
$env:GROQ_API_KEY = "gsk-..."   # For Groq

# start the continuous pipeline
python main.py
```

### Configuration via `.env`

**LLM Configuration** (supports OpenAI, Groq, or any OpenAI-compatible API):
- `GROQ_API_KEY` or `OPENAI_API_KEY` - API key for LLM provider
- `LLM_MODEL` - Model name (e.g., `llama-3.3-70b-versatile`, `gpt-4o-mini`)
- `LLM_BASE_URL` - API endpoint (e.g., `https://api.groq.com/openai/v1`)
- `LLM_TEMPERATURE` - Temperature for LLM responses (default: 0.2)
- `USE_LLM` - Enable/disable LLM reasoning (default: true)

**Simulation Parameters**:
- `LOGS_PER_SECOND` - Log generation rate (default: 5.0)
- `ERROR_SPIKE_PROB` - Probability of error spikes (default: 0.1)
- `ANOMALY_THRESHOLD` - Threshold for anomaly detection (default: 5)
- `ERROR_RATE_THRESHOLD` - Error rate trigger (default: 0.3)

**Other Settings**:
- `DRY_RUN` - Simulate without taking actions (default: false)
- `OUTPUT_DIR` - Directory for outputs (demo only)

## Behavior

1. Simulated logs stream via `pw.io.python.read()`.
2. Deterministic anomaly detection (error spikes, high error rates, critical events).
3. LangGraph orchestrates `observe → reason → plan → act → remember`.
4. Reasoning and planning use OpenAI when confidence permits; rule-based fallback otherwise.
5. Incidents are persisted in Pathway tables with summaries for real-time querying.

## What This Demonstrates

- Real-time streaming (not batch).
- Explicit multi-agent orchestration (not prompt chaining).
- Stateful memory outside the LLM.
- Clean separation of concerns and production-style layout.

## Integration with Interface Layer

This backend generates incident data that can be consumed by the interface layer in multiple ways:

**Demo Mode** (current):
- Writes to `./storage/incidents.json` and `./storage/summaries.json`
- Interface layer reads these files

**Production Options**:
1. **Pathway REST Connector**: Expose `pw.io.http.rest_connector()` for real-time queries
2. **Database Output**: Write to PostgreSQL/MongoDB using `pw.io.postgres.write()`
3. **Message Queue**: Publish events via `pw.io.kafka.write()`
4. **WebSocket Streaming**: Real-time incident stream to interface

See the interface repository for query and override capabilities: [pathwaycom-llm-app](https://github.com/Jayaprakash3704/pathwaycom-llm-app)

---

## Notes

- **LLM Providers**: Supports OpenAI, Groq, or any OpenAI-compatible API via base URL configuration
- **Agent Fallbacks**: When LLM confidence is low, agents use deterministic rule-based logic
- **Action Executors**: Currently simulated. Replace with real integrations (PagerDuty, Slack, Kubernetes) in production
- **Similarity Memory**: In-process store for context; authoritative incident state is in Pathway tables
- **Windows Compatibility**: Pathway uses stub mode on Windows; full streaming available on Linux/macOS

---

## Related Repositories

- **Interface Layer (Human Oversight)**: [pathwaycom-llm-app](https://github.com/Jayaprakash3704/pathwaycom-llm-app) - REST API, dashboard, explanations, manual overrides

---

## 🏆 For Hackathon Judges

This project is our **Track 1: Agentic AI** submission.

**Key Highlights**:
- ✅ Real-time streaming with Pathway Engine (not batch processing)
- ✅ 5-agent system using LangGraph (explicit orchestration, not prompt chaining)
- ✅ LLM-powered reasoning with deterministic fallbacks
- ✅ Production-ready architecture with human oversight layer
- ✅ Solves real operational problem ($500K/year monitoring costs)

**Documentation**:
- **Hackathon Pitch**: See [HACKATHON.md](HACKATHON.md) for complete submission details
- **Demo Script**: See [DEMO.md](DEMO.md) for 5-minute walkthrough
- **Architecture**: Pathway streaming → Anomaly detection → LangGraph agents → Incident tables

**What Makes This Production-Ready**:
1. Separated backend (autonomous agents) from interface (human controls)
2. Full audit trail for compliance (GDPR, SOC 2)
3. LLM-agnostic (works with OpenAI, Groq, Azure, or local models)
4. Deterministic fallbacks when LLM confidence is low
5. Comprehensive error handling and logging

**Quick Start**: `python main.py` (see demo in 60 seconds)

---

## References

- **Pathway Docs**: https://pathway.com/docs/
- **LangGraph Docs**: https://langchain-ai.github.io/langgraph/
- **Groq API**: https://console.groq.com/
- **OpenAI API**: https://platform.openai.com/docs/
