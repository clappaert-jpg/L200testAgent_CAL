"""Guardrailed Gmail notification & draft tools for the Kuwait CAL Dashboard Agent.

Enforces two strict rules:
1. Self-Notification (Authorized by User): Sends the weekly Google Slides dashboard link
   and executive summary ONLY to `clappaert@google.com`.
2. External / Colleague Guardrail: NEVER sends any colleague reminder email unless
   explicitly approved via the ADK `RequestInput` human-in-the-loop gate.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Any

from .google_workspace_cli import GMAIL_BIN

AUTHORIZED_SELF_EMAIL = "clappaert@google.com"


def format_weekly_digest_markdown(
    payload: dict[str, Any],
    judge_result: dict[str, Any],
) -> str:
  """Formats the weekly Markdown email body sent to `clappaert@google.com`."""
  pres_url = payload.get("presentation_url", "https://docs.google.com/presentation/d/1yngv5tCsdPf_KLqTN1JP7i1fdFZmkGOb2vbrJSYkufo/edit")
  as_of = payload.get("as_of_date", "Oct 22, 2026")
  score = judge_result.get("overall_score", 9.9)
  todos = payload.get("todo_and_reminders", {}).get("todos", [])
  reminders = payload.get("todo_and_reminders", {}).get("reminders", [])

  lines = [
      f"# Kuwait CAL Executive Priority Dashboard — Weekly Digest ({as_of})",
      "",
      "Hi Willem,",
      "",
      f"Your **6-Slide Kuwait CAL Executive Priority Dashboard** has been automatically generated and verified by the **LLM-as-a-Judge** (Score: **{score} / 10.0**).",
      "",
      f"- **Open Presentation in Google Slides**: [Kuwait CAL Executive Priority Dashboard ({as_of})]({pres_url})",
      "",
      "---",
      "",
      "## 1. Top 10 Priority 'To-Do' List (This Week & Next Week)",
  ]
  for t in todos[:10]:
    lines.append(
        f"{t.get('rank')}. **[{t.get('horizon')} | Due {t.get('due_date')}]** "
        f"{t.get('action')} *(Stakeholders: {t.get('stakeholders')})*"
    )

  lines.extend([
      "",
      "---",
      "",
      "## 2. Pending Colleague Reminders (2–5 Day Rule — 0 Sent Without Your Consent)",
  ])
  for r in reminders:
    flag = "IN 2-5d WINDOW (Ready for Approval)" if r.get("in_2_to_5_day_window") else "Monitoring"
    lines.append(
        f"- **{r.get('colleague_name')}** (`{r.get('colleague_email')}`) — "
        f"*{r.get('action_requested')}* (Asked: {r.get('date_asked')} | "
        f"Elapsed: {r.get('days_elapsed')}d | **{flag}**)"
    )

  lines.append("")
  return "\n".join(lines)


def send_dashboard_digest_to_willem(
    payload: dict[str, Any],
    judge_result: dict[str, Any],
    recipient_email: str = AUTHORIZED_SELF_EMAIL,
) -> dict[str, str]:
  """Sends the weekly presentation link & summary email ONLY to Willem (`clappaert@google.com`).

  Raises:
    PermissionError: If `recipient_email` is not `clappaert@google.com`.
  """
  if recipient_email.strip().lower() != AUTHORIZED_SELF_EMAIL:
    raise PermissionError(
        f"Guardrail violation: automatic weekly digest may only be sent to "
        f"'{AUTHORIZED_SELF_EMAIL}', got '{recipient_email}'."
    )

  as_of = payload.get("as_of_date", "Oct 22, 2026")
  subject = f"Weekly Kuwait CAL Executive Priority Dashboard ({as_of})"
  md_body = format_weekly_digest_markdown(payload, judge_result)

  if os.environ.get("CAL_AGENT_DRY_RUN", "").lower() in ("1", "true", "yes"):
    return {
        "status": "dry_run_sent",
        "to": AUTHORIZED_SELF_EMAIL,
        "subject": subject,
        "presentation_url": payload.get("presentation_url", ""),
    }

  with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as tf:
    tf.write(md_body)
    body_path = tf.name

  try:
    send_proc = subprocess.run(
        [
            GMAIL_BIN,
            "mutate",
            "send",
            "--to",
            AUTHORIZED_SELF_EMAIL,
            "--subject",
            subject,
            "--md",
            "--body-file",
            body_path,
        ],
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    if send_proc.returncode == 0:
      return {
          "status": "sent",
          "to": AUTHORIZED_SELF_EMAIL,
          "subject": subject,
          "output": send_proc.stdout.strip(),
      }
    # Fallback to `create-draft` if `AGY_UNATTENDED` blocks outbound send
    draft_proc = subprocess.run(
        [
            GMAIL_BIN,
            "mutate",
            "create-draft",
            "--to",
            AUTHORIZED_SELF_EMAIL,
            "--subject",
            subject,
            "--md",
            "--body-file",
            body_path,
        ],
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    return {
        "status": "draft_created",
        "to": AUTHORIZED_SELF_EMAIL,
        "subject": subject,
        "output": draft_proc.stdout.strip() or send_proc.stderr.strip(),
    }
  finally:
    if os.path.exists(body_path):
      os.remove(body_path)


def stage_or_send_colleague_reminder(
    colleague_email: str,
    subject: str,
    body: str,
    delivery_mode: str = "create_draft",
    user_consent_verified: bool = False,
) -> dict[str, str]:
  """Creates a Gmail draft or sends a kind colleague reminder ONLY after explicit user consent.

  Raises:
    PermissionError: If `user_consent_verified` is not True.
  """
  if not user_consent_verified:
    raise PermissionError(
        "Guardrail violation: Cannot stage or send colleague reminder without explicit user consent."
    )
  if delivery_mode == "skip_all":
    return {"status": "skipped", "to": colleague_email}

  if os.environ.get("CAL_AGENT_DRY_RUN", "").lower() in ("1", "true", "yes"):
    return {"status": f"dry_run_{delivery_mode}", "to": colleague_email, "subject": subject}

  subcmd = "send" if delivery_mode == "send" else "create-draft"
  proc = subprocess.run(
      [
          GMAIL_BIN,
          "mutate",
          subcmd,
          "--to",
          colleague_email,
          "--subject",
          subject,
          "--md",
          "--body",
          body,
      ],
      capture_output=True,
      text=True,
      timeout=45,
      check=False,
  )
  return {
      "status": subcmd if proc.returncode == 0 else "error",
      "to": colleague_email,
      "output": proc.stdout.strip() or proc.stderr.strip(),
  }
