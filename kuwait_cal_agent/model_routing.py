"""Strategic Model Routing for Kuwait CAL Executive Priority Dashboard Agent.

Implements cost/latency vs. reasoning-depth model tiering across ADK LlmAgents:
- Tier 1 (FAST_EXTRACTION -> `gemini-3.8-flash`): High-throughput structured
  extraction from Calendar/Gmail (`todo_and_reminders_agent`) and tabular AFA
  spreadsheet metrics (`afa_financials_agent`).
- Tier 2 (DEEP_REASONING -> `gemini-3.1-pro` with ThinkingConfig): Complex
  multi-document risk correlation (`pso_risks_agent`) and Kuwait Vision 2035
  architectural synthesis (`innovation_radar_agent`).
- Tier 3 (ADVERSARIAL_JUDGE -> `gemini-3.1-pro` with extended ThinkingConfig):
  Strict 5-point rubric evaluation (`llm_judge_agent`) and self-healing revision
  (`revise_dashboard_agent`).
- Dynamic Escalation: Automatically upgrades any `gemini-3.8-flash` task to
  `gemini-3.1-pro` when `retry_iteration > 0` or input token complexity exceeds
  the fast-tier threshold.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import os
from typing import Any

from .observability.logging import log_intent, log_outcome

FLASH_MODEL = os.environ.get("CAL_FLASH_MODEL", "gemini-3.8-flash")
PRO_MODEL = os.environ.get("CAL_PRO_MODEL", "gemini-3.1-pro")


class ModelTier(str, Enum):
  """Strategic model routing tiers."""

  FAST_EXTRACTION = "FAST_EXTRACTION"
  DEEP_REASONING = "DEEP_REASONING"
  ADVERSARIAL_JUDGE = "ADVERSARIAL_JUDGE"


@dataclass(frozen=True)
class ModelRouteDecision:
  """Represents a resolved model routing configuration for an LlmAgent."""

  agent_name: str
  selected_model: str
  tier: ModelTier
  thinking_budget: int
  temperature: float
  rationale: str
  escalated: bool = False

  def to_dict(self) -> dict[str, Any]:
    data = asdict(self)
    data["tier"] = self.tier.value
    return data


_STATIC_AGENT_TIERS: dict[str, tuple[ModelTier, str]] = {
    "todo_and_reminders_agent": (
        ModelTier.FAST_EXTRACTION,
        "Structured action & SLA reminder extraction from Calendar/Gmail fits low-latency gemini-3.8-flash.",
    ),
    "afa_financials_agent": (
        ModelTier.FAST_EXTRACTION,
        "Deterministic tabular extraction & attainment math for GCP/TIF/PSF fits gemini-3.8-flash.",
    ),
    "pso_risks_agent": (
        ModelTier.DEEP_REASONING,
        "Cross-document correlation of sovereign cloud risks across Meet transcripts, emails, and trackers requires gemini-3.1-pro.",
    ),
    "innovation_radar_agent": (
        ModelTier.DEEP_REASONING,
        "Strategic Kuwait Vision 2035 use-case design and architecture synthesis requires gemini-3.1-pro.",
    ),
    "llm_judge_agent": (
        ModelTier.ADVERSARIAL_JUDGE,
        "Adversarial 5-point rubric audit and arithmetic verification requires gemini-3.1-pro with deep thinking.",
    ),
    "revise_dashboard_agent": (
        ModelTier.ADVERSARIAL_JUDGE,
        "Self-healing correction of failed rubric dimensions requires gemini-3.1-pro.",
    ),
}


class ModelRouter:
  """Central strategic model router with complexity & retry escalation."""

  COMPLEXITY_TOKEN_THRESHOLD: int = 32_000

  @classmethod
  def select_model(
      cls,
      agent_name: str,
      *,
      context_tokens: int = 0,
      retry_iteration: int = 0,
  ) -> ModelRouteDecision:
    """Selects optimal Gemini model (`gemini-3.8-flash` vs `gemini-3.1-pro`)."""
    base_tier, rationale = _STATIC_AGENT_TIERS.get(
        agent_name,
        (
            ModelTier.FAST_EXTRACTION,
            "Default fast extraction tier.",
        ),
    )

    escalated = False
    effective_tier = base_tier

    if base_tier == ModelTier.FAST_EXTRACTION and (
        retry_iteration > 0 or context_tokens > cls.COMPLEXITY_TOKEN_THRESHOLD
    ):
      effective_tier = ModelTier.DEEP_REASONING
      escalated = True
      rationale = (
          f"Dynamically escalated {agent_name} from {FLASH_MODEL} to {PRO_MODEL} "
          f"(retry_iteration={retry_iteration}, context_tokens={context_tokens})."
      )

    if effective_tier == ModelTier.FAST_EXTRACTION:
      decision = ModelRouteDecision(
          agent_name=agent_name,
          selected_model=FLASH_MODEL,
          tier=effective_tier,
          thinking_budget=0,
          temperature=0.1,
          rationale=rationale,
          escalated=escalated,
      )
    elif effective_tier == ModelTier.DEEP_REASONING:
      decision = ModelRouteDecision(
          agent_name=agent_name,
          selected_model=PRO_MODEL,
          tier=effective_tier,
          thinking_budget=4096,
          temperature=0.2,
          rationale=rationale,
          escalated=escalated,
      )
    else:
      decision = ModelRouteDecision(
          agent_name=agent_name,
          selected_model=PRO_MODEL,
          tier=effective_tier,
          thinking_budget=8192,
          temperature=0.1,
          rationale=rationale,
          escalated=escalated,
      )

    log_intent(
        component="model_router",
        action="select_model",
        intent=f"Route {agent_name} to optimal Gemini model tier ({decision.tier.value})",
        model=decision.selected_model,
        model_tier=decision.tier.value,
        metadata=decision.to_dict(),
    )
    log_outcome(
        component="model_router",
        action="select_model",
        outcome=f"Selected {decision.selected_model} (tier={decision.tier.value}, thinking_budget={decision.thinking_budget})",
        status="SUCCESS",
        model=decision.selected_model,
        metrics={
            "thinking_budget": decision.thinking_budget,
            "escalated": int(decision.escalated),
        },
    )
    return decision

  @classmethod
  def get_routing_table(cls) -> dict[str, dict[str, Any]]:
    """Returns the complete static routing table for inspection and tests."""
    return {
        name: cls.select_model(name).to_dict() for name in _STATIC_AGENT_TIERS
    }
