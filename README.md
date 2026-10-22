# Kuwait CAL Executive Priority Dashboard Agent (Python ADK 2.x)

Automated multi-agent system built in **Google Agent Development Kit (`google-adk` 2.x)** for the Google Cloud Consulting Account Lead (CAL) in Kuwait. Runs every **Sunday at 06:00 AM (`Asia/Kuwait`)** to synthesize Google Calendar, Gmail, Gemini Meet Notes, and AFA/TIF/PSF consumption trackers into a **6-slide Google Slides executive presentation**, audits the deck via an independent **LLM-as-a-Judge** self-healing loop, and emails the verified presentation link to `clappaert@google.com`.

---

## Architecture & L200 Engineering Capabilities

1. **Multi-Agent Orchestration & Strategic Model Routing (`kuwait_cal_agent/model_routing.py`, `kuwait_cal_agent/agent.py`)**
   - Uses ADK 2.x graph-based `Workflow` and `JoinNode` barriers for parallel Stage-1 data collection and parallel Stage-2 domain synthesis.
   - **Tier 1 — Fast Structured Extraction (`gemini-3.8-flash`)**: Assigned to `todo_and_reminders_agent` and `afa_financials_agent` for low-latency tabular and action extraction.
   - **Tier 2 — Deep Reasoning & Strategic Synthesis (`gemini-3.1-pro` with `ThinkingConfig`)**: Assigned to `pso_risks_agent` (cross-channel sovereign cloud risk correlation) and `innovation_radar_agent` (New Kuwait Vision 2035 & 3-Layer National AI Factory ideation).
   - **Tier 3 — Adversarial Judge & Self-Healing (`gemini-3.1-pro` with extended `thinking_budget=8192`)**: Assigned to `llm_judge_agent` and `revise_dashboard_agent`.
   - **Dynamic Escalation**: `ModelRouter.select_model()` automatically escalates any `gemini-3.8-flash` task to `gemini-3.1-pro` when `retry_iteration > 0` or input token complexity exceeds `32,000` tokens.

2. **Persistent SQLite Session Store, Context Compaction & Async Memory Consolidation (`kuwait_cal_agent/memory/`)**
   - **Persistent Session Database (`session_store.py`)**: `SqliteSessionService` / `DatabaseSessionService` persists all session state, event journals (`session_events`), and resumable workflow checkpoints (`workflow_checkpoints`) in SQLite (`WAL` mode) rather than volatile in-memory dictionaries.
   - **Context & Event History Compaction (`compaction.py`)**: `ContextCompactor` and `EventsCompactionConfig` enforce token-budget compaction over verbose workspace payloads while preserving high-signal anchors (financial figures, dates, RAG statuses, project names) and compacting multi-step event histories.
   - **Background Asynchronous Memory Consolidation (`consolidation.py`)**: `AsyncMemoryConsolidator` runs non-blockingly via `asyncio.create_task()` at workflow completion to extract episodic facts into long-term `semantic_memories` (preventing weekly duplicate Kuwait Vision 2035 ideas and tracking longitudinal PSO risk and AFA burn velocity).

3. **Observability, OpenTelemetry Distributed Tracing & PII Redaction (`kuwait_cal_agent/observability/`)**
   - **Structured JSON Logging (`logging.py`)**: All components emit structured single-line JSON logs with explicit `INTENT` (`log_intent`) and `OUTCOME` (`log_outcome`) capture, correlated with active OpenTelemetry `trace_id` and `span_id`.
   - **Distributed Tracing (`telemetry.py`)**: OpenTelemetry `TracerProvider` and `@traced_node` / `@traced_tool` decorators record hierarchical spans across the workflow DAG with `gen_ai.request.model`, `adk.intent`, `adk.outcome`, and latency metrics.
   - **Automated PII Redaction (`pii_redactor.py`)**: `PiiRedactor` and `PiiRedactingFilter` scrub emails (`c***@google.com`), 12-digit Kuwait Civil IDs, phone numbers, and OAuth/API tokens from all logs and OpenTelemetry span attributes before emission.

4. **Resilient Tool & Interface Design (`kuwait_cal_agent/tools/`)**
   - Explicit ADK `FunctionToolWrapper` declarations with strict parameter validation.
   - Exponential backoff with jitter (`@retry_with_backoff`) protecting against transient `503 UNAVAILABLE` and `429 RESOURCE_EXHAUSTED` errors.
   - Cryptographic idempotency ledger (`GLOBAL_IDEMPOTENCY_LEDGER`) preventing duplicate email sends or slide mutations across retries.
   - Hard security guardrails: self-digest email is locked to `clappaert@google.com`, and colleague 2–5 day SLA reminders require explicit human consent (`user_consent_verified=True`) via ADK `RequestInput`.

5. **Golden Dataset Evaluation Harness & Terraform IaC (`evals/`, `infra/terraform/`)**
   - **Golden Dataset & Regression Harness (`evals/golden_dataset.json`, `evals/run_eval.py`)**: Automated evaluation suite testing nominal execution, LLM-as-a-Judge self-healing loops, HITL `RequestInput` pause/resume, strategic model routing (`gemini-3.8-flash` / `gemini-3.1-pro`), OpenTelemetry spans, PII redaction, and persistent memory consolidation (`--min-score 0.95`).
   - **Terraform IaC (`infra/terraform/`)**: Provisions Cloud Run v2 service, Cloud Scheduler (`0 6 * * 0` in `Asia/Kuwait`), Secret Manager, and least-privilege Service Account IAM bindings.

---

## Quick Start

```bash
# 1. Run unit & integration test suite
python3 -m unittest discover -s tests -v

# 2. Run the Golden Dataset Regression Evaluation Harness
python3 evals/run_eval.py --min-score 0.95

# 3. Execute a Sunday 6:00 AM dry-run
python3 run_sunday_dashboard.py --once --dry-run
```
