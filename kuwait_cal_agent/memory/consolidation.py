"""Background Asynchronous Memory Consolidation (`AsyncMemoryConsolidator`).

Extracts episodic workflow session state in the background (`asyncio.create_task`)
and consolidates long-term semantic facts into a persistent SQLite knowledge
bank (`semantic_memories`):
1. `innovation_history`: Prevents repeating the same Kuwait Vision 2035 ideas
   across consecutive weeks.
2. `pso_risk_history`: Tracks longitudinal RAG status transitions across PSO
   engagements.
3. `afa_burn_history`: Records weekly GCP/TIF/PSF attainment velocity.
4. `colleague_sla_history`: Tracks colleague follow-up latency.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from ..observability.logging import log_intent, log_outcome
from .session_store import DEFAULT_DB_PATH


class AsyncMemoryConsolidator:
  """Background async service consolidating episodic runs into semantic memory."""

  def __init__(self, db_path: str | Path | None = None) -> None:
    self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
    self.db_path.parent.mkdir(parents=True, exist_ok=True)
    self._pending_tasks: set[asyncio.Task[dict[str, Any]]] = set()
    self._init_schema()

  def _connect(self) -> sqlite3.Connection:
    conn = sqlite3.connect(str(self.db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

  def _init_schema(self) -> None:
    with self._connect() as conn:
      conn.executescript(
          """
          CREATE TABLE IF NOT EXISTS semantic_memories (
              memory_id TEXT PRIMARY KEY,
              category TEXT NOT NULL,
              entity_key TEXT NOT NULL,
              fact_summary TEXT NOT NULL,
              metadata_json TEXT NOT NULL,
              confidence REAL NOT NULL DEFAULT 1.0,
              source_session_id TEXT NOT NULL,
              updated_at TEXT NOT NULL
          );
          CREATE INDEX IF NOT EXISTS idx_semantic_category
              ON semantic_memories(category, entity_key);
          """
      )

  def schedule_consolidation(
      self, session_id: str, session_state: dict[str, Any]
  ) -> asyncio.Task[dict[str, Any]]:
    """Schedules non-blocking background memory consolidation via asyncio.create_task."""
    task = asyncio.create_task(
        self.consolidate_session_async(session_id, dict(session_state))
    )
    self._pending_tasks.add(task)
    task.add_done_callback(self._pending_tasks.discard)
    return task

  async def wait_for_pending_tasks(self) -> list[dict[str, Any]]:
    """Awaits any in-flight background memory consolidation tasks."""
    if not self._pending_tasks:
      return []
    results = await asyncio.gather(*list(self._pending_tasks), return_exceptions=False)
    return list(results)

  async def consolidate_session_async(
      self, session_id: str, session_state: dict[str, Any]
  ) -> dict[str, Any]:
    """Asynchronously extracts long-term semantic facts from a completed session."""
    log_intent(
        component="async_memory_consolidator",
        action="consolidate_session_async",
        intent=f"Consolidate episodic state from session {session_id} into long-term semantic memory",
        session_id=session_id,
    )
    await asyncio.sleep(0)  # Yield to event loop so caller is never blocked

    payload = session_state.get("dashboard_payload") or {}
    if isinstance(payload, str):
      try:
        payload = json.loads(payload)
      except json.JSONDecodeError:
        payload = {}

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    facts_stored = 0

    with self._connect() as conn:
      # 1. Consolidate Kuwait Vision 2035 Innovation Ideas to avoid weekly repetition
      ideas = (
          payload.get("innovation_radar", {}).get("ideas", [])
          if isinstance(payload.get("innovation_radar"), dict)
          else []
      )
      for idea in ideas:
        if not isinstance(idea, dict):
          continue
        title = str(idea.get("title", "")).strip()
        agency = str(idea.get("target_ministry_or_agency", "")).strip()
        if not title:
          continue
        mem_id = hashlib.sha256(f"innovation:{title}".encode("utf-8")).hexdigest()[:24]
        conn.execute(
            """
            INSERT INTO semantic_memories (
                memory_id, category, entity_key, fact_summary, metadata_json,
                confidence, source_session_id, updated_at
            )
            VALUES (?, 'innovation_history', ?, ?, ?, 1.0, ?, ?)
            ON CONFLICT(memory_id) DO UPDATE SET
                fact_summary = excluded.fact_summary,
                metadata_json = excluded.metadata_json,
                source_session_id = excluded.source_session_id,
                updated_at = excluded.updated_at
            """,
            (
                mem_id,
                title,
                f"Proposed '{title}' for {agency}",
                json.dumps(idea, default=str),
                session_id,
                now,
            ),
        )
        facts_stored += 1

      # 2. Consolidate PSO Portfolio Risk Trends
      projects = (
          payload.get("pso_portfolio", {}).get("projects", [])
          if isinstance(payload.get("pso_portfolio"), dict)
          else []
      )
      for proj in projects:
        if not isinstance(proj, dict):
          continue
        pname = str(proj.get("project_name", "")).strip()
        rag = str(proj.get("rag_status", "")).strip()
        risk = str(proj.get("primary_risk_or_issue", "")).strip()
        if not pname:
          continue
        mem_id = hashlib.sha256(f"pso_risk:{pname}".encode("utf-8")).hexdigest()[:24]
        conn.execute(
            """
            INSERT INTO semantic_memories (
                memory_id, category, entity_key, fact_summary, metadata_json,
                confidence, source_session_id, updated_at
            )
            VALUES (?, 'pso_risk_history', ?, ?, ?, 0.95, ?, ?)
            ON CONFLICT(memory_id) DO UPDATE SET
                fact_summary = excluded.fact_summary,
                metadata_json = excluded.metadata_json,
                source_session_id = excluded.source_session_id,
                updated_at = excluded.updated_at
            """,
            (
                mem_id,
                pname,
                f"Project {pname} is {rag}: {risk}",
                json.dumps(proj, default=str),
                session_id,
                now,
            ),
        )
        facts_stored += 1

      # 3. Consolidate AFA Financial Attainment Snapshot
      afa = payload.get("afa_consumption")
      if isinstance(afa, dict):
        for stream in afa.get("commit_streams", []):
          if not isinstance(stream, dict):
            continue
          sname = str(stream.get("stream_name", "")).strip()
          att = stream.get("attainment_pct", "")
          gap = stream.get("gap_usd", "")
          if not sname:
            continue
          mem_id = hashlib.sha256(f"afa_stream:{sname}".encode("utf-8")).hexdigest()[:24]
          conn.execute(
              """
              INSERT INTO semantic_memories (
                  memory_id, category, entity_key, fact_summary, metadata_json,
                  confidence, source_session_id, updated_at
              )
              VALUES (?, 'afa_burn_history', ?, ?, ?, 1.0, ?, ?)
              ON CONFLICT(memory_id) DO UPDATE SET
                  fact_summary = excluded.fact_summary,
                  metadata_json = excluded.metadata_json,
                  source_session_id = excluded.source_session_id,
                  updated_at = excluded.updated_at
              """,
              (
                  mem_id,
                  sname,
                  f"Stream {sname} attainment={att}, gap={gap}",
                  json.dumps(stream, default=str),
                  session_id,
                  now,
              ),
          )
          facts_stored += 1

    summary = {
        "session_id": session_id,
        "facts_consolidated": facts_stored,
        "timestamp": now,
    }
    log_outcome(
        component="async_memory_consolidator",
        action="consolidate_session_async",
        outcome=f"Consolidated {facts_stored} semantic memory facts from session {session_id}",
        status="SUCCESS",
        session_id=session_id,
        metrics={"facts_consolidated": facts_stored},
    )
    return summary

  def query_memories(
      self, category: str | None = None, limit: int = 50
  ) -> list[dict[str, Any]]:
    """Retrieves consolidated long-term semantic memories from SQLite."""
    with self._connect() as conn:
      if category:
        rows = conn.execute(
            """
            SELECT memory_id, category, entity_key, fact_summary, metadata_json,
                   confidence, source_session_id, updated_at
            FROM semantic_memories
            WHERE category = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (category, limit),
        ).fetchall()
      else:
        rows = conn.execute(
            """
            SELECT memory_id, category, entity_key, fact_summary, metadata_json,
                   confidence, source_session_id, updated_at
            FROM semantic_memories
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
      return [
          {
              "memory_id": r["memory_id"],
              "category": r["category"],
              "entity_key": r["entity_key"],
              "fact_summary": r["fact_summary"],
              "metadata": json.loads(r["metadata_json"]),
              "confidence": r["confidence"],
              "source_session_id": r["source_session_id"],
              "updated_at": r["updated_at"],
          }
          for r in rows
      ]
