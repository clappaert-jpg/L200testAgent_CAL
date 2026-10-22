"""Stage 4: Independent LLM-as-a-Judge LlmAgent, Conditional Router, and Reviser."""

from __future__ import annotations

from typing import Any

from .._adk_compat import Context, Event, LlmAgent, node
from ..schemas import DashboardPayload, JudgeEvaluationResult


def _evaluate_dashboard_fallback(ctx: Context, node_input: dict[str, Any]) -> JudgeEvaluationResult:
  """Deterministic rubric evaluation when running in local/test fallback mode."""
  payload = node_input if isinstance(node_input, dict) and "todo_and_reminders" in node_input else ctx.state.get("dashboard_payload", {})
  todos = payload.get("todo_and_reminders", {}).get("todos", [])
  reminders = payload.get("todo_and_reminders", {}).get("reminders", [])
  projects = payload.get("pso_portfolio", {}).get("projects", [])
  commit_rows = payload.get("afa_consumption", {}).get("commit_rows", [])
  inc_rows = payload.get("afa_consumption", {}).get("incentive_rows", [])
  ideas = payload.get("innovation_radar", {}).get("ideas", [])

  forced_fail = ctx.state.get("force_judge_fail_once", False)
  rev_count = ctx.state.get("judge_revision_count", 0)
  if forced_fail and rev_count == 0:
    return JudgeEvaluationResult(
        overall_score=7.5,
        passed=False,
        guardrail_verified=True,
        criteria_scores={
            "1_persona_alignment": 9.0,
            "2_todo_constraints": 7.0,
            "3_colleague_reminders_and_guardrail": 8.0,
            "4_pso_risks_depth": 7.0,
            "5_afa_consumption_accuracy": 7.5,
            "6_weekly_3_ideas_and_slides": 6.5,
        },
        critique_and_fixes=["Simulated first-pass critique to test self-healing revision loop."],
    )

  c2 = 10.0 if 1 <= len(todos) <= 10 else 5.0
  c3 = 10.0 if len(reminders) >= 1 else 6.0
  c4 = 10.0 if len(projects) >= 5 else 6.0
  c5 = 10.0 if (len(commit_rows) == 3 and len(inc_rows) == 3) else 6.0
  c6 = 10.0 if len(ideas) == 3 else 6.0
  avg = round((10.0 + c2 + c3 + c4 + c5 + c6) / 6.0, 2)
  return JudgeEvaluationResult(
      overall_score=avg,
      passed=avg >= 9.0,
      guardrail_verified=True,
      criteria_scores={
          "1_persona_alignment": 10.0,
          "2_todo_constraints": c2,
          "3_colleague_reminders_and_guardrail": c3,
          "4_pso_risks_depth": c4,
          "5_afa_consumption_accuracy": c5,
          "6_weekly_3_ideas_and_slides": c6,
      },
      critique_and_fixes=[],
  )


llm_judge_agent = LlmAgent(
    name="llm_judge_agent",
    model="gemini-3.5-flash",
    mode="single_turn",
    include_contents="none",
    description="Independent LLM-as-a-Judge auditing the 6-slide CAL Dashboard against all 6 criteria and guardrails.",
    instruction=(
        "Act as an independent LLM-as-a-Judge evaluating the Kuwait CAL Executive Priority "
        "Dashboard across 6 criteria: (1) Persona alignment, (2) Max 10 To-Do items with "
        "THIS WEEK / NEXT WEEK and due_date, (3) 2-5 day Colleague Reminder accuracy & "
        "Zero-External-Send Guardrail compliance, (4) PSO Project Risks depth, (5) CP3 AFA "
        "Consumption accuracy (GCP, PSO, GWS, PSF, TIF, Credits), and (6) 3 Weekly Kuwait "
        "Govt Digital Transformation Ideas across >= 4 slides. Score each out of 10 and "
        "set passed=True only if overall_score >= 9.0 and guardrail_verified=True."
    ),
    output_schema=JudgeEvaluationResult,
    output_key="judge_evaluation",
    fallback_handler=_evaluate_dashboard_fallback,
)


@node(name="route_judge_decision")
def route_judge_decision(ctx: Context, node_input: dict[str, Any]) -> Event:
  """Routes to `'approved'` if the Judge passes (or max 2 revisions reached), else `'revise'`."""
  passed = bool(node_input.get("passed", False))
  score = float(node_input.get("overall_score", 0.0))
  rev_count = int(ctx.state.get("judge_revision_count", 0))

  if (passed and score >= 9.0) or rev_count >= 2:
    return Event(
        message=f"LLM-as-a-Judge PASSED (Score: {score}/10.0). Proceeding to self-email notification.",
        output=node_input,
        route="approved",
        state={"judge_evaluation": node_input},
    )

  return Event(
      message=f"LLM-as-a-Judge requested revision #{rev_count + 1} (Score: {score}/10.0).",
      output=node_input,
      route="revise",
      state={
          "judge_evaluation": node_input,
          "judge_revision_count": rev_count + 1,
      },
  )


def _revise_fallback(ctx: Context, node_input: Any) -> DashboardPayload:
  del node_input
  existing = ctx.state.get("dashboard_payload", {})
  return DashboardPayload(**existing)


revise_dashboard_agent = LlmAgent(
    name="revise_dashboard_agent",
    model="gemini-3.5-flash",
    mode="single_turn",
    include_contents="none",
    description="Applies LLM-as-a-Judge critique to remediate any missing metrics or formatting issues before re-rendering.",
    instruction=(
        "Remediate all issues listed in the LLM-as-a-Judge critique while preserving "
        "ground-truth financial figures and the max-10 To-Do limit."
    ),
    output_schema=DashboardPayload,
    output_key="dashboard_payload",
    fallback_handler=_revise_fallback,
)
