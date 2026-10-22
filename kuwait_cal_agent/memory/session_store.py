"""Persistent SQLite Database Session Store (`DatabaseSessionService`).

Replaces volatile in-memory state dictionaries with a durable SQLite database
supporting session state persistence, event history journaling, and resumable
workflow checkpoints (`RequestInput` human-in-the-loop interrupts).
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import sqlite3
from typing import Any

from ..observability.logging import log_intent, log_outcome

try:
  from google.adk.sessions import DatabaseSessionService as AdkDatabaseSessionService  # type: ignore
  _HAS_ADK_DB_SESSION = True
except ImportError:
  AdkDatabaseSessionService = None  # type: ignore
  _HAS_ADK_DB_SESSION = False

DEFAULT_DB_PATH = Path(
    os.environ.get(
        "CAL_SESSION_DB_PATH",
        str(Path(__file__).resolve().parents[2] / "kuwait_cal_sessions.db"),
    )
)


class SqliteSessionService:
  """Persistent SQLite-backed session & checkpoint service for ADK workflows."""

  def __init__(self, db_path: str | Path | None = None) -> None:
    self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
    self.db_path.parent.mkdir(parents=True, exist_ok=True)
    self.db_url = f"sqlite:///{self.db_path}"
    self._init_schema()

  def _connect(self) -> sqlite3.Connection:
    conn = sqlite3.connect(str(self.db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

  def _init_schema(self) -> None:
    with self._connect() as conn:
      conn.executescript(
          """
          CREATE TABLE IF NOT EXISTS sessions (
              session_id TEXT PRIMARY KEY,
              app_name TEXT NOT NULL,
              user_id TEXT NOT NULL,
              state_json TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'ACTIVE',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
          );

          CREATE TABLE IF NOT EXISTS session_events (
              event_id INTEGER PRIMARY KEY AUTOINCREMENT,
              session_id TEXT NOT NULL,
              step_index INTEGER NOT NULL,
              node_name TEXT NOT NULL,
              route TEXT,
              event_state_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY (session_id) REFERENCES sessions(session_id)
          );

          CREATE TABLE IF NOT EXISTS workflow_checkpoints (
              session_id TEXT NOT NULL,
              checkpoint_key TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY (session_id, checkpoint_key)
          );
          """
      )

  def create_or_load_session(
      self,
      session_id: str,
      *,
      app_name: str = "kuwait_cal_executive_dashboard",
      user_id: str = "clappaert",
      initial_state: dict[str, Any] | None = None,
  ) -> dict[str, Any]:
    """Creates a new persistent session or loads existing state from SQLite."""
    log_intent(
        component="database_session_service",
        action="create_or_load_session",
        intent=f"Initialize or resume persistent SQLite session {session_id}",
        session_id=session_id,
    )
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with self._connect() as conn:
      row = conn.execute(
          "SELECT state_json, status FROM sessions WHERE session_id = ?",
          (session_id,),
      ).fetchone()
      if row is not None:
        existing_state = json.loads(row["state_json"])
        if initial_state:
          existing_state.update(initial_state)
          conn.execute(
              "UPDATE sessions SET state_json = ?, updated_at = ? WHERE session_id = ?",
              (json.dumps(existing_state, default=str), now, session_id),
          )
        log_outcome(
            component="database_session_service",
            action="create_or_load_session",
            outcome=f"Loaded existing persistent session {session_id} ({len(existing_state)} state keys)",
            status="SUCCESS",
            session_id=session_id,
        )
        return existing_state

      state = dict(initial_state or {})
      conn.execute(
          """
          INSERT INTO sessions (session_id, app_name, user_id, state_json, status, created_at, updated_at)
          VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?)
          """,
          (
              session_id,
              app_name,
              user_id,
              json.dumps(state, default=str),
              now,
              now,
          ),
      )
      log_outcome(
          component="database_session_service",
          action="create_or_load_session",
          outcome=f"Created new persistent SQLite session {session_id}",
          status="SUCCESS",
          session_id=session_id,
      )
      return state

  def update_session_state(
      self,
      session_id: str,
      state_delta: dict[str, Any],
      *,
      node_name: str = "workflow",
      step_index: int = 0,
      route: str | None = None,
      status: str | None = None,
  ) -> dict[str, Any]:
    """Atomically merges state_delta into SQLite session state and journals the event."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with self._connect() as conn:
      row = conn.execute(
          "SELECT state_json, status FROM sessions WHERE session_id = ?",
          (session_id,),
      ).fetchone()
      current_state: dict[str, Any] = (
          json.loads(row["state_json"]) if row is not None else {}
      )
      current_status = status or (row["status"] if row is not None else "ACTIVE")
      current_state.update(state_delta)
      serialized_full = json.dumps(current_state, default=str)
      serialized_delta = json.dumps(state_delta, default=str)

      if row is None:
        conn.execute(
            """
            INSERT INTO sessions (session_id, app_name, user_id, state_json, status, created_at, updated_at)
            VALUES (?, 'kuwait_cal_executive_dashboard', 'clappaert', ?, ?, ?, ?)
            """,
            (session_id, serialized_full, current_status, now, now),
        )
      else:
        conn.execute(
            """
            UPDATE sessions
            SET state_json = ?, status = ?, updated_at = ?
            WHERE session_id = ?
            """,
            (serialized_full, current_status, now, session_id),
        )

      conn.execute(
          """
          INSERT INTO session_events (session_id, step_index, node_name, route, event_state_json, created_at)
          VALUES (?, ?, ?, ?, ?, ?)
          """,
          (session_id, step_index, node_name, route, serialized_delta, now),
      )
    return current_state

  def get_session_state(self, session_id: str) -> dict[str, Any]:
    """Reads the current persisted state dict for session_id from SQLite."""
    with self._connect() as conn:
      row = conn.execute(
          "SELECT state_json FROM sessions WHERE session_id = ?",
          (session_id,),
      ).fetchone()
      if row is None:
        return {}
      return json.loads(row["state_json"])

  def get_session_events(self, session_id: str) -> list[dict[str, Any]]:
    """Returns ordered event journal entries for session_id."""
    with self._connect() as conn:
      rows = conn.execute(
          """
          SELECT event_id, step_index, node_name, route, event_state_json, created_at
          FROM session_events
          WHERE session_id = ?
          ORDER BY event_id ASC
          """,
          (session_id,),
      ).fetchall()
      return [
          {
              "event_id": r["event_id"],
              "step_index": r["step_index"],
              "node_name": r["node_name"],
              "route": r["route"],
              "state_delta": json.loads(r["event_state_json"]),
              "created_at": r["created_at"],
          }
          for r in rows
      ]

  def save_checkpoint(
      self, session_id: str, checkpoint_key: str, payload: dict[str, Any]
  ) -> None:
    """Persists a named workflow checkpoint (e.g., JoinNode or RequestInput gate)."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with self._connect() as conn:
      conn.execute(
          """
          INSERT INTO workflow_checkpoints (session_id, checkpoint_key, payload_json, updated_at)
          VALUES (?, ?, ?, ?)
          ON CONFLICT(session_id, checkpoint_key)
          DO UPDATE SET payload_json = excluded.payload_json, updated_at = excluded.updated_at
          """,
          (session_id, checkpoint_key, json.dumps(payload, default=str), now),
      )

  def load_checkpoint(
      self, session_id: str, checkpoint_key: str
  ) -> dict[str, Any] | None:
    """Loads a named workflow checkpoint from SQLite."""
    with self._connect() as conn:
      row = conn.execute(
          """
          SELECT payload_json FROM workflow_checkpoints
          WHERE session_id = ? AND checkpoint_key = ?
          """,
          (session_id, checkpoint_key),
      ).fetchone()
      if row is None:
        return None
      return json.loads(row["payload_json"])
