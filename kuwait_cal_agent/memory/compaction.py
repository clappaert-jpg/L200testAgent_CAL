"""Context & Event History Compaction (`ContextCompactor` & `EventsCompactionConfig`).

Prevents context window bloat by compacting multi-turn session event histories
and large raw Google Workspace payloads (Calendar agendas, Gmail threads,
Docs, Sheets) while preserving high-signal entities (financial figures, dates,
project names, and action owners).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Any

from ..observability.logging import log_intent, log_outcome


@dataclass(frozen=True)
class EventsCompactionConfig:
  """Configuration for sliding-window and token-budget context compaction."""

  compaction_interval: int = 4
  overlap_size: int = 2
  max_context_tokens: int = 16_000
  max_field_chars: int = 4_000


_HIGH_SIGNAL_LINE_PATTERN = re.compile(
    r"(?:\$[\d,.]+[KMB]?|\b\d{1,3}(?:\.\d+)?%|\b202\d-\d{2}-\d{2}\b|"
    r"\b(?:RED|AMBER|GREEN|HIGH|MEDIUM|LOW|ACTION|BLOCKER|RISK|GAP|ATTAINMENT|"
    r"CITRA|MOF|CBK|KDIPA|TIF|PSF|GCP|SLA|DUE)\b)",
    re.IGNORECASE,
)


def estimate_tokens(text_or_obj: Any) -> int:
  """Approximates LLM token count (~4 characters per token)."""
  if isinstance(text_or_obj, str):
    return max(1, len(text_or_obj) // 4)
  serialized = json.dumps(text_or_obj, default=str)
  return max(1, len(serialized) // 4)


class ContextCompactor:
  """Sliding-window event history & token-budget workspace context compactor."""

  def __init__(self, config: EventsCompactionConfig | None = None) -> None:
    self.config = config or EventsCompactionConfig()

  def compact_text_preserving_anchors(
      self, text: str, max_chars: int | None = None
  ) -> str:
    """Compacts long text by keeping header, high-signal anchor lines, and tail."""
    limit = max_chars or self.config.max_field_chars
    if not text or len(text) <= limit:
      return text

    lines = text.splitlines()
    if len(lines) <= 10:
      half = limit // 2
      return (
          text[:half]
          + "\n... [COMPACTED MIDDLE CONTEXT] ...\n"
          + text[-half:]
      )

    head_lines = lines[:5]
    tail_lines = lines[-5:]
    middle_lines = lines[5:-5]
    anchor_lines = [
        line for line in middle_lines if _HIGH_SIGNAL_LINE_PATTERN.search(line)
    ]

    compacted_parts = (
        head_lines
        + ["... [COMPACTED: Preserved High-Signal Anchors] ..."]
        + anchor_lines[:25]
        + ["... [END COMPACTED ANCHORS] ..."]
        + tail_lines
    )
    joined = "\n".join(compacted_parts)
    if len(joined) > limit:
      return joined[:limit] + "\n... [TRUNCATED TO TOKEN BUDGET]"
    return joined

  def compact_workspace_context(
      self, raw_context: dict[str, Any]
  ) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compacts joined Google Workspace context within `max_context_tokens`."""
    original_tokens = estimate_tokens(raw_context)
    log_intent(
        component="context_compactor",
        action="compact_workspace_context",
        intent=(
            f"Compact raw workspace context (original_tokens={original_tokens}, "
            f"budget={self.config.max_context_tokens})"
        ),
        metadata=asdict(self.config),
    )

    compacted: dict[str, Any] = {}
    fields_compacted = 0

    for key, value in raw_context.items():
      if isinstance(value, str):
        new_val = self.compact_text_preserving_anchors(value)
        if len(new_val) < len(value):
          fields_compacted += 1
        compacted[key] = new_val
      elif isinstance(value, dict):
        sub_dict: dict[str, Any] = {}
        for sub_k, sub_v in value.items():
          if isinstance(sub_v, str):
            new_sub_v = self.compact_text_preserving_anchors(sub_v)
            if len(new_sub_v) < len(sub_v):
              fields_compacted += 1
            sub_dict[sub_k] = new_sub_v
          else:
            sub_dict[sub_k] = sub_v
        compacted[key] = sub_dict
      else:
        compacted[key] = value

    compacted_tokens = estimate_tokens(compacted)
    compression_ratio = round(
        compacted_tokens / max(1, original_tokens), 4
    )
    metrics = {
        "original_tokens": original_tokens,
        "compacted_tokens": compacted_tokens,
        "compression_ratio": compression_ratio,
        "fields_compacted": fields_compacted,
        "within_budget": compacted_tokens <= self.config.max_context_tokens,
    }
    log_outcome(
        component="context_compactor",
        action="compact_workspace_context",
        outcome=(
            f"Compacted context from {original_tokens} to {compacted_tokens} tokens "
            f"(ratio={compression_ratio})"
        ),
        status="SUCCESS",
        metrics=metrics,
    )
    return compacted, metrics

  def compact_event_history(
      self, events: list[dict[str, Any]]
  ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Applies sliding-window summarization over multi-step session event history."""
    total_events = len(events)
    if total_events <= self.config.compaction_interval:
      return events, {
          "events_before": total_events,
          "events_after": total_events,
          "compacted": False,
      }

    overlap = max(1, self.config.overlap_size)
    older_events = events[:-overlap]
    recent_events = events[-overlap:]

    summarized_nodes = [str(e.get("node_name", "unknown")) for e in older_events]
    merged_keys: set[str] = set()
    for ev in older_events:
      delta = ev.get("state_delta") or {}
      if isinstance(delta, dict):
        merged_keys.update(delta.keys())

    summary_event = {
        "event_id": "COMPACTED_SUMMARY",
        "step_index": older_events[-1].get("step_index", 0),
        "node_name": "history_compaction_summary",
        "route": older_events[-1].get("route"),
        "state_delta": {
            "_compacted_nodes": summarized_nodes,
            "_compacted_state_keys": sorted(merged_keys),
            "_compacted_event_count": len(older_events),
        },
    }
    compacted_list = [summary_event] + recent_events
    return compacted_list, {
        "events_before": total_events,
        "events_after": len(compacted_list),
        "compacted": True,
        "summarized_event_count": len(older_events),
    }
