# Pathway Real-Time Incident Response Backend

Backend-only system for continuous log ingestion, anomaly detection, and autonomous incident reasoning/response. Built on Pathway for streaming/state, orchestrated by LangGraph agents, and using OpenAI (`gpt-4o-mini`) for analysis and planning with deterministic fallbacks.

— No UI, no prompts, no chat. Pure backend streaming.

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

# set your key
$env:OPENAI_API_KEY = "sk-..."

# start the continuous pipeline
python main.py
```

Configuration via `.env` (optional):

- `LOGS_PER_SECOND`, `ERROR_SPIKE_PROB`, `ANOMALY_THRESHOLD`, `ERROR_RATE_THRESHOLD`
- `USE_LLM`, `DRY_RUN`, `OUTPUT_DIR` (used only for local dev; no file sinks are configured)

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

## Notes

- Action executors are simulated. Replace with integrations (PagerDuty, Slack, Kubernetes) in production.
- Similarity memory uses an in-process store for scoring; authoritative incident state is in Pathway tables.

## References

- Pathway Docs: https://pathway.com/docs/
- LangGraph Docs: https://langchain-ai.github.io/langgraph/
