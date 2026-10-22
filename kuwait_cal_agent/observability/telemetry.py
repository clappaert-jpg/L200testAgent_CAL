"""Distributed Tracing with OpenTelemetry & PII-Redacted Span Attributes.

Provides OpenTelemetry TracerProvider setup, span context propagation, and
@traced_node / @traced_tool decorators that capture intent, outcome, latency,
and GenAI model metadata on every workflow stage and tool execution.
"""

from __future__ import annotations

import contextvars
import functools
import inspect
import secrets
import time
from typing import Any, Callable

from .logging import log_intent, log_outcome
from .pii_redactor import scrub_pii

try:
  from opentelemetry import trace as otel_trace  # type: ignore
  from opentelemetry.sdk.resources import Resource  # type: ignore
  from opentelemetry.sdk.trace import TracerProvider  # type: ignore
  from opentelemetry.sdk.trace.export import (  # type: ignore
      SimpleSpanProcessor,
      SpanExporter,
      SpanExportResult,
  )
  _HAS_OTEL_SDK = True
except ImportError:
  otel_trace = None  # type: ignore
  Resource = None  # type: ignore
  TracerProvider = None  # type: ignore
  SimpleSpanProcessor = None  # type: ignore
  SpanExporter = object  # type: ignore
  SpanExportResult = None  # type: ignore
  _HAS_OTEL_SDK = False


_ACTIVE_TRACE_ID: contextvars.ContextVar[str] = contextvars.ContextVar(
    "active_trace_id", default=""
)
_ACTIVE_SPAN_ID: contextvars.ContextVar[str] = contextvars.ContextVar(
    "active_span_id", default=""
)
_RECORDED_SPANS: list[dict[str, Any]] = []


class PiiRedactingSpanExporter(SpanExporter):  # type: ignore[misc]
  """OpenTelemetry SpanExporter that scrubs PII and records spans in-memory."""

  def export(self, spans: Any) -> Any:
    for span in spans:
      ctx = span.get_span_context()
      attrs = dict(span.attributes or {})
      _RECORDED_SPANS.append({
          "name": span.name,
          "trace_id": f"{ctx.trace_id:032x}",
          "span_id": f"{ctx.span_id:016x}",
          "parent_span_id": (
              f"{span.parent.span_id:016x}" if span.parent else None
          ),
          "start_time_ns": span.start_time,
          "end_time_ns": span.end_time,
          "attributes": scrub_pii(attrs),
          "status": str(span.status.status_code) if span.status else "OK",
      })
    if SpanExportResult is not None:
      return SpanExportResult.SUCCESS
    return None

  def shutdown(self) -> None:
    return None


class _FallbackSpan:
  """OpenTelemetry-compatible Span used when opentelemetry-sdk is absent."""

  def __init__(
      self,
      name: str,
      trace_id: str,
      span_id: str,
      parent_span_id: str | None = None,
      attributes: dict[str, Any] | None = None,
  ) -> None:
    self.name = name
    self.trace_id = trace_id
    self.span_id = span_id
    self.parent_span_id = parent_span_id
    self.attributes: dict[str, Any] = scrub_pii(attributes or {})
    self.status: str = "OK"
    self.start_time_ns: int = time.time_ns()
    self.end_time_ns: int | None = None
    self._prev_trace_token: Any = None
    self._prev_span_token: Any = None

  def set_attribute(self, key: str, value: Any) -> None:
    self.attributes[key] = scrub_pii({key: value})[key]

  def set_status(self, status: str, description: str | None = None) -> None:
    self.status = status
    if description:
      self.set_attribute("otel.status_description", description)

  def record_exception(self, exc: BaseException) -> None:
    self.status = "ERROR"
    self.set_attribute("exception.type", type(exc).__name__)
    self.set_attribute("exception.message", str(exc))

  def __enter__(self) -> "_FallbackSpan":
    self._prev_trace_token = _ACTIVE_TRACE_ID.set(self.trace_id)
    self._prev_span_token = _ACTIVE_SPAN_ID.set(self.span_id)
    return self

  def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
    if exc_val is not None:
      self.record_exception(exc_val)
    self.end_time_ns = time.time_ns()
    _RECORDED_SPANS.append({
        "name": self.name,
        "trace_id": self.trace_id,
        "span_id": self.span_id,
        "parent_span_id": self.parent_span_id,
        "start_time_ns": self.start_time_ns,
        "end_time_ns": self.end_time_ns,
        "duration_ms": round(
            (self.end_time_ns - self.start_time_ns) / 1_000_000.0, 3
        ),
        "attributes": scrub_pii(self.attributes),
        "status": self.status,
    })
    if self._prev_span_token is not None:
      _ACTIVE_SPAN_ID.reset(self._prev_span_token)
    if self._prev_trace_token is not None:
      _ACTIVE_TRACE_ID.reset(self._prev_trace_token)


class _UnifiedTracer:
  """Wraps OpenTelemetry Tracer and fallback span creation seamlessly."""

  def __init__(self, service_name: str = "kuwait-cal-executive-agent") -> None:
    self.service_name = service_name
    self._otel_tracer = None
    if _HAS_OTEL_SDK and otel_trace is not None and TracerProvider is not None:
      resource = Resource.create({"service.name": service_name})
      provider = TracerProvider(resource=resource)
      provider.add_span_processor(
          SimpleSpanProcessor(PiiRedactingSpanExporter())
      )
      otel_trace.set_tracer_provider(provider)
      self._otel_tracer = otel_trace.get_tracer(service_name)

  def start_as_current_span(
      self, name: str, attributes: dict[str, Any] | None = None
  ) -> _FallbackSpan:
    parent_trace_id = _ACTIVE_TRACE_ID.get()
    parent_span_id = _ACTIVE_SPAN_ID.get() or None
    trace_id = parent_trace_id or secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    merged_attrs = {"service.name": self.service_name, **(attributes or {})}
    return _FallbackSpan(
        name=name,
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        attributes=merged_attrs,
    )


_TRACER = _UnifiedTracer()


def get_tracer() -> _UnifiedTracer:
  """Returns the global OpenTelemetry-compatible tracer."""
  return _TRACER


def get_current_trace_And_span_id() -> tuple[str, str]:
  """Returns the active (trace_id, span_id) pair for log correlation."""
  trace_id = _ACTIVE_TRACE_ID.get() or "00000000000000000000000000000000"
  span_id = _ACTIVE_SPAN_ID.get() or "0000000000000000"
  return (trace_id, span_id)


def get_recorded_spans() -> list[dict[str, Any]]:
  """Returns all recorded OpenTelemetry spans (with PII scrubbed)."""
  return list(_RECORDED_SPANS)


def clear_recorded_spans() -> None:
  """Clears recorded spans buffer."""
  _RECORDED_SPANS.clear()


def traced_node(
    node_name: str,
    intent: str,
    *,
    model: str | None = None,
    model_tier: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
  """Decorator instrumenting an ADK workflow node with OTel spans & Intent/Outcome logs."""

  def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
    if inspect.iscoroutinefunction(func):

      @functools.wraps(func)
      async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        attrs = {
            "adk.node.name": node_name,
            "adk.intent": intent,
            "gen_ai.system": "google_adk",
        }
        if model:
          attrs["gen_ai.request.model"] = model
        if model_tier:
          attrs["adk.model_tier"] = model_tier

        with _TRACER.start_as_current_span(
            f"node.{node_name}", attributes=attrs
        ) as span:
          log_intent(
              component="workflow_node",
              action=node_name,
              intent=intent,
              model=model,
              model_tier=model_tier,
          )
          try:
            result = await func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            route = getattr(result, "route", None)
            state_keys = (
                list(result.state.keys())
                if getattr(result, "state", None)
                else []
            )
            outcome_summary = (
                f"Completed node {node_name}; updated_state_keys={state_keys}"
                + (f", route={route}" if route else "")
            )
            span.set_attribute("adk.outcome", outcome_summary)
            span.set_attribute("adk.state_keys", ",".join(state_keys))
            if route:
              span.set_attribute("adk.route", str(route))
            log_outcome(
                component="workflow_node",
                action=node_name,
                outcome=outcome_summary,
                status="SUCCESS",
                latency_ms=elapsed_ms,
                model=model,
                metrics={"state_keys_updated": len(state_keys)},
            )
            return result
          except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            span.record_exception(exc)
            log_outcome(
                component="workflow_node",
                action=node_name,
                outcome=f"Node {node_name} raised {type(exc).__name__}",
                status="ERROR",
                latency_ms=elapsed_ms,
                model=model,
                error=str(exc),
            )
            raise

      return async_wrapper

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
      start = time.perf_counter()
      attrs = {
          "adk.node.name": node_name,
          "adk.intent": intent,
          "gen_ai.system": "google_adk",
      }
      if model:
        attrs["gen_ai.request.model"] = model
      with _TRACER.start_as_current_span(
          f"node.{node_name}", attributes=attrs
      ) as span:
        log_intent(
            component="workflow_node",
            action=node_name,
            intent=intent,
            model=model,
            model_tier=model_tier,
        )
        try:
          result = func(*args, **kwargs)
          elapsed_ms = (time.perf_counter() - start) * 1000.0
          span.set_attribute("adk.outcome", f"Completed {node_name}")
          log_outcome(
              component="workflow_node",
              action=node_name,
              outcome=f"Completed {node_name}",
              status="SUCCESS",
              latency_ms=elapsed_ms,
              model=model,
          )
          return result
        except Exception as exc:
          elapsed_ms = (time.perf_counter() - start) * 1000.0
          span.record_exception(exc)
          log_outcome(
              component="workflow_node",
              action=node_name,
              outcome=f"Failed {node_name}",
              status="ERROR",
              latency_ms=elapsed_ms,
              error=str(exc),
          )
          raise

    return sync_wrapper

  return decorator


def traced_tool(
    tool_name: str, intent: str
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
  """Decorator instrumenting an ADK tool with OTel spans, PII redaction, and Intent/Outcome logs."""

  def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
      start = time.perf_counter()
      safe_kwargs = scrub_pii(kwargs)
      attrs = {
          "adk.tool.name": tool_name,
          "adk.intent": intent,
          "adk.tool.args": str(safe_kwargs),
      }
      with _TRACER.start_as_current_span(
          f"tool.{tool_name}", attributes=attrs
      ) as span:
        log_intent(
            component="tool",
            action=tool_name,
            intent=intent,
            metadata={"kwargs": safe_kwargs},
        )
        try:
          result = func(*args, **kwargs)
          elapsed_ms = (time.perf_counter() - start) * 1000.0
          status = "SUCCESS"
          if isinstance(result, dict):
            raw_status = str(result.get("status", "SUCCESS")).upper()
            if "BLOCKED" in raw_status:
              status = "BLOCKED"
            elif raw_status in ("ERROR", "FAILED"):
              status = "ERROR"
          outcome_desc = (
              f"Tool {tool_name} finished with status={status}"
          )
          span.set_attribute("adk.outcome", outcome_desc)
          span.set_attribute("adk.tool.status", status)
          log_outcome(
              component="tool",
              action=tool_name,
              outcome=outcome_desc,
              status=status,
              latency_ms=elapsed_ms,
          )
          return result
        except Exception as exc:
          elapsed_ms = (time.perf_counter() - start) * 1000.0
          span.record_exception(exc)
          log_outcome(
              component="tool",
              action=tool_name,
              outcome=f"Tool {tool_name} raised {type(exc).__name__}",
              status="ERROR",
              latency_ms=elapsed_ms,
              error=str(exc),
          )
          raise

    return wrapper

  return decorator
