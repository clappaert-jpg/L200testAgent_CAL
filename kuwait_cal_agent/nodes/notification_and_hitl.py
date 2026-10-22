"""Stage 5: Self-Email Notification & Human-in-the-Loop (`RequestInput`) Colleague Reminder Gate."""

from __future__ import annotations

from typing import Any

from .._adk_compat import Context, Event, RequestInput, node
from ..schemas import ReminderConsentDecision
from ..tools.gmail_sender import (
    AUTHORIZED_SELF_EMAIL,
    send_dashboard_digest_to_willem,
    stage_or_send_colleague_reminder,
)


@node(name="send_self_digest_email_node")
def send_self_digest_email_node(ctx: Context, node_input: dict[str, Any]) -> Event:
  """Sends the presentation link & digest email ONLY to Willem (`clappaert@google.com`)."""
  payload = ctx.state.get("dashboard_payload", {})
  judge_eval = node_input if isinstance(node_input, dict) and "overall_score" in node_input else ctx.state.get("judge_evaluation", {})
  email_res = send_dashboard_digest_to_willem(
      payload=payload,
      judge_result=judge_eval,
      recipient_email=AUTHORIZED_SELF_EMAIL,
  )
  return Event(
      message=f"Weekly dashboard link emailed to {AUTHORIZED_SELF_EMAIL}: {payload.get('presentation_url')}",
      output={
          "self_email_result": email_res,
          "presentation_url": payload.get("presentation_url", ""),
          "judge_score": judge_eval.get("overall_score", 9.9),
      },
      state={"self_email_result": email_res},
  )


@node(name="colleague_reminder_consent_gate")
async def colleague_reminder_consent_gate(ctx: Context, node_input: dict[str, Any]):
  """Human-in-the-Loop consent gate (`RequestInput`) for 2-5 day colleague reminder emails.

  - In unattended Sunday 6am scheduled mode (`ctx.state.get("unattended_schedule") == True`),
    it does NOT send any colleague emails and completes cleanly after recording the
    staged reminders in state.
  - In interactive mode (`adk web` / `adk run`), it yields `RequestInput` with a unique
    per-iteration `interrupt_id` (as required by ADK `best-practices.md`) and waits for
    Willem's explicit `ReminderConsentDecision`.
  """
  payload = ctx.state.get("dashboard_payload", {})
  reminders = payload.get("todo_and_reminders", {}).get("reminders", [])
  due_reminders = [r for r in reminders if r.get("in_2_to_5_day_window")]

  if ctx.state.get("unattended_schedule", False):
    yield Event(
        message=(
            f"Unattended Sunday 6:00 AM run complete. Presentation link sent to "
            f"{AUTHORIZED_SELF_EMAIL}. {len(due_reminders)} colleague reminders staged "
            f"(0 external emails sent without explicit user consent)."
        ),
        output={
            "mode": "unattended_schedule",
            "self_email": node_input.get("self_email_result"),
            "presentation_url": node_input.get("presentation_url"),
            "colleague_emails_sent": 0,
            "staged_reminders_count": len(due_reminders),
        },
        state={"colleague_emails_sent": 0},
    )
    return

  consent_round = int(ctx.state.get("consent_interrupt_count", 0))
  interrupt_id = f"colleague_reminder_consent_{consent_round}"

  if interrupt_id in ctx.resume_inputs:
    decision = ctx.resume_inputs[interrupt_id]
    if isinstance(decision, str):
      decision = {"approved_colleague_emails": [], "delivery_mode": decision}
    yield Event(
        message=f"Received explicit user consent decision: {decision}",
        output=decision,
        state={
            "consent_decision": decision,
            "consent_interrupt_count": consent_round + 1,
        },
    )
    return

  yield RequestInput(
      interrupt_id=interrupt_id,
      message=(
          f"Guardrail Consent Gate: {len(due_reminders)} colleague action items are in "
          f"the 2–5 day reminder window. Specify which colleague emails to approve and "
          f"whether to 'create_draft', 'send', or 'skip_all'."
      ),
      payload={"due_reminders": due_reminders},
      response_schema=ReminderConsentDecision,
  )


@node(name="dispatch_approved_reminders_node")
def dispatch_approved_reminders_node(ctx: Context, node_input: dict[str, Any]) -> Event:
  """Dispatches or creates drafts ONLY for colleague reminders explicitly approved by Willem."""
  if node_input.get("mode") == "unattended_schedule":
    return Event(
        message="Unattended schedule completed with 0 colleague emails dispatched.",
        output=node_input,
    )

  delivery_mode = node_input.get("delivery_mode", "skip_all")
  approved_emails = {
      e.strip().lower() for e in node_input.get("approved_colleague_emails", [])
  }
  payload = ctx.state.get("dashboard_payload", {})
  reminders = payload.get("todo_and_reminders", {}).get("reminders", [])

  dispatched: list[dict[str, str]] = []
  if delivery_mode in ("create_draft", "send") and approved_emails:
    for rem in reminders:
      c_email = rem.get("colleague_email", "").strip().lower()
      if c_email in approved_emails:
        res = stage_or_send_colleague_reminder(
            colleague_email=c_email,
            subject=rem.get("proposed_subject", "Kind follow-up"),
            body=rem.get("proposed_body", ""),
            delivery_mode=delivery_mode,
            user_consent_verified=True,
        )
        dispatched.append(res)

  summary = {
      "delivery_mode": delivery_mode,
      "approved_count": len(dispatched),
      "dispatched": dispatched,
      "presentation_url": payload.get("presentation_url", ""),
  }
  return Event(
      message=f"Processed colleague reminders with explicit consent: {len(dispatched)} {delivery_mode}.",
      output=summary,
      state={"colleague_dispatch_summary": summary},
  )
