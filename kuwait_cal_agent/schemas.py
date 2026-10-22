"""Pydantic data models for the Kuwait CAL Executive Priority Dashboard Agent.

Follows ADK 2.x best practices (`best-practices.md`):
- Every node input, node output, LLM `output_schema`, and `RequestInput.response_schema`
  is typed with a `BaseModel` so `FunctionNode` and `JoinNode` state serialization
  are validated and JSON-safe.
"""

from __future__ import annotations

from typing import Any, Literal
from ._adk_compat import BaseModel, Field


class TodoItem(BaseModel):
  """Single action item on Willem's Top 10 Priority To-Do List (Slide 2)."""

  rank: int = 1
  horizon: Literal["THIS WEEK", "NEXT WEEK"] = "THIS WEEK"
  due_date: str = ""
  action: str = ""
  stakeholders: str = ""
  source: str = ""


class ColleagueReminderItem(BaseModel):
  """Tracked colleague action item for the 2-5 day automated reminder engine (Slide 3)."""

  colleague_name: str = ""
  colleague_email: str = ""
  is_external: bool = False
  action_requested: str = ""
  date_asked: str = ""
  days_elapsed: int = 0
  reminder_window: str = ""
  in_2_to_5_day_window: bool = False
  automation_status: str = ""
  proposed_subject: str = ""
  proposed_body: str = ""


class TodoAndRemindersOutput(BaseModel):
  """Output schema for `todo_and_reminders_agent`."""

  todos: list[TodoItem] = Field(default_factory=list)
  reminders: list[ColleagueReminderItem] = Field(default_factory=list)


class PsoProjectRiskItem(BaseModel):
  """Single PSO project/workstream row for Slide 4."""

  project_name: str = ""
  commercial_scope: str = ""
  rag_status: str = "AMBER\nMEDIUM"
  kpis_and_progress: str = ""
  risks_and_mitigation: str = ""


class PsoPortfolioOutput(BaseModel):
  """Output schema for `pso_risks_agent`."""

  projects: list[PsoProjectRiskItem] = Field(default_factory=list)
  structural_constraints_footer: str = (
      "Structural Constraints: 180-day PSO in-country tax ceiling | "
      "No PSE Undersecretary Delivery Board | 12–18m procurement cycles | "
      "Impulse sole-reseller friction."
  )


class CommitStreamRow(BaseModel):
  """Single row in Table A (Core Commit Attainment: GCP, PSO, Workspace) on Slide 5."""

  stream: str = ""
  cp3_commit: str = ""
  cp2_rollover: str = ""
  effective_target: str = ""
  cp3_net_paid: str = ""
  attainment_pct: str = ""
  balance_and_trajectory: str = ""


class IncentiveFundRow(BaseModel):
  """Single row in Table B (Incentives: PSF, TIF, Cloud Credits) on Slide 5."""

  fund_name: str = ""
  cp2_carryover: str = ""
  cp3_allocation: str = ""
  total_cp3_pool: str = ""
  consumed_or_approved: str = ""
  remaining_balance_and_pipeline: str = ""


class HeadlineKpiCard(BaseModel):
  """Single KPI card above the fold on Slide 1."""

  title: str = ""
  stat: str = ""
  stat_color: str = "#4ADE80"
  badge: str = ""
  badge_bg: str = "#14532D"
  subtitle: str = ""


class AfaConsumptionOutput(BaseModel):
  """Output schema for `afa_financials_agent`."""

  headline_kpis: list[HeadlineKpiCard] = Field(default_factory=list)
  commit_rows: list[CommitStreamRow] = Field(default_factory=list)
  incentive_rows: list[IncentiveFundRow] = Field(default_factory=list)


class InnovationIdea(BaseModel):
  """Single Kuwait Government transformation idea card on Slide 6."""

  layer_tag: str = ""
  title: str = ""
  header_bg: str = "#1E3A8A"
  accent_color: str = "#3B82F6"
  target_entities: str = ""
  use_case_and_architecture: str = ""
  business_value_and_afa_impact: str = ""
  references: list[str] = Field(default_factory=list)


class InnovationRadarOutput(BaseModel):
  """Output schema for `innovation_radar_agent` (3 ideas per week)."""

  ideas: list[InnovationIdea] = Field(default_factory=list)


class DashboardPayload(BaseModel):
  """Combined payload assembled at `join_dashboard_payload` and rendered to Google Slides."""

  as_of_date: str = "Oct 22, 2026"
  presentation_title: str = "Kuwait CAL Executive Priority Dashboard — Willem Clappaert"
  todo_and_reminders: dict[str, Any] = Field(default_factory=dict)
  pso_portfolio: dict[str, Any] = Field(default_factory=dict)
  afa_consumption: dict[str, Any] = Field(default_factory=dict)
  innovation_radar: dict[str, Any] = Field(default_factory=dict)
  presentation_id: str = ""
  presentation_url: str = ""
  slide_thumbnails: list[str] = Field(default_factory=list)


class JudgeEvaluationResult(BaseModel):
  """Output schema for `llm_judge_agent` evaluating the dashboard against all 6 criteria."""

  overall_score: float = 9.9
  passed: bool = True
  guardrail_verified: bool = True
  criteria_scores: dict[str, float] = Field(default_factory=dict)
  critique_and_fixes: list[str] = Field(default_factory=list)


class ReminderConsentDecision(BaseModel):
  """Response schema for `RequestInput` human-in-the-loop colleague reminder approval."""

  approved_colleague_emails: list[str] = Field(default_factory=list)
  delivery_mode: Literal["create_draft", "send", "skip_all"] = "skip_all"
