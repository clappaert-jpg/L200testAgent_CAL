#!/usr/bin/env python3
"""Dedicated Golden-Dataset Regression Evaluation Harness for Kuwait CAL ADK Agent.

Evaluates the agent against `evals/golden_dataset.json` across 5 rubric dimensions:
1. Tool & Interface Trajectory Accuracy
2. Context Compaction & Persistent SQLite Memory Consolidation
3. Orchestration, Self-Healing Judge Loop & Strategic Model Routing (`gemini-3.8-flash` & `gemini-3.1-pro`)
4. Observability (Structured JSON Intent/Outcome Logs, OpenTelemetry Spans & PII Redaction)
5. Guardrail & HITL (`RequestInput`) Enforcement

Usage:
  python3 evals/run_eval.py --min-score 0.95
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
  sys.path.insert(0, str(REPO_ROOT))

from kuwait_cal_agent._adk_compat import DatabaseSessionService, InMemoryRunner, genai_types
from kuwait_cal_agent.agent import app, memory_consolidator, root_agent
from kuwait_cal_agent.memory.compaction import ContextCompactor
from kuwait_cal_agent.model_routing import FLASH_MODEL, ModelRouter, PRO_MODEL
from kuwait_cal_agent.observability.logging import (
    clear_captured_json_logs,
    get_captured_json_logs,
    log_outcome,
)
from kuwait_cal_agent.observability.pii_redactor import scrub_pii
from kuwait_cal_agent.observability.telemetry import (
    clear_recorded_spans,
    get_recorded_spans,
)

GOLDEN_DATASET_PATH = Path(__file__).resolve().parent / "golden_dataset.json"


def _short_node_name(event: Any) -> str | None:
  if not getattr(event, "node_info", None):
    return None
  return str(event.node_info.path).split("/")[-1].split("@")[0]


async def evaluate_case_01_nominal(case: dict[str, Any], db_path: str) -> dict[str, Any]:
  """Evaluates Case 01: Nominal Sunday 6am Executive Run & Trajectory."""
  runner = InMemoryRunner(
      app=app, session_service=DatabaseSessionService(db_path=db_path)
  )
  session = await runner.session_service.create_session(
      app_name=app.name,
      user_id="clappaert",
      state=dict(case["initial_state"]),
  )
  msg = genai_types.Content(
      role="user",
      parts=[genai_types.Part.from_text(text=case["user_prompt"])],
  )
  events = [
      e
      async for e in runner.run_async(
          user_id="clappaert", session_id=session.id, new_message=msg
      )
  ]
  await memory_consolidator.wait_for_pending_tasks()

  visited = [_short_node_name(e) for e in events if _short_node_name(e)]
  expected = case["expected_trajectory"]
  matched = sum(1 for node in expected if node in visited)
  trajectory_recall = matched / len(expected)

  after = await runner.session_service.get_session(
      app_name=app.name, user_id="clappaert", session_id=session.id
  )
  payload = after.state["dashboard_payload"]
  assertions = case["expected_assertions"]
  checks = [
      len(payload["todo_and_reminders"]["todos"]) <= assertions["max_todos"],
      len(payload["innovation_radar"]["ideas"]) == assertions["exact_innovation_ideas"],
      after.state["judge_evaluation"]["overall_score"] >= assertions["min_judge_score"],
      after.state["self_email_result"]["to"] == assertions["self_email_recipient"],
      after.state["colleague_emails_sent"] == assertions["colleague_emails_sent"],
  ]
  assertion_score = sum(1 for c in checks if c) / len(checks)
  score = round((trajectory_recall + assertion_score) / 2.0, 4)
  return {
      "case_id": case["case_id"],
      "score": score,
      "trajectory_recall": round(trajectory_recall, 4),
      "assertion_score": round(assertion_score, 4),
      "passed": score >= 0.95,
  }


async def evaluate_case_02_self_healing(case: dict[str, Any], db_path: str) -> dict[str, Any]:
  """Evaluates Case 02: Self-Healing LLM-as-a-Judge Revision Loop on gemini-3.1-pro."""
  runner = InMemoryRunner(
      agent=root_agent,
      app_name="eval_self_healing",
      session_service=DatabaseSessionService(db_path=db_path),
  )
  session = await runner.session_service.create_session(
      app_name="eval_self_healing",
      user_id="clappaert",
      state=dict(case["initial_state"]),
  )
  msg = genai_types.Content(
      role="user",
      parts=[genai_types.Part.from_text(text=case["user_prompt"])],
  )
  events = [
      e
      async for e in runner.run_async(
          user_id="clappaert", session_id=session.id, new_message=msg
      )
  ]
  visited = [_short_node_name(e) for e in events if _short_node_name(e)]
  after = await runner.session_service.get_session(
      app_name="eval_self_healing", user_id="clappaert", session_id=session.id
  )
  assertions = case["expected_assertions"]
  checks = [
      "revise_dashboard_agent" in visited,
      visited.count("llm_judge_agent") == 2,
      after.state.get("judge_revision_count") == assertions["judge_revision_count"],
      bool(after.state.get("judge_evaluation", {}).get("passed")) is assertions["judge_passed"],
      after.state.get("active_revision_model") == assertions["active_revision_model"],
  ]
  score = round(sum(1 for c in checks if c) / len(checks), 4)
  return {
      "case_id": case["case_id"],
      "score": score,
      "passed": score == 1.0,
  }


async def evaluate_case_03_hitl_gate(case: dict[str, Any], db_path: str) -> dict[str, Any]:
  """Evaluates Case 03: Interactive RequestInput Consent Gate Pause & Resume."""
  runner = InMemoryRunner(
      app=app, session_service=DatabaseSessionService(db_path=db_path)
  )
  session = await runner.session_service.create_session(
      app_name=app.name,
      user_id="clappaert",
      state=dict(case["initial_state"]),
  )
  msg = genai_types.Content(
      role="user",
      parts=[genai_types.Part.from_text(text=case["user_prompt"])],
  )
  paused_events = [
      e
      async for e in runner.run_async(
          user_id="clappaert", session_id=session.id, new_message=msg
      )
  ]
  fc_events = [e for e in paused_events if e.get_function_calls()]
  if not fc_events:
    return {"case_id": case["case_id"], "score": 0.0, "passed": False}

  fc = fc_events[-1].get_function_calls()[0]
  resume_msg = genai_types.Content(
      role="user",
      parts=[
          genai_types.Part(
              function_response=genai_types.FunctionResponse(
                  id=fc.id,
                  name=fc.name,
                  response={"result": case["resume_approval"]},
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
      if _short_node_name(e) == "dispatch_approved_reminders_node" and e.output
  ]
  assertions = case["expected_assertions"]
  checks = [
      fc.name == assertions["requires_interrupt"],
      bool(final_events),
      final_events[-1].output.get("approved_count") == assertions["approved_count_after_resume"],
      final_events[-1].output.get("delivery_mode") == assertions["delivery_mode"],
  ]
  score = round(sum(1 for c in checks if c) / len(checks), 4)
  return {
      "case_id": case["case_id"],
      "score": score,
      "passed": score == 1.0,
  }


def evaluate_case_04_model_routing(case: dict[str, Any]) -> dict[str, Any]:
  """Evaluates Case 04: Strategic Model Routing (`gemini-3.8-flash` & `gemini-3.1-pro`) + Escalation."""
  expected_map = case["expected_routing"]
  checks: list[bool] = []
  for agent_name, expected_model in expected_map.items():
    route = ModelRouter.select_model(agent_name)
    checks.append(route.selected_model == expected_model)

  # Verify dynamic escalation from gemini-3.8-flash to gemini-3.1-pro on retry or token spike
  escalated_retry = ModelRouter.select_model(
      "todo_and_reminders_agent", retry_iteration=1
  )
  escalated_tokens = ModelRouter.select_model(
      "afa_financials_agent", context_tokens=50_000
  )
  checks.append(escalated_retry.selected_model == PRO_MODEL and escalated_retry.escalated)
  checks.append(escalated_tokens.selected_model == PRO_MODEL and escalated_tokens.escalated)
  checks.append(FLASH_MODEL == "gemini-3.8-flash")
  checks.append(PRO_MODEL == "gemini-3.1-pro")

  score = round(sum(1 for c in checks if c) / len(checks), 4)
  return {
      "case_id": case["case_id"],
      "score": score,
      "passed": score == 1.0,
  }


async def evaluate_case_05_observability_and_memory(
    case: dict[str, Any]
) -> dict[str, Any]:
  """Evaluates Case 05: OpenTelemetry Spans, Structured JSON Intent/Outcome Logs, PII Redaction, and Memory."""
  logs = get_captured_json_logs()
  spans = get_recorded_spans()

  has_intent_logs = any(l.get("event_type") == "INTENT" and l.get("intent") for l in logs)
  has_outcome_logs = any(l.get("event_type") == "OUTCOME" and l.get("outcome") for l in logs)
  has_otel_spans = len(spans) >= 10 and all("trace_id" in s and "span_id" in s for s in spans)

  # Test PII redaction on sensitive probe strings
  probe = case["pii_probe_samples"][0]
  scrubbed = scrub_pii(probe)
  forbidden = case["expected_assertions"]["must_not_contain"]
  pii_clean = all(token not in scrubbed for token in forbidden) and "c***@google.com" in scrubbed

  # Test ContextCompactor on oversized payload
  compactor = ContextCompactor()
  huge_context = {
      "transcript": "\n".join(
          [f"Line {i}: general chatter" for i in range(500)]
          + ["CRITICAL ACTION: CITRA $28.5M CP3 milestone due 2026-10-29 (RED RISK)"]
          + [f"Footer {i}" for i in range(500)]
      )
  }
  compacted_ctx, comp_metrics = compactor.compact_workspace_context(huge_context)
  compaction_ok = (
      comp_metrics["compacted_tokens"] < comp_metrics["original_tokens"]
      and "CITRA $28.5M" in compacted_ctx["transcript"]
  )

  # Verify background AsyncMemoryConsolidator persisted facts in SQLite
  memories = memory_consolidator.query_memories()
  memory_ok = len(memories) >= case["expected_assertions"]["min_consolidated_facts"]

  checks = [
      has_intent_logs,
      has_outcome_logs,
      has_otel_spans,
      pii_clean,
      compaction_ok,
      memory_ok,
  ]
  score = round(sum(1 for c in checks if c) / len(checks), 4)
  return {
      "case_id": case["case_id"],
      "score": score,
      "spans_recorded": len(spans),
      "json_logs_emitted": len(logs),
      "semantic_memories_stored": len(memories),
      "passed": score == 1.0,
  }


async def run_all_evaluations(min_score: float = 0.95) -> dict[str, Any]:
  os.environ["CAL_AGENT_DRY_RUN"] = "1"
  clear_captured_json_logs()
  clear_recorded_spans()

  dataset = json.loads(GOLDEN_DATASET_PATH.read_text(encoding="utf-8"))
  cases = {c["case_id"]: c for c in dataset["cases"]}

  with tempfile.TemporaryDirectory(prefix="cal_eval_db_") as tmp_dir:
    db_path = str(Path(tmp_dir) / "eval_sessions.db")
    r1 = await evaluate_case_01_nominal(cases["eval_01_nominal_sunday_executive_run"], db_path)
    r2 = await evaluate_case_02_self_healing(cases["eval_02_self_healing_judge_loop"], db_path)
    r3 = await evaluate_case_03_hitl_gate(cases["eval_03_hitl_colleague_reminder_consent_gate"], db_path)
    r4 = evaluate_case_04_model_routing(cases["eval_04_strategic_model_routing_and_escalation"])
    r5 = await evaluate_case_05_observability_and_memory(
        cases["eval_05_observability_pii_and_persistent_memory"]
    )

  results = [r1, r2, r3, r4, r5]
  aggregate_score = round(
      sum(r["score"] for r in results) / len(results), 4
  )
  passed = aggregate_score >= min_score and all(r["passed"] for r in results)

  report = {
      "dataset_name": dataset["dataset_name"],
      "version": dataset["version"],
      "aggregate_score": aggregate_score,
      "min_score_threshold": min_score,
      "passed": passed,
      "case_results": results,
  }
  log_outcome(
      component="evaluation_harness",
      action="run_all_evaluations",
      outcome=f"Golden dataset evaluation finished: aggregate_score={aggregate_score} (passed={passed})",
      status="SUCCESS" if passed else "FAILED",
      metrics={"aggregate_score": aggregate_score, "cases_tested": len(results)},
  )
  return report


def main() -> int:
  parser = argparse.ArgumentParser(
      description="Run Kuwait CAL Agent Golden Dataset Regression Evaluation Harness"
  )
  parser.add_argument(
      "--min-score",
      type=float,
      default=0.95,
      help="Minimum aggregate score required to pass (default: 0.95)",
  )
  args = parser.parse_args()
  report = asyncio.run(run_all_evaluations(min_score=args.min_score))
  sys.stdout.write(json.dumps(report, indent=2) + "\n")
  return 0 if report["passed"] else 1


if __name__ == "__main__":
  sys.exit(main())
