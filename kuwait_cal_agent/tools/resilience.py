"""Tool Resilience, Exponential Backoff Retry, Idempotency & ADK FunctionTool Wrappers.

Protects external Google Workspace CLI and model invocations against transient
`503 UNAVAILABLE` and `429 RESOURCE_EXHAUSTED` spikes, enforces idempotency keys
for state-mutating tools, and exposes ADK FunctionTool schemas.
"""

from __future__ import annotations

import functools
import hashlib
import inspect
import json
import random
import time
from typing import Any, Callable

from ..observability.logging import log_intent, log_outcome

try:
  from google.adk.tools import FunctionTool as AdkFunctionTool  # type: ignore
  _HAS_ADK_FUNCTION_TOOL = True
except ImportError:
  AdkFunctionTool = None  # type: ignore
  _HAS_ADK_FUNCTION_TOOL = False

_TRANSIENT_ERROR_MARKERS = (
    "503",
    "UNAVAILABLE",
    "429",
    "RESOURCE_EXHAUSTED",
    "rateLimitExceeded",
    "DEADLINE_EXCEEDED",
    "timed out",
    "Temporary failure",
)


def is_transient_error(error_or_msg: Any) -> bool:
  """Returns True if an exception or error message indicates a retryable transient fault."""
  text = str(error_or_msg)
  return any(marker.lower() in text.lower() for marker in _TRANSIENT_ERROR_MARKERS)


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay_sec: float = 0.05,
    max_delay_sec: float = 2.0,
    jitter: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
  """Exponential backoff decorator for tools and LLM calls facing 503/429 spikes."""

  def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
      last_exc: Exception | None = None
      for attempt in range(1, max_attempts + 1):
        try:
          result = func(*args, **kwargs)
          if (
              isinstance(result, dict)
              and result.get("status") == "ERROR"
              and is_transient_error(result.get("error", ""))
              and attempt < max_attempts
          ):
            delay = min(max_delay_sec, base_delay_sec * (2 ** (attempt - 1)))
            if jitter:
              delay *= 0.5 + random.random()
            log_intent(
                component="tool_resilience",
                action=func.__name__,
                intent=f"Retry transient tool error on attempt {attempt}/{max_attempts}",
                metadata={"attempt": attempt, "delay_sec": round(delay, 4)},
            )
            time.sleep(delay)
            continue
          return result
        except Exception as exc:  # pylint: disable=broad-except
          last_exc = exc
          if attempt < max_attempts and is_transient_error(exc):
            delay = min(max_delay_sec, base_delay_sec * (2 ** (attempt - 1)))
            if jitter:
              delay *= 0.5 + random.random()
            log_outcome(
                component="tool_resilience",
                action=func.__name__,
                outcome=f"Transient exception on attempt {attempt}; backing off {delay:.3f}s",
                status="RETRYING",
                error=str(exc),
            )
            time.sleep(delay)
            continue
          raise
      if last_exc is not None:
        raise last_exc
      return None

    return wrapper

  return decorator


class IdempotencyLedger:
  """Prevents duplicate side-effects (emails/slides) when retrying state-mutating tools."""

  def __init__(self) -> None:
    self._records: dict[str, dict[str, Any]] = {}

  @staticmethod
  def compute_key(operation: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(f"{operation}:{canonical}".encode("utf-8")).hexdigest()
    return f"idem_{operation}_{digest[:20]}"

  def get(self, key: str) -> dict[str, Any] | None:
    return self._records.get(key)

  def record(self, key: str, result: dict[str, Any]) -> None:
    self._records[key] = dict(result)

  def clear(self) -> None:
    self._records.clear()


GLOBAL_IDEMPOTENCY_LEDGER = IdempotencyLedger()


class FunctionToolWrapper:
  """ADK FunctionTool interface descriptor with explicit JSON schema metadata."""

  def __init__(
      self,
      func: Callable[..., Any],
      *,
      name: str | None = None,
      description: str | None = None,
      read_only: bool = True,
      requires_confirmation: bool = False,
  ) -> None:
    self.func = func
    self.name = name or func.__name__
    self.description = description or (inspect.getdoc(func) or "").strip()
    self.read_only = read_only
    self.requires_confirmation = requires_confirmation
    self.adk_tool = (
        AdkFunctionTool(func) if _HAS_ADK_FUNCTION_TOOL and AdkFunctionTool else None
    )

  def __call__(self, *args: Any, **kwargs: Any) -> Any:
    return self.func(*args, **kwargs)

  def to_declaration(self) -> dict[str, Any]:
    sig = inspect.signature(self.func)
    params: dict[str, Any] = {}
    required: list[str] = []
    for pname, param in sig.parameters.items():
      params[pname] = {
          "type": str(param.annotation) if param.annotation != inspect.Parameter.empty else "Any",
          "default": None if param.default == inspect.Parameter.empty else param.default,
      }
      if param.default == inspect.Parameter.empty:
        required.append(pname)
    return {
        "name": self.name,
        "description": self.description,
        "read_only": self.read_only,
        "requires_confirmation": self.requires_confirmation,
        "parameters": {"properties": params, "required": required},
    }
