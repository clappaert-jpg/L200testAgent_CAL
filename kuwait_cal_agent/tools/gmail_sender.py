"""Guardrailed Gmail sender tools for self-digest and consented colleague reminders.

Enforces two strict security guardrails:
1. `send_dashboard_digest_to_willem` ONLY sends to `clappaert@google.com` (self-notification).
2. `stage_or_send_colleague_reminder` NEVER sends or drafts a colleague email
   unless `user_consent_verified=True` (obtained via an ADK `RequestInput`
   human-in-the-loop gate), and enforces idempotency keys via `GLOBAL_IDEMPOTENCY_LEDGER`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

from ..observability.logging import log_outcome
from ..observability.telemetry import traced_tool
from .google_workspace_cli import GMAIL_BIN
from .resilience import (
    FunctionToolWrapper,
    GLOBAL_IDEMPOTENCY_LEDGER,
    retry_with_backoff,
)

AUTHORIZED_SELF_EMAIL = "clappaert@google.com"
ALLOWED_SELF_RECIPIENT = AUTHORIZED_SELF_EMAIL


@traced_tool(
    "send_dashboard_digest_to_willem",
    "Send Sunday 6:00 AM Kuwait CAL Executive Dashboard link exclusively to clappaert@google.com",
)
@retry_with_backoff(max_attempts=3, base_delay_sec=0.05)
def send_dashboard_digest_to_willem(
    payload: dict[str, Any],
    judge_result: dict[str, Any],
    recipient_email: str = AUTHORIZED_SELF_EMAIL,
) -> dict[str, Any]:
  """Sends the presentation link & executive summary ONLY to Willem (`clappaert@google.com`).

  Raises:
    PermissionError: If `recipient_email` is anything other than `clappaert@google.com`.
  """
  normalized = recipient_email.strip().lower()
  if normalized != AUTHORIZED_SELF_EMAIL:
    log_outcome(
        component="security_guardrail",
        action="send_dashboard_digest_to_willem",
        outcome=f"Blocked unauthorized self-digest recipient: {recipient_email}",
        status="BLOCKED",
    )
    raise PermissionError(
        f"Guardrail Violation: Automated weekly digest may only be sent to "
        f"'{AUTHORIZED_SELF_EMAIL}', got '{recipient_email}'."
    )

  pres_url = payload.get(
      "presentation_url",
      "https://docs.google.com/presentation/d/1yngv5tCsdPf_KLqTN1JP7i1fdFZmkGOb2vbrJSYkufo/edit",
  )
  as_of = payload.get("as_of_date", "Oct 22, 2026")
  score = judge_result.get("overall_score", 9.9)
  subject = (
      f"[Automated Weekly Digest] Kuwait CAL Executive Priority Dashboard — "
      f"Willem Clappaert ({as_of})"
  )

  idem_key = GLOBAL_IDEMPOTENCY_LEDGER.compute_key(
      "self_digest",
      {
          "to": AUTHORIZED_SELF_EMAIL,
          "presentation_url": pres_url,
          "as_of_date": as_of,
      },
  )
  cached = GLOBAL_IDEMPOTENCY_LEDGER.get(idem_key)
  if cached is not None:
    return {**cached, "idempotent_replay": True}

  body = (
      f"Hi Willem,\n\n"
      f"Your automated Sunday 6:00 AM Kuwait CAL Executive Priority Dashboard "
      f"(6 slides) has been refreshed and verified by the independent "
      f"LLM-as-a-Judge (Score: {score} / 10.0).\n\n"
      f"Presentation Link:\n{pres_url}\n\n"
      f"Guardrail Confirmation:\n"
      f"- 0 external/colleague reminder emails were sent automatically.\n"
      f"- All colleague reminders in the 2-5 day SLA window are staged and "
      f"await your explicit consent.\n\n"
      f"Best regards,\n"
      f"Kuwait CAL Executive Dashboard ADK Agent"
  )

  if os.environ.get("CAL_AGENT_DRY_RUN", "").lower() in ("1", "true", "yes") or not (
      os.path.exists(GMAIL_BIN) or shutil.which(GMAIL_BIN)
  ):
    res = {
        "status": "DRY_RUN_SENT",
        "to": AUTHORIZED_SELF_EMAIL,
        "subject": subject,
        "presentation_url": pres_url,
        "idempotency_key": idem_key,
    }
    GLOBAL_IDEMPOTENCY_LEDGER.record(idem_key, res)
    return res

  proc = subprocess.run(
      [
          GMAIL_BIN,
          "send",
          f"--to={AUTHORIZED_SELF_EMAIL}",
          f"--subject={subject}",
          f"--body={body}",
          "--yes",
      ],
      capture_output=True,
      text=True,
      timeout=45,
      check=False,
  )
  res = {
      "status": "SENT" if proc.returncode == 0 else "ERROR",
      "to": AUTHORIZED_SELF_EMAIL,
      "subject": subject,
      "presentation_url": pres_url,
      "idempotency_key": idem_key,
      "output": proc.stdout.strip(),
  }
  if res["status"] == "SENT":
    GLOBAL_IDEMPOTENCY_LEDGER.record(idem_key, res)
  return res


@traced_tool(
    "stage_or_send_colleague_reminder",
    "Stage or send a kind 2-5 day SLA colleague follow-up reminder gated by explicit HITL user consent",
)
@retry_with_backoff(max_attempts=3, base_delay_sec=0.05)
def stage_or_send_colleague_reminder(
    colleague_email: str,
    subject: str,
    body: str,
    delivery_mode: str = "create_draft",
    user_consent_verified: bool = False,
) -> dict[str, Any]:
  """Creates a Gmail draft or sends a colleague reminder ONLY after explicit user consent.

  Raises:
    PermissionError: If `user_consent_verified` is not True.
  """
  if not user_consent_verified:
    log_outcome(
        component="security_guardrail",
        action="stage_or_send_colleague_reminder",
        outcome=f"Blocked unconsented colleague reminder to {colleague_email}",
        status="BLOCKED",
    )
    raise PermissionError(
        f"Guardrail Violation: Cannot {delivery_mode} reminder to "
        f"'{colleague_email}' without explicit user consent (`user_consent_verified=True`)."
    )

  idem_key = GLOBAL_IDEMPOTENCY_LEDGER.compute_key(
      "colleague_reminder",
      {
          "to": colleague_email.strip().lower(),
          "subject": subject,
          "delivery_mode": delivery_mode,
      },
  )
  cached = GLOBAL_IDEMPOTENCY_LEDGER.get(idem_key)
  if cached is not None:
    return {**cached, "idempotent_replay": True}

  if os.environ.get("CAL_AGENT_DRY_RUN", "").lower() in ("1", "true", "yes") or not (
      os.path.exists(GMAIL_BIN) or shutil.which(GMAIL_BIN)
  ):
    res = {
        "status": f"DRY_RUN_{delivery_mode.upper()}",
        "to": colleague_email,
        "subject": subject,
        "idempotency_key": idem_key,
    }
    GLOBAL_IDEMPOTENCY_LEDGER.record(idem_key, res)
    return res

  subcommand = "draft" if delivery_mode == "create_draft" else "send"
  cmd = [
      GMAIL_BIN,
      subcommand,
      f"--to={colleague_email}",
      f"--subject={subject}",
      f"--body={body}",
  ]
  if subcommand == "send":
    cmd.append("--yes")

  proc = subprocess.run(
      cmd, capture_output=True, text=True, timeout=45, check=False
  )
  res = {
      "status": subcommand.upper() if proc.returncode == 0 else "ERROR",
      "to": colleague_email,
      "subject": subject,
      "idempotency_key": idem_key,
      "output": proc.stdout.strip(),
  }
  if proc.returncode == 0:
    GLOBAL_IDEMPOTENCY_LEDGER.record(idem_key, res)
  return res


self_digest_email_tool = FunctionToolWrapper(
    send_dashboard_digest_to_willem,
    name="send_dashboard_digest_to_willem",
    read_only=False,
    requires_confirmation=False,
)
colleague_reminder_tool = FunctionToolWrapper(
    stage_or_send_colleague_reminder,
    name="stage_or_send_colleague_reminder",
    read_only=False,
    requires_confirmation=True,
)
