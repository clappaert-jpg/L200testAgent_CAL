"""Unit & Workflow Integration Tests for the Kuwait CAL ADK Agent.

Compatible with both `pytest` (`pytest tests/`) and `python3 -m unittest discover -s tests`.
Verifies:
1. Parallel Fan-Out & `JoinNode` Synchronization across Stage 1 & Stage 2.
2. Strategic Model Routing (`gemini-3.8-flash` for fast extraction, `gemini-3.1-pro` for deep reasoning & judge, plus dynamic escalation).
3. Persistent SQLite `DatabaseSessionService`, `ContextCompactor`, and background `AsyncMemoryConsolidator`.
4. OpenTelemetry distributed tracing spans, structured JSON `INTENT`/`OUTCOME` logs, and `PiiRedactor`.
5. LLM-as-a-Judge Conditional Revision Loop (`'revise'` -> `revise_dashboard_agent` -> `'approved'`).
6. Interactive Human-in-the-Loop (`RequestInput`) pause & resume and hard email guardrails.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from kuwait_cal_agent._adk_compat import DatabaseSessionService, InMemoryRunner, genai_types
from kuwait_cal_agent.agent import app, memory_consolidator, root_agent
from kuwait_cal_agent.memory.compaction import ContextCompactor
from kuwait_cal_agent.memory.consolidation import AsyncMemoryConsolidator
from kuwait_cal_agent.memory.session_store import SqliteSessionService
from kuwait_cal_agent.model_routing import FLASH_MODEL, ModelRouter, ModelTier, PRO_MODEL
from kuwait_cal_agent.observability.logging import (
    clear_captured_json_logs,
    get_captured_json_logs,
)
from kuwait_cal_agent.observability.pii_redactor import scrub_pii
from kuwait_cal_agent.observability.telemetry import (
    clear_recorded_spans,
    get_recorded_spans,
)
from kuwait_cal_agent.tools.gmail_sender import (
    send_dashboard_digest_to_willem,
    stage_or_send_colleague_reminder,
)
from kuwait_cal_agent.tools.resilience import GLOBAL_IDEMPOTENCY_LEDGER
from kuwait_cal_agent.tools.slides_renderer import build_six_slide_batch_ops


def node_name(event) -> str | None:
  """Extracts the short node name from `event.node_info.path` ('workflow@1/step@1' -> 'step')."""
  if not getattr(event, "node_info", None):
    return None
  return event.node_info.path.split("/")[-1].split("@")[0]


class KuwaitCalAdkWorkflowTests(unittest.IsolatedAsyncioTestCase):
  """Tests the 5-stage ADK Workflow graph, strategic model routing, memory, OTel, and HITL guardrails."""

  def setUp(self) -> None:
    super().setUp()
    os.environ["CAL_AGENT_DRY_RUN"] = "1"
    GLOBAL_IDEMPOTENCY_LEDGER.clear()
    clear_captured_json_logs()
    clear_recorded_spans()
    self._tmp_dir = tempfile.TemporaryDirectory(prefix="cal_test_db_")
    self.db_path = str(Path(self._tmp_dir.name) / "test_sessions.db")

  def tearDown(self) -> None:
    self._tmp_dir.cleanup()
    super().tearDown()

  async def test_unattended_sunday_6am_workflow_run(self) -> None:
    """Verifies full unattended Sunday 6am run: fan-out, join, slides, judge, self-email, OTel, and SQLite state."""
    runner = InMemoryRunner(
        app=app, session_service=DatabaseSessionService(db_path=self.db_path)
    )
    session = await runner.session_service.create_session(
        app_name=app.name,
        user_id="clappaert",
        state={"unattended_schedule": True},
    )
    msg = genai_types.Content(
        role="user",
        parts=[genai_types.Part.from_text(text="Run Sunday 6am dashboard")],
    )
    events = [
        e
        async for e in runner.run_async(
            user_id="clappaert", session_id=session.id, new_message=msg
        )
    ]
    await memory_consolidator.wait_for_pending_tasks()
    visited = [node_name(e) for e in events if node_name(e)]

    # Stage 1 collectors and join
    self.assertIn("collect_agenda_and_emails", visited)
    self.assertIn("collect_afa_consumption", visited)
    self.assertIn("collect_project_and_gov_docs", visited)
    self.assertIn("collect_kuwait_innovation_context", visited)
    self.assertIn("join_raw_context", visited)

    # Stage 2 domain LlmAgents and join
    self.assertIn("todo_and_reminders_agent", visited)
    self.assertIn("pso_risks_agent", visited)
    self.assertIn("afa_financials_agent", visited)
    self.assertIn("innovation_radar_agent", visited)
    self.assertIn("join_dashboard_payload", visited)

    # Stage 3, 4, 5
    self.assertIn("build_slides_deck_node", visited)
    self.assertIn("llm_judge_agent", visited)
    self.assertIn("send_self_digest_email_node", visited)
    self.assertIn("dispatch_approved_reminders_node", visited)

    after = await runner.session_service.get_session(
        app_name=app.name, user_id="clappaert", session_id=session.id
    )
    payload = after.state["dashboard_payload"]
    self.assertEqual(len(payload["todo_and_reminders"]["todos"]), 10)
    self.assertEqual(len(payload["innovation_radar"]["ideas"]), 3)
    self.assertEqual(after.state["self_email_result"]["to"], "clappaert@google.com")
    self.assertEqual(after.state["colleague_emails_sent"], 0)
    self.assertIn("compaction_metrics", after.state)
    self.assertIn("event_history_compaction", after.state)

    # Verify OpenTelemetry spans and structured JSON logs were recorded
    spans = get_recorded_spans()
    logs = get_captured_json_logs()
    self.assertGreaterEqual(len(spans), 10)
    self.assertTrue(any(l.get("event_type") == "INTENT" for l in logs))
    self.assertTrue(any(l.get("event_type") == "OUTCOME" for l in logs))

  async def test_llm_judge_self_healing_revision_loop(self) -> None:
    """Verifies that a failed first-pass Judge score routes to `revise_dashboard_agent` (`gemini-3.1-pro`) and loops."""
    runner = InMemoryRunner(
        agent=root_agent,
        app_name="test_judge_loop",
        session_service=DatabaseSessionService(db_path=self.db_path),
    )
    session = await runner.session_service.create_session(
        app_name="test_judge_loop",
        user_id="clappaert",
        state={"unattended_schedule": True, "force_judge_fail_once": True},
    )
    msg = genai_types.Content(
        role="user",
        parts=[genai_types.Part.from_text(text="Test judge revision loop")],
    )
    events = [
        e
        async for e in runner.run_async(
            user_id="clappaert", session_id=session.id, new_message=msg
        )
    ]
    visited = [node_name(e) for e in events if node_name(e)]

    self.assertIn("revise_dashboard_agent", visited)
    self.assertEqual(visited.count("build_slides_deck_node"), 2)
    self.assertEqual(visited.count("llm_judge_agent"), 2)

    after = await runner.session_service.get_session(
        app_name="test_judge_loop", user_id="clappaert", session_id=session.id
    )
    self.assertEqual(after.state["judge_revision_count"], 1)
    self.assertEqual(after.state["active_revision_model"], "gemini-3.1-pro")
    self.assertTrue(after.state["judge_evaluation"]["passed"])

  async def test_hitl_pause_and_resume_for_colleague_reminders(self) -> None:
    """Verifies interactive `RequestInput` pause and resume for colleague reminder approval."""
    runner = InMemoryRunner(
        app=app, session_service=DatabaseSessionService(db_path=self.db_path)
    )
    session = await runner.session_service.create_session(
        app_name=app.name,
        user_id="clappaert",
        state={"unattended_schedule": False},
    )
    msg = genai_types.Content(
        role="user",
        parts=[genai_types.Part.from_text(text="Run interactive dashboard")],
    )
    paused_events = [
        e
        async for e in runner.run_async(
            user_id="clappaert", session_id=session.id, new_message=msg
        )
    ]
    fc_events = [e for e in paused_events if e.get_function_calls()]
    self.assertTrue(fc_events, "Expected an `adk_request_input` interrupt event")
    fc = fc_events[-1].get_function_calls()[0]
    self.assertEqual(fc.name, "adk_request_input")

    approval_decision = {
        "approved_colleague_emails": ["ehsanr@google.com", "ljammal@google.com"],
        "delivery_mode": "create_draft",
    }
    resume_msg = genai_types.Content(
        role="user",
        parts=[
            genai_types.Part(
                function_response=genai_types.FunctionResponse(
                    id=fc.id,
                    name=fc.name,
                    response={"result": approval_decision},
                )
            )
        ],
    )
    resumed_events = [
        e
        async for e in runner.run_async(
            user_id="clappaert", session_id=session.id, new_message=resume_msg
        )
    ]
    final_events = [
        e
        for e in resumed_events
        if node_name(e) == "dispatch_approved_reminders_node" and e.output
    ]
    self.assertTrue(final_events)
    self.assertEqual(final_events[-1].output["approved_count"], 2)
    self.assertEqual(final_events[-1].output["delivery_mode"], "create_draft")

  def test_strategic_model_routing_and_dynamic_escalation(self) -> None:
    """Verifies gemini-3.8-flash and gemini-3.1-pro assignment and dynamic escalation."""
    self.assertEqual(FLASH_MODEL, "gemini-3.8-flash")
    self.assertEqual(PRO_MODEL, "gemini-3.1-pro")

    todo_route = ModelRouter.select_model("todo_and_reminders_agent")
    afa_route = ModelRouter.select_model("afa_financials_agent")
    pso_route = ModelRouter.select_model("pso_risks_agent")
    innov_route = ModelRouter.select_model("innovation_radar_agent")
    judge_route = ModelRouter.select_model("llm_judge_agent")

    self.assertEqual(todo_route.selected_model, "gemini-3.8-flash")
    self.assertEqual(todo_route.tier, ModelTier.FAST_EXTRACTION)
    self.assertEqual(afa_route.selected_model, "gemini-3.8-flash")
    self.assertEqual(pso_route.selected_model, "gemini-3.1-pro")
    self.assertEqual(pso_route.tier, ModelTier.DEEP_REASONING)
    self.assertEqual(innov_route.selected_model, "gemini-3.1-pro")
    self.assertEqual(judge_route.selected_model, "gemini-3.1-pro")
    self.assertEqual(judge_route.tier, ModelTier.ADVERSARIAL_JUDGE)

    # Dynamic escalation from gemini-3.8-flash to gemini-3.1-pro on retry or token spike
    escalated = ModelRouter.select_model(
        "todo_and_reminders_agent", retry_iteration=1
    )
    self.assertEqual(escalated.selected_model, "gemini-3.1-pro")
    self.assertTrue(escalated.escalated)

  async def test_sqlite_persistence_compaction_and_pii_redaction(self) -> None:
    """Verifies SQLite session durability, context compaction, async memory consolidation, and PII scrubbing."""
    store = SqliteSessionService(db_path=self.db_path)
    store.create_or_load_session("sess_01", initial_state={"k1": "v1"})
    store.update_session_state("sess_01", {"k2": "v2"}, node_name="node_a", step_index=1)
    reloaded = store.get_session_state("sess_01")
    self.assertEqual(reloaded["k1"], "v1")
    self.assertEqual(reloaded["k2"], "v2")

    compactor = ContextCompactor()
    long_text = "\n".join(
        [f"Filler line {i}" for i in range(400)]
        + ["ACTION: $28.5M CP3 milestone due 2026-10-29 (RED)"]
        + [f"Tail line {i}" for i in range(400)]
    )
    compacted, metrics = compactor.compact_workspace_context({"doc": long_text})
    self.assertLess(metrics["compacted_tokens"], metrics["original_tokens"])
    self.assertIn("$28.5M CP3", compacted["doc"])

    consolidator = AsyncMemoryConsolidator(db_path=self.db_path)
    res = await consolidator.consolidate_session_async(
        "sess_01",
        {
            "dashboard_payload": {
                "innovation_radar": {
                    "ideas": [
                        {
                            "title": "National Sovereign AI Gateway",
                            "target_ministry_or_agency": "CAIT",
                        }
                    ]
                }
            }
        },
    )
    self.assertGreaterEqual(res["facts_consolidated"], 1)
    facts = consolidator.query_memories(category="innovation_history")
    self.assertEqual(facts[0]["entity_key"], "National Sovereign AI Gateway")

    # PII redaction verification
    raw_pii = "Email clappaert@google.com, Civil ID 289051201234, Phone +965 5555 1234, Token Bearer TEST_OAUTH_TOKEN_SAMPLE_12345"
    scrubbed = scrub_pii(raw_pii)
    self.assertNotIn("289051201234", scrubbed)
    self.assertNotIn("+965 5555 1234", scrubbed)
    self.assertNotIn("TEST_OAUTH_TOKEN_SAMPLE_12345", scrubbed)
    self.assertIn("c***@google.com", scrubbed)

  def test_slide_batch_column_width_and_guardrail_exceptions(self) -> None:
    """Verifies all table column widths are >= 32pt (406400 EMU) and guardrails block unauthorized sends."""
    from kuwait_cal_agent._adk_compat import Context
    from kuwait_cal_agent.nodes.domain_agents import (
        _default_afa_consumption,
        _default_innovation_radar,
        _default_pso_portfolio,
        _default_todo_and_reminders,
    )

    ctx = Context()
    payload = {
        "as_of_date": "Oct 22, 2026",
        "todo_and_reminders": _default_todo_and_reminders(ctx, "").model_dump(),
        "pso_portfolio": _default_pso_portfolio(ctx, "").model_dump(),
        "afa_consumption": _default_afa_consumption(ctx, "").model_dump(),
        "innovation_radar": _default_innovation_radar(ctx, "").model_dump(),
    }
    ops = build_six_slide_batch_ops(payload)
    add_slides = [op for op in ops if op.get("op") == "add-slide"]
    self.assertEqual(len(add_slides), 5)

    for op in ops:
      if op.get("op") == "updateTableColumnProperties":
        width_pt = op["updateTableColumnProperties"]["tableColumnProperties"][
            "columnWidth"
        ]["magnitude"]
        self.assertGreaterEqual(
            width_pt, 32, "Google Slides API requires column width >= 32pt"
        )

    with self.assertRaises(PermissionError):
      send_dashboard_digest_to_willem(
          payload, {"overall_score": 9.9}, recipient_email="someone@example.com"
      )

    with self.assertRaises(PermissionError):
      stage_or_send_colleague_reminder(
          colleague_email="ehsanr@google.com",
          subject="Follow up",
          body="Hi",
          delivery_mode="send",
          user_consent_verified=False,
      )


if __name__ == "__main__":
  unittest.main()
