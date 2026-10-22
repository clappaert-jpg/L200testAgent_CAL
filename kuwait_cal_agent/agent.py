"""Root ADK `Workflow` Graph and Resumable `App` definition for the Kuwait CAL Agent.

Configured with:
- Strategic Model Routing (`gemini-3.8-flash` for fast extraction, `gemini-3.1-pro`
  for deep reasoning, strategic ideation, and adversarial LLM-as-a-Judge)
- Persistent SQLite `DatabaseSessionService` (`SqliteSessionService`)
- Sliding-window & token-budget `EventsCompactionConfig` (`ContextCompactor`)
- Background `AsyncMemoryConsolidator`
- OpenTelemetry distributed tracing & PII-redacted structured JSON logging
"""

from __future__ import annotations

from ._adk_compat import App, JoinNode, ResumabilityConfig, START, Workflow
from .memory.compaction import EventsCompactionConfig
from .memory.consolidation import AsyncMemoryConsolidator
from .memory.session_store import SqliteSessionService
from .nodes.data_collectors import (
    collect_afa_consumption,
    collect_agenda_and_emails,
    collect_kuwait_innovation_context,
    collect_project_and_gov_docs,
    store_joined_context,
)
from .nodes.deck_builder import build_slides_deck_node
from .nodes.domain_agents import (
    afa_financials_agent,
    innovation_radar_agent,
    pso_risks_agent,
    todo_and_reminders_agent,
)
from .nodes.llm_judge import (
    llm_judge_agent,
    revise_dashboard_agent,
    route_judge_decision,
)
from .nodes.notification_and_hitl import (
    colleague_reminder_consent_gate,
    dispatch_approved_reminders_node,
    send_self_digest_email_node,
)

# Persistent SQLite Session Store & Async Memory Consolidator
session_service = SqliteSessionService()
memory_consolidator = AsyncMemoryConsolidator()
compaction_config = EventsCompactionConfig(
    compaction_interval=4,
    overlap_size=2,
    max_context_tokens=16_000,
)

# JoinNodes synchronizing Stage 1 (Data Ingestion) and Stage 2 (Domain LlmAgents)
join_raw_context = JoinNode(name="join_raw_context")
join_dashboard_payload = JoinNode(name="join_dashboard_payload")

root_agent = Workflow(
    name="kuwait_cal_dashboard_workflow",
    description=(
        "End-to-end Kuwait Consulting Account Lead (CAL) Executive Priority Dashboard "
        "workflow: parallel Workspace ingestion, token-budget context compaction, "
        "4 specialized domain LlmAgents with strategic model routing (gemini-3.8-flash "
        "& gemini-3.1-pro), 6-slide Google Slides generation, LLM-as-a-Judge "
        "self-healing revision loop, automatic self-email notification to "
        "clappaert@google.com, RequestInput Human-in-the-Loop consent gate, and "
        "background async semantic memory consolidation."
    ),
    input_schema=str,
    edges=[
        # Stage 1: Parallel Data Collection Fan-Out & Join
        (
            START,
            (
                collect_agenda_and_emails,
                collect_afa_consumption,
                collect_project_and_gov_docs,
                collect_kuwait_innovation_context,
            ),
        ),
        (
            (
                collect_agenda_and_emails,
                collect_afa_consumption,
                collect_project_and_gov_docs,
                collect_kuwait_innovation_context,
            ),
            join_raw_context,
        ),
        (join_raw_context, store_joined_context),
        # Stage 2: Parallel Domain Synthesis LlmAgents Fan-Out & Join
        (
            store_joined_context,
            (
                todo_and_reminders_agent,
                pso_risks_agent,
                afa_financials_agent,
                innovation_radar_agent,
            ),
        ),
        (
            (
                todo_and_reminders_agent,
                pso_risks_agent,
                afa_financials_agent,
                innovation_radar_agent,
            ),
            join_dashboard_payload,
        ),
        # Stage 3: Build 6-Slide Google Slides Presentation
        (join_dashboard_payload, build_slides_deck_node),
        # Stage 4: Independent LLM-as-a-Judge Audit & Conditional Revision Loop
        (build_slides_deck_node, llm_judge_agent, route_judge_decision),
        (
            route_judge_decision,
            {
                "revise": revise_dashboard_agent,
                "approved": send_self_digest_email_node,
            },
        ),
        (revise_dashboard_agent, build_slides_deck_node),
        # Stage 5: Self-Email Notification + RequestInput Colleague Reminder Consent Gate
        (
            send_self_digest_email_node,
            colleague_reminder_consent_gate,
            dispatch_approved_reminders_node,
        ),
    ],
)

app = App(
    name="kuwait_cal_dashboard_app",
    root_agent=root_agent,
    resumability_config=ResumabilityConfig(is_resumable=True),
    events_compaction_config=compaction_config,
)
