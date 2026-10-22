"""Structured JSON Logging with explicit Intent/Outcome capture & PII Redaction.

Replaces raw print statements with structured JSON records correlated with
OpenTelemetry trace_id and span_id, enforcing automated PII redaction.
"""

from __future__ import annotations

import datetime
import json
import logging
import sys
from typing import Any

from .pii_redactor import PiiRedactingFilter, scrub_pii

try:
  from pythonjsonlogger import jsonlogger  # type: ignore
  _HAS_PYTHON_JSON_LOGGER = True
except ImportError:
  jsonlogger = None  # type: ignore
  _HAS_PYTHON_JSON_LOGGER = False

try:
  import structlog  # type: ignore
  _HAS_STRUCTLOG = True
except ImportError:
  structlog = None  # type: ignore
  _HAS_STRUCTLOG = False


class StructuredJsonFormatter(logging.Formatter):
  """Emits single-line JSON log records with OpenTelemetry context & PII scrubbing."""

  def format(self, record: logging.LogRecord) -> str:
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    message = record.getMessage()

    payload: dict[str, Any] = {
        "timestamp": now_iso,
        "severity": record.levelname,
        "logger": record.name,
        "message": scrub_pii(message),
        "event_type": getattr(record, "event_type", "APPLICATION_LOG"),
        "component": getattr(record, "component", record.name),
        "action": getattr(record, "action", record.funcName),
        "trace_id": getattr(record, "trace_id", "00000000000000000000000000000000"),
        "span_id": getattr(record, "span_id", "0000000000000000"),
        "pii_redacted": True,
    }

    for extra_field in (
        "intent",
        "outcome",
        "status",
        "latency_ms",
        "model",
        "model_tier",
        "session_id",
        "metrics",
        "metadata",
        "error",
    ):
      val = getattr(record, extra_field, None)
      if val is not None:
        payload[extra_field] = scrub_pii(val)

    if record.exc_info:
      payload["exception"] = scrub_pii(self.formatException(record.exc_info))

    return json.dumps(payload, ensure_ascii=False, default=str)


_CONFIGURED_LOGGERS: set[str] = set()
_LOG_RECORDS_BUFFER: list[dict[str, Any]] = []


class InMemoryJsonLogHandler(logging.Handler):
  """Captures structured JSON log dicts in-memory for audit and eval assertions."""

  def emit(self, record: logging.LogRecord) -> None:
    try:
      formatted = self.format(record)
      _LOG_RECORDS_BUFFER.append(json.loads(formatted))
    except Exception:  # pylint: disable=broad-except
      pass


def get_structured_logger(name: str = "kuwait_cal_agent") -> logging.Logger:
  """Returns a configured structured JSON logger with PII redaction filter."""
  logger = logging.getLogger(name)
  if name not in _CONFIGURED_LOGGERS:
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.filters.clear()
    logger.handlers.clear()

    pii_filter = PiiRedactingFilter()
    formatter = StructuredJsonFormatter()

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(pii_filter)

    memory_handler = InMemoryJsonLogHandler()
    memory_handler.setFormatter(formatter)
    memory_handler.addFilter(pii_filter)

    logger.addFilter(pii_filter)
    logger.addHandler(stream_handler)
    logger.addHandler(memory_handler)
    _CONFIGURED_LOGGERS.add(name)
  return logger


def get_captured_json_logs() -> list[dict[str, Any]]:
  """Returns all structured JSON logs emitted during the process lifecycle."""
  return list(_LOG_RECORDS_BUFFER)


def clear_captured_json_logs() -> None:
  """Clears the in-memory JSON log buffer (useful between unit/eval tests)."""
  _LOG_RECORDS_BUFFER.clear()


def _current_trace_ids() -> tuple[str, str]:
  """Fetches active OpenTelemetry trace_id and span_id if available."""
  try:
    from .telemetry import get_current_trace_And_span_id
    return get_current_trace_And_span_id()
  except Exception:  # pylint: disable=broad-except
    return ("00000000000000000000000000000000", "0000000000000000")


def log_intent(
    component: str,
    action: str,
    intent: str,
    *,
    model: str | None = None,
    model_tier: str | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
  """Emits an explicit structured JSON log capturing agent/tool INTENT."""
  logger = get_structured_logger("kuwait_cal_agent")
  trace_id, span_id = _current_trace_ids()
  logger.info(
      f"[{component}.{action}] INTENT: {intent}",
      extra={
          "event_type": "INTENT",
          "component": component,
          "action": action,
          "intent": intent,
          "model": model,
          "model_tier": model_tier,
          "session_id": session_id,
          "metadata": metadata or {},
          "trace_id": trace_id,
          "span_id": span_id,
      },
  )


def log_outcome(
    component: str,
    action: str,
    outcome: str,
    *,
    status: str = "SUCCESS",
    latency_ms: float | None = None,
    model: str | None = None,
    session_id: str | None = None,
    metrics: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
  """Emits an explicit structured JSON log capturing agent/tool OUTCOME."""
  logger = get_structured_logger("kuwait_cal_agent")
  trace_id, span_id = _current_trace_ids()
  level = logging.ERROR if status in ("ERROR", "FAILED") else logging.INFO
  logger.log(
      level,
      f"[{component}.{action}] OUTCOME ({status}): {outcome}",
      extra={
          "event_type": "OUTCOME",
          "component": component,
          "action": action,
          "outcome": outcome,
          "status": status,
          "latency_ms": round(latency_ms, 3) if latency_ms is not None else None,
          "model": model,
          "session_id": session_id,
          "metrics": metrics or {},
          "error": error,
          "trace_id": trace_id,
          "span_id": span_id,
      },
  )
