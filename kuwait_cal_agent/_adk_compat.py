"""Canonical Google ADK 2.x imports with persistent SQLite session & OTel tracing support.

When `google-adk` and `pydantic` are installed in the Python environment, this
module re-exports the canonical classes from `google.adk`, `google.adk.agents`,
`google.adk.apps`, `google.adk.events`, `google.adk.runners`,
`google.adk.sessions`, and `google.adk.workflow`.

When invoked in minimal environments, it provides API-compatible classes backed
by `SqliteSessionService` (persistent SQLite database session storage),
`ContextCompactor` (event history compaction), and OpenTelemetry span tracing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import inspect
import time
from typing import Any, AsyncIterator, Callable
import uuid

from .memory.compaction import ContextCompactor, EventsCompactionConfig
from .memory.session_store import SqliteSessionService
from .observability.logging import log_intent, log_outcome
from .observability.telemetry import get_tracer

try:
  from pydantic import BaseModel, Field  # type: ignore
  HAS_PYDANTIC = True
except ImportError:
  HAS_PYDANTIC = False

  def Field(
      default: Any = None,
      *,
      default_factory: Callable[[], Any] | None = None,
      **kwargs: Any,
  ) -> Any:
    del kwargs
    if default_factory is not None:
      return field(default_factory=default_factory)
    return default

  class BaseModel:
    """Lightweight BaseModel fallback when pydantic is not yet installed."""

    def __init__(self, **kwargs: Any) -> None:
      annotations = getattr(self.__class__, "__annotations__", {})
      for k in annotations:
        if k in kwargs:
          setattr(self, k, kwargs[k])
        elif hasattr(self.__class__, k):
          val = getattr(self.__class__, k)
          setattr(self, k, val() if callable(val) else val)
        else:
          setattr(self, k, None)
      for k, v in kwargs.items():
        setattr(self, k, v)

    @classmethod
    def model_validate(cls, data: Any) -> "BaseModel":
      if isinstance(data, cls):
        return data
      if isinstance(data, dict):
        return cls(**data)
      raise TypeError(f"Cannot validate {type(data)} as {cls.__name__}")

    def model_dump(self, exclude_none: bool = False) -> dict[str, Any]:
      out: dict[str, Any] = {}
      for k, v in self.__dict__.items():
        if exclude_none and v is None:
          continue
        out[k] = self._serialize(v, exclude_none=exclude_none)
      return out

    @classmethod
    def _serialize(cls, value: Any, exclude_none: bool = False) -> Any:
      if isinstance(value, BaseModel):
        return value.model_dump(exclude_none=exclude_none)
      if isinstance(value, list):
        return [cls._serialize(i, exclude_none=exclude_none) for i in value]
      if isinstance(value, dict):
        return {
            k: cls._serialize(v, exclude_none=exclude_none)
            for k, v in value.items()
        }
      return value


try:
  from google.adk import Agent, Context, Event, Runner, Workflow  # type: ignore
  from google.adk.agents import LlmAgent  # type: ignore
  from google.adk.apps import App, ResumabilityConfig  # type: ignore
  from google.adk.events import EventActions, RequestInput  # type: ignore
  from google.adk.runners import InMemoryRunner  # type: ignore
  from google.adk.workflow import (  # type: ignore
      DEFAULT_ROUTE,
      Edge,
      FunctionNode,
      JoinNode,
      START,
      node,
  )
  from google.genai import types as genai_types  # type: ignore
  HAS_GOOGLE_ADK = True
except ImportError:
  HAS_GOOGLE_ADK = False
  START = "START"
  DEFAULT_ROUTE = "__DEFAULT__"

  @dataclass
  class NodeInfo:
    path: str

  @dataclass
  class FunctionCall:
    id: str
    name: str
    args: dict[str, Any] = field(default_factory=dict)

  @dataclass
  class FunctionResponse:
    id: str
    name: str
    response: dict[str, Any] = field(default_factory=dict)

  @dataclass
  class Part:
    text: str | None = None
    function_call: FunctionCall | None = None
    function_response: FunctionResponse | None = None

    @classmethod
    def from_text(cls, text: str) -> "Part":
      return cls(text=text)

  @dataclass
  class Content:
    role: str = "user"
    parts: list[Part] = field(default_factory=list)

  class _GenaiTypesNamespace:
    Part = Part
    Content = Content
    FunctionCall = FunctionCall
    FunctionResponse = FunctionResponse

  genai_types = _GenaiTypesNamespace()

  @dataclass
  class EventActions:
    state_delta: dict[str, Any] = field(default_factory=dict)

  class Event:
    """ADK-compatible Event carrying message, output, route, and state."""

    def __init__(
        self,
        *,
        message: str | None = None,
        output: Any = None,
        route: str | None = None,
        state: dict[str, Any] | None = None,
        author: str = "workflow",
        node_info: NodeInfo | None = None,
        content: Content | None = None,
    ) -> None:
      self.output = (
          output.model_dump() if isinstance(output, BaseModel) else output
      )
      self.route = route
      self.state = state or {}
      self.actions = EventActions(state_delta=dict(self.state))
      self.author = author
      self.node_info = node_info
      if content is not None:
        self.content = content
      elif message is not None:
        self.content = Content(role="model", parts=[Part(text=message)])
      else:
        self.content = None

    def get_function_calls(self) -> list[FunctionCall]:
      if not self.content or not self.content.parts:
        return []
      return [
          p.function_call
          for p in self.content.parts
          if p.function_call is not None
      ]

  class RequestInput:
    """ADK-compatible RequestInput for Human-in-the-Loop workflow pauses."""

    def __init__(
        self,
        *,
        interrupt_id: str | None = None,
        message: str | None = None,
        payload: Any = None,
        response_schema: Any = None,
    ) -> None:
      self.interrupt_id = interrupt_id or str(uuid.uuid4())
      self.message = message
      self.payload = (
          payload.model_dump() if isinstance(payload, BaseModel) else payload
      )
      self.response_schema = response_schema

  class Context:
    """ADK-compatible execution context holding session state & resume_inputs."""

    def __init__(
        self,
        state: dict[str, Any] | None = None,
        resume_inputs: dict[str, Any] | None = None,
    ) -> None:
      self.state: dict[str, Any] = state if state is not None else {}
      self.resume_inputs: dict[str, Any] = (
          resume_inputs if resume_inputs is not None else {}
      )

  class FunctionNode:
    def __init__(
        self,
        func: Callable[..., Any],
        name: str | None = None,
        rerun_on_resume: bool = False,
    ) -> None:
      self.func = func
      self.name = name or func.__name__
      self.rerun_on_resume = rerun_on_resume

  def node(
      func: Callable[..., Any] | None = None,
      *,
      name: str | None = None,
      parallel_worker: bool = False,
      rerun_on_resume: bool = False,
  ) -> Any:
    def _wrap(f: Callable[..., Any]) -> Callable[..., Any]:
      setattr(f, "_adk_node_name", name or f.__name__)
      setattr(f, "_adk_parallel_worker", parallel_worker)
      setattr(f, "_adk_rerun_on_resume", rerun_on_resume)
      return f

    return _wrap(func) if func is not None else _wrap

  class JoinNode:
    """Synchronizes multiple incoming branches into a dict keyed by node name."""

    def __init__(self, name: str) -> None:
      self.name = name

  class LlmAgent:
    """ADK LlmAgent node with support for strategic model routing, output_schema, and tools."""

    DEFAULT_MODEL = "gemini-3.8-flash"

    def __init__(
        self,
        *,
        name: str,
        model: str = DEFAULT_MODEL,
        instruction: str | Callable[[Context], str] = "",
        description: str = "",
        tools: list[Callable[..., Any]] | None = None,
        output_schema: Any = None,
        output_key: str | None = None,
        mode: str = "single_turn",
        include_contents: str = "default",
        fallback_handler: Callable[[Context, Any], Any] | None = None,
    ) -> None:
      self.name = name
      self.model = model
      self.instruction = instruction
      self.description = description
      self.tools = tools or []
      self.output_schema = output_schema
      self.output_key = output_key
      self.mode = mode
      self.include_contents = include_contents
      self.fallback_handler = fallback_handler

  Agent = LlmAgent

  @dataclass
  class Edge:
    source: Any
    target: Any

  @dataclass
  class ResumabilityConfig:
    is_resumable: bool = True

  class App:
    def __init__(
        self,
        *,
        name: str,
        root_agent: "Workflow",
        resumability_config: ResumabilityConfig | None = None,
        events_compaction_config: EventsCompactionConfig | None = None,
    ) -> None:
      self.name = name
      self.root_agent = root_agent
      self.resumability_config = resumability_config or ResumabilityConfig(
          is_resumable=True
      )
      self.events_compaction_config = (
          events_compaction_config or EventsCompactionConfig()
      )

  class Workflow:
    """ADK 2.x Graph Workflow orchestrating FunctionNodes, LlmAgents, JoinNodes, and routed edges."""

    def __init__(
        self,
        *,
        name: str,
        edges: list[tuple[Any, ...]],
        input_schema: Any = str,
        description: str = "",
    ) -> None:
      self.name = name
      self.edges = edges
      self.input_schema = input_schema
      self.description = description

  @dataclass
  class Session:
    id: str
    app_name: str
    user_id: str
    state: dict[str, Any] = field(default_factory=dict)
    pending_interrupt: tuple[Any, RequestInput] | None = None
    pending_node_input: Any = None

  class DatabaseSessionService:
    """Persistent SQLite-backed SessionService replacing volatile in-memory dicts."""

    def __init__(self, db_path: str | None = None) -> None:
      self._sqlite = SqliteSessionService(db_path=db_path)
      self._active_sessions: dict[tuple[str, str, str], Session] = {}

    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> Session:
      sid = session_id or str(uuid.uuid4())
      init_state = dict(state or {})
      init_state["session_id"] = sid
      persisted = self._sqlite.create_or_load_session(
          sid, app_name=app_name, user_id=user_id, initial_state=init_state
      )
      sess = Session(
          id=sid, app_name=app_name, user_id=user_id, state=persisted
      )
      self._active_sessions[(app_name, user_id, sid)] = sess
      return sess

    async def get_session(
        self, *, app_name: str, user_id: str, session_id: str
    ) -> Session:
      key = (app_name, user_id, session_id)
      db_state = self._sqlite.get_session_state(session_id)
      if key in self._active_sessions:
        sess = self._active_sessions[key]
        sess.state.update(db_state)
        return sess
      sess = Session(
          id=session_id, app_name=app_name, user_id=user_id, state=db_state
      )
      self._active_sessions[key] = sess
      return sess

    def persist_step(
        self,
        session: Session,
        state_delta: dict[str, Any],
        *,
        node_name: str,
        step_index: int,
        route: str | None = None,
    ) -> None:
      updated = self._sqlite.update_session_state(
          session.id,
          state_delta,
          node_name=node_name,
          step_index=step_index,
          route=route,
      )
      session.state.update(updated)

  # Alias for compatibility with tests importing InMemorySessionService
  InMemorySessionService = DatabaseSessionService

  class InMemoryRunner:
    """Executes an ADK Workflow or App backed by persistent `DatabaseSessionService`, `ContextCompactor`, and OpenTelemetry tracing."""

    def __init__(
        self,
        *,
        agent: Workflow | None = None,
        app: App | None = None,
        app_name: str = "kuwait_cal_app",
        session_service: DatabaseSessionService | None = None,
    ) -> None:
      if app is not None:
        self.app = app
        self.agent = app.root_agent
        self.app_name = app.name
      elif agent is not None:
        self.agent = agent
        self.app_name = app_name
        self.app = App(name=app_name, root_agent=agent)
      else:
        raise ValueError("Either `agent` or `app` must be provided to Runner.")
      self.session_service = session_service or DatabaseSessionService()
      self.compactor = ContextCompactor(self.app.events_compaction_config)

    @staticmethod
    def _node_name(n: Any) -> str:
      if isinstance(n, str):
        return n
      if hasattr(n, "name"):
        return str(n.name)
      if hasattr(n, "_adk_node_name"):
        return str(getattr(n, "_adk_node_name"))
      return getattr(n, "__name__", str(n))

    def _build_adj(
        self,
    ) -> tuple[dict[str, list[Any]], dict[str, Any], dict[str, list[str]]]:
      adj: dict[str, list[Any]] = {}
      nodes_by_name: dict[str, Any] = {}
      join_preds: dict[str, list[str]] = {}

      def _register(item: Any) -> None:
        if isinstance(item, (tuple, list)):
          for sub in item:
            _register(sub)
        elif isinstance(item, dict):
          for sub in item.values():
            _register(sub)
        elif not isinstance(item, str):
          nodes_by_name[self._node_name(item)] = item

      for edge in self.agent.edges:
        for item in edge:
          _register(item)
        for i in range(len(edge) - 1):
          src, dst = edge[i], edge[i + 1]
          if isinstance(src, (tuple, list)) and isinstance(dst, JoinNode):
            preds = [self._node_name(s) for s in src]
            join_preds[dst.name] = preds
            for s in src:
              adj.setdefault(self._node_name(s), []).append(dst)
          elif isinstance(src, (tuple, list)):
            for s in src:
              adj.setdefault(self._node_name(s), []).append(dst)
          else:
            adj.setdefault(self._node_name(src), []).append(dst)
      return adj, nodes_by_name, join_preds

    async def _invoke_single_node(
        self,
        node_obj: Any,
        ctx: Context,
        node_input: Any,
    ) -> list[Event | RequestInput]:
      n_name = self._node_name(node_obj)
      n_info = NodeInfo(path=f"{self.agent.name}@1/{n_name}@1")

      if isinstance(node_obj, LlmAgent):
        start_t = time.perf_counter()
        tracer = get_tracer()
        with tracer.start_as_current_span(
            f"llm_agent.{node_obj.name}",
            attributes={
                "gen_ai.system": "google_adk",
                "gen_ai.request.model": node_obj.model,
                "adk.agent.name": node_obj.name,
                "adk.intent": node_obj.description or node_obj.name,
            },
        ) as span:
          log_intent(
              component="llm_agent",
              action=node_obj.name,
              intent=node_obj.description or f"Execute LlmAgent {node_obj.name}",
              model=node_obj.model,
              session_id=str(ctx.state.get("session_id", "")),
          )
          if node_obj.fallback_handler is not None:
            raw = node_obj.fallback_handler(ctx, node_input)
            if inspect.isawaitable(raw):
              raw = await raw
          else:
            raise RuntimeError(
                f"LlmAgent '{node_obj.name}' requires google-adk or a fallback_handler."
            )
          payload = raw.model_dump() if isinstance(raw, BaseModel) else raw
          state_delta = (
              {node_obj.output_key: payload} if node_obj.output_key else {}
          )
          ctx.state.update(state_delta)
          elapsed_ms = (time.perf_counter() - start_t) * 1000.0
          span.set_attribute(
              "adk.outcome",
              f"Generated {node_obj.output_key or node_obj.name} via {node_obj.model}",
          )
          log_outcome(
              component="llm_agent",
              action=node_obj.name,
              outcome=f"Completed {node_obj.name} using model {node_obj.model}",
              status="SUCCESS",
              latency_ms=elapsed_ms,
              model=node_obj.model,
              session_id=str(ctx.state.get("session_id", "")),
          )
          return [
              Event(
                  output=payload,
                  state=state_delta,
                  author=self.agent.name,
                  node_info=n_info,
              )
          ]

      fn = node_obj.func if isinstance(node_obj, FunctionNode) else node_obj
      sig = inspect.signature(fn)
      params = list(sig.parameters.keys())
      call_args: list[Any] = []
      if len(params) >= 2:
        call_args = [ctx, node_input]
      elif len(params) == 1:
        if params[0] in ("ctx", "context"):
          call_args = [ctx]
        else:
          call_args = [node_input]

      res = fn(*call_args)
      items: list[Any] = []
      if inspect.isasyncgen(res):
        async for item in res:
          items.append(item)
      elif inspect.isgenerator(res):
        for item in res:
          items.append(item)
      else:
        if inspect.isawaitable(res):
          res = await res
        items.append(res)

      normalized: list[Event | RequestInput] = []
      for item in items:
        if isinstance(item, RequestInput):
          normalized.append(item)
        elif isinstance(item, Event):
          item.author = self.agent.name
          item.node_info = n_info
          if item.state:
            ctx.state.update(item.state)
          normalized.append(item)
        else:
          val = item.model_dump() if isinstance(item, BaseModel) else item
          normalized.append(
              Event(output=val, author=self.agent.name, node_info=n_info)
          )
      return normalized

    async def run_async(
        self,
        *,
        user_id: str,
        session_id: str,
        new_message: Content,
    ) -> AsyncIterator[Event]:
      session = await self.session_service.get_session(
          app_name=self.app_name, user_id=user_id, session_id=session_id
      )
      adj, _, join_preds = self._build_adj()
      ctx = Context(state=session.state)
      step_idx = 0

      tracer = get_tracer()
      with tracer.start_as_current_span(
          f"workflow.{self.agent.name}",
          attributes={
              "adk.workflow.name": self.agent.name,
              "adk.session.id": session_id,
              "adk.user.id": user_id,
          },
      ):
        if session.pending_interrupt is not None:
          interrupted_node, req_input = session.pending_interrupt
          session.pending_interrupt = None
          resume_val: Any = None
          if new_message.parts and new_message.parts[0].function_response:
            resp_dict = new_message.parts[0].function_response.response
            resume_val = resp_dict.get("result", resp_dict)
          ctx.resume_inputs[req_input.interrupt_id] = resume_val
          queue: list[tuple[Any, Any]] = [
              (interrupted_node, session.pending_node_input)
          ]
        else:
          initial_text = ""
          if new_message.parts and new_message.parts[0].text is not None:
            initial_text = new_message.parts[0].text
          queue = [(START, initial_text)]

        join_buffers: dict[str, dict[str, Any]] = {}

        while queue:
          current_node, current_input = queue.pop(0)
          c_name = self._node_name(current_node)
          step_idx += 1

          if c_name == START:
            for target in adj.get(START, []):
              if isinstance(target, (tuple, list)):
                for t in target:
                  queue.append((t, current_input))
              else:
                queue.append((target, current_input))
            continue

          if isinstance(current_node, JoinNode):
            merged = join_buffers.pop(current_node.name, current_input)
            self.session_service._sqlite.save_checkpoint(
                session_id, current_node.name, {"merged_keys": list(merged.keys())}
            )
            j_info = NodeInfo(path=f"{self.agent.name}@1/{current_node.name}@1")
            j_event = Event(
                output=merged, author=self.agent.name, node_info=j_info
            )
            yield j_event
            for target in adj.get(current_node.name, []):
              if isinstance(target, (tuple, list)):
                for t in target:
                  queue.append((t, merged))
              else:
                queue.append((target, merged))
            continue

          emitted = await self._invoke_single_node(
              current_node, ctx, current_input
          )
          node_output: Any = None
          chosen_route: str | None = None

          for item in emitted:
            if isinstance(item, RequestInput):
              session.pending_interrupt = (current_node, item)
              session.pending_node_input = current_input
              self.session_service._sqlite.save_checkpoint(
                  session_id,
                  f"interrupt_{item.interrupt_id}",
                  {"node": c_name, "message": item.message},
              )
              fc = FunctionCall(
                  id=item.interrupt_id,
                  name="adk_request_input",
                  args={"message": item.message, "payload": item.payload},
              )
              yield Event(
                  author=self.agent.name,
                  node_info=NodeInfo(path=f"{self.agent.name}@1/{c_name}@1"),
                  content=Content(role="model", parts=[Part(function_call=fc)]),
              )
              return
            else:
              if item.output is not None:
                node_output = item.output
              if item.route is not None:
                chosen_route = item.route
              if item.state:
                self.session_service.persist_step(
                    session,
                    item.state,
                    node_name=c_name,
                    step_index=step_idx,
                    route=chosen_route,
                )
              yield item

          for target in adj.get(c_name, []):
            if isinstance(target, JoinNode):
              buf = join_buffers.setdefault(target.name, {})
              buf[c_name] = node_output
              expected = join_preds.get(target.name, [])
              if all(p in buf for p in expected):
                queue.append((target, dict(buf)))
            elif isinstance(target, dict):
              route_key = (
                  chosen_route if chosen_route in target else DEFAULT_ROUTE
              )
              if route_key in target:
                queue.append((target[route_key], node_output))
            elif isinstance(target, (tuple, list)):
              for t in target:
                queue.append((t, node_output))
            else:
              queue.append((target, node_output))

        # Compact session event history at the end of the turn
        raw_events = self.session_service._sqlite.get_session_events(session_id)
        _, hist_metrics = self.compactor.compact_event_history(raw_events)
        self.session_service.persist_step(
            session,
            {"event_history_compaction": hist_metrics},
            node_name="event_history_compactor",
            step_index=step_idx + 1,
        )

  Runner = InMemoryRunner
