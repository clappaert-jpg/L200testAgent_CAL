#!/usr/bin/env python3
"""CLI & Sunday 6:00 AM (`Asia/Kuwait`) Scheduler for the Kuwait CAL ADK Agent.

Emits structured JSON logs with OpenTelemetry trace correlation and PII redaction.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta
import os
from typing import Any
from zoneinfo import ZoneInfo

from kuwait_cal_agent._adk_compat import InMemoryRunner, genai_types
from kuwait_cal_agent.agent import app, memory_consolidator
from kuwait_cal_agent.observability.logging import (
    get_structured_logger,
    log_intent,
    log_outcome,
)

KUWAIT_TZ = ZoneInfo("Asia/Kuwait")
LOGGER = get_structured_logger("kuwait_cal_scheduler")


async def execute_dashboard_run(
    *,
    unattended: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
  """Runs the ADK `kuwait_cal_dashboard_app` workflow with persistent SQLite session state."""
  if dry_run:
    os.environ["CAL_AGENT_DRY_RUN"] = "1"

  log_intent(
      component="scheduler_runner",
      action="execute_dashboard_run",
      intent="Execute weekly Kuwait CAL Executive Priority Dashboard ADK workflow",
      metadata={"unattended": unattended, "dry_run": dry_run},
  )

  runner = InMemoryRunner(app=app)
  session = await runner.session_service.create_session(
      app_name=app.name,
      user_id="clappaert",
      state={"unattended_schedule": unattended},
  )

  msg = genai_types.Content(
      role="user",
      parts=[
          genai_types.Part.from_text(
              text=(
                  "Run the weekly Kuwait CAL Executive Priority Dashboard, verify "
                  "with LLM-as-a-Judge, and email the presentation link to clappaert@google.com."
              )
          )
      ],
  )

  events = []
  async for event in runner.run_async(
      user_id="clappaert",
      session_id=session.id,
      new_message=msg,
  ):
    events.append(event)
    if event.content and event.content.parts:
      for part in event.content.parts:
        if part.text:
          LOGGER.info(
              part.text,
              extra={
                  "event_type": "WORKFLOW_EVENT",
                  "component": event.author,
                  "session_id": session.id,
              },
          )
        elif part.function_call:
          LOGGER.info(
              f"HITL Interrupt requested: {part.function_call.name}",
              extra={
                  "event_type": "HITL_INTERRUPT",
                  "component": event.author,
                  "session_id": session.id,
                  "metadata": {
                      "interrupt_id": part.function_call.id,
                      "message": part.function_call.args.get("message"),
                  },
              },
          )

  # Ensure any background async memory consolidation tasks complete cleanly
  await memory_consolidator.wait_for_pending_tasks()

  updated_session = await runner.session_service.get_session(
      app_name=app.name,
      user_id="clappaert",
      session_id=session.id,
  )
  summary = {
      "session_id": session.id,
      "events_count": len(events),
      "presentation_url": updated_session.state.get(
          "dashboard_payload", {}
      ).get("presentation_url", ""),
      "judge_evaluation": updated_session.state.get("judge_evaluation", {}),
      "self_email_result": updated_session.state.get("self_email_result", {}),
      "compaction_metrics": updated_session.state.get("compaction_metrics", {}),
  }
  log_outcome(
      component="scheduler_runner",
      action="execute_dashboard_run",
      outcome="Completed Kuwait CAL Executive Dashboard workflow run",
      status="SUCCESS",
      session_id=session.id,
      metrics={
          "events_count": len(events),
          "judge_score": summary["judge_evaluation"].get("overall_score", 0.0),
      },
  )
  return summary


def seconds_until_next_sunday_6am(now: datetime | None = None) -> float:
  """Calculates seconds until the next Sunday 06:00:00 in `Asia/Kuwait` time."""
  current = (now or datetime.now(tz=KUWAIT_TZ)).astimezone(KUWAIT_TZ)
  days_ahead = (6 - current.weekday()) % 7
  target = current.replace(
      hour=6, minute=0, second=0, microsecond=0
  ) + timedelta(days=days_ahead)
  if target <= current:
    target += timedelta(days=7)
  return (target - current).total_seconds()


async def run_sunday_6am_daemon(dry_run: bool = False) -> None:
  """Runs the Sunday 6:00 AM (`Asia/Kuwait`) scheduler loop."""
  try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
    from apscheduler.triggers.cron import CronTrigger  # type: ignore

    scheduler = AsyncIOScheduler(timezone=KUWAIT_TZ)
    scheduler.add_job(
        execute_dashboard_run,
        trigger=CronTrigger(
            day_of_week="sun", hour=6, minute=0, timezone=KUWAIT_TZ
        ),
        kwargs={"unattended": True, "dry_run": dry_run},
        id="weekly_kuwait_cal_dashboard",
        replace_existing=True,
    )
    scheduler.start()
    LOGGER.info(
        "Started APScheduler daemon: every Sunday at 06:00 Asia/Kuwait.",
        extra={"event_type": "SCHEDULER_START", "component": "daemon"},
    )
    while True:
      await asyncio.sleep(3600)
  except ImportError:
    LOGGER.info(
        "Using built-in asyncio Sunday 06:00 Asia/Kuwait timer.",
        extra={"event_type": "SCHEDULER_START", "component": "daemon"},
    )
    while True:
      wait_seconds = seconds_until_next_sunday_6am()
      LOGGER.info(
          f"Next run scheduled in {wait_seconds / 3600:.2f} hours (Sunday 06:00 Asia/Kuwait).",
          extra={
              "event_type": "SCHEDULER_WAIT",
              "component": "daemon",
              "metrics": {"wait_hours": round(wait_seconds / 3600.0, 2)},
          },
      )
      await asyncio.sleep(wait_seconds)
      await execute_dashboard_run(unattended=True, dry_run=dry_run)


def main() -> None:
  parser = argparse.ArgumentParser(
      description="Kuwait CAL Executive Priority Dashboard Agent (Python ADK)"
  )
  parser.add_argument(
      "--once",
      action="store_true",
      help="Run the dashboard workflow immediately once and exit.",
  )
  parser.add_argument(
      "--interactive",
      action="store_true",
      help="Run interactively and pause at the RequestInput colleague reminder consent gate.",
  )
  parser.add_argument(
      "--daemon",
      action="store_true",
      help="Run continuously on the Sunday 06:00 Asia/Kuwait schedule.",
  )
  parser.add_argument(
      "--dry-run",
      action="store_true",
      help="Execute workflow in dry-run mode without mutating Google Slides or Gmail.",
  )
  args = parser.parse_args()

  if args.daemon:
    asyncio.run(run_sunday_6am_daemon(dry_run=args.dry_run))
  else:
    unattended_mode = not args.interactive
    result = asyncio.run(
        execute_dashboard_run(unattended=unattended_mode, dry_run=args.dry_run)
    )
    LOGGER.info(
        "Workflow execution summary",
        extra={
            "event_type": "WORKFLOW_SUMMARY",
            "component": "cli",
            "session_id": result["session_id"],
            "metrics": {
                "presentation_url": result["presentation_url"],
                "judge_score": result["judge_evaluation"].get("overall_score"),
                "email_status": result["self_email_result"].get("status"),
            },
        },
    )


if __name__ == "__main__":
  main()
