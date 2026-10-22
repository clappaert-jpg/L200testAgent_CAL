"""Unit & Workflow Integration Tests for the Kuwait CAL ADK Agent.

Compatible with both `pytest` (`pytest tests/`) and `python3 -m unittest discover -s tests`.
Verifies:
1. Parallel Fan-Out & `JoinNode` Synchronization across Stage 1 & Stage 2.
2. Deterministic 6-Slide Google Slides batch generation (including >= 34pt column widths).
3. LLM-as-a-Judge Conditional Revision Loop (`'revise'` -> `revise_dashboard_agent` -> `'approved'`).
4. Unattended Sunday 6:00 AM execution (`clappaert@google.com` self-email + 0 colleague emails).
5. Interactive Human-in-the-Loop (`RequestInput`) pause & resume for colleague reminders.
6. Hard Guardrail Enforcement (`PermissionError` if unconsented colleague send is attempted).
"""

from __future__ import annotations

import os
import unittest

from kuwait_cal_agent._adk_compat import InMemoryRunner, genai_types
from kuwait_cal_agent.agent import app, root_agent
from kuwait_cal_agent.tools.gmail_sender import (
    send_dashboard_digest_to_willem,
    stage_or_send_colleague_reminder,
)
from kuwait_cal_agent.tools.slides_renderer import build_six_slide_batch_ops


def node_name(event) -> str | None:
  """Extracts the short node name from `event.node_info.path` ('workflow@1/step@1' -> 'step')."""
  if not getattr(event, "node_info", None):
    return None
  return event.node_info.path.split("/")[-1].split("@")[0]


class KuwaitCalAdkWorkflowTests(unittest.IsolatedAsyncioTestCase):
  """Tests the 5-stage ADK Workflow graph, LLM-as-a-Judge loop, and HITL guardrails."""

  def setUp(self) -> None:
    super().setUp()
    os.environ["CAL_AGENT_DRY_RUN"] = "1"

  async def test_unattended_sunday_6am_workflow_run(self) -> None:
    """Verifies full unattended Sunday 6am run: fan-out, join, slides, judge, and self-email."""
    runner = InMemoryRunner(app=app)
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

  async def test_llm_judge_self_healing_revision_loop(self) -> None:
    """Verifies that a failed first-pass Judge score routes to `revise_dashboard_agent` and loops."""
    runner = InMemoryRunner(agent=root_agent, app_name="test_judge_loop")
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
    self.assertTrue(after.state["judge_evaluation"]["passed"])

  async def test_hitl_pause_and_resume_for_colleague_reminders(self) -> None:
    """Verifies interactive `RequestInput` pause and resume for colleague reminder approval."""
    runner = InMemoryRunner(app=app)
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

    # Resume with explicit approval to create drafts for Ehsan and Lama
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
        e for e in resumed_events if node_name(e) == "dispatch_approved_reminders_node" and e.output
    ]
    self.assertTrue(final_events)
    self.assertEqual(final_events[-1].output["approved_count"], 2)
    self.assertEqual(final_events[-1].output["delivery_mode"], "create_draft")

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
    # Slide 1 ('p') + 5 added slides = 6 slides total
    self.assertEqual(len(add_slides), 5)

    for op in ops:
      if op.get("op") == "updateTableColumnProperties":
        width_pt = (
            op["updateTableColumnProperties"]["tableColumnProperties"]["columnWidth"]["magnitude"]
        )
        self.assertGreaterEqual(width_pt, 32, "Google Slides API requires column width >= 32pt")

    # Guardrail 1: Self-digest cannot be sent to anyone other than clappaert@google.com
    with self.assertRaises(PermissionError):
      send_dashboard_digest_to_willem(payload, {"overall_score": 9.9}, recipient_email="someone@example.com")

    # Guardrail 2: Colleague reminder cannot be staged/sent without user_consent_verified=True
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
