#!/usr/bin/env python3
"""CLI & Sunday 6:00 AM (`Asia/Kuwait`) Scheduler for the Kuwait CAL ADK Agent.

Usage:
  # 1. Execute one unattended Sunday 6am dashboard run (creates slides, runs Judge, emails link to Willem):
  python3 run_sunday_dashboard.py --once

  # 2. Execute a dry run (validates full ADK Workflow graph without external API mutations):
  python3 run_sunday_dashboard.py --once --dry-run

  # 3. Run interactive mode (pauses at RequestInput consent gate for 2-5d colleague reminders):
  python3 run_sunday_dashboard.py --interactive

  # 4. Run continuous Sunday 06:00 Asia/Kuwait scheduler daemon:
  python3 run_sunday_dashboard.py --daemon
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta
import os
from zoneinfo import ZoneInfo

from kuwait_cal_agent._adk_compat import InMemoryRunner, genai_types
from kuwait_cal_agent.agent import app

KUWAIT_TZ = ZoneInfo("Asia/Kuwait")


async def execute_dashboard_run(
    *,
    unattended: bool = True,
    dry_run: bool = False,
) -> dict:
  """Runs the ADK `kuwait_cal_dashboard_app` workflow using `InMemoryRunner`."""
  if dry_run:
    os.environ["CAL_AGENT_DRY_RUN"] = "1"

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
          print(f"[{event.author}] {part.text}")
        elif part.function_call:
          print(
              f"[HITL INTERRUPT: {part.function_call.name}] "
              f"id={part.function_call.id} message={part.function_call.args.get('message')}"
          )

  updated_session = await runner.session_service.get_session(
      app_name=app.name,
      user_id="clappaert",
      session_id=session.id,
  )
  return {
      "session_id": session.id,
      "events_count": len(events),
      "presentation_url": updated_session.state.get("dashboard_payload", {}).get("presentation_url", ""),
      "judge_evaluation": updated_session.state.get("judge_evaluation", {}),
      "self_email_result": updated_session.state.get("self_email_result", {}),
  }


def seconds_until_next_sunday_6am(now: datetime | None = None) -> float:
  """Calculates seconds until the next Sunday 06:00:00 in `Asia/Kuwait` time."""
  current = (now or datetime.now(tz=KUWAIT_TZ)).astimezone(KUWAIT_TZ)
  # Python weekday(): Monday=0 ... Sunday=6
  days_ahead = (6 - current.weekday()) % 7
  target = current.replace(hour=6, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
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
        trigger=CronTrigger(day_of_week="sun", hour=6, minute=0, timezone=KUWAIT_TZ),
        kwargs={"unattended": True, "dry_run": dry_run},
        id="weekly_kuwait_cal_dashboard",
        replace_existing=True,
    )
    scheduler.start()
    print("Started APScheduler daemon: every Sunday at 06:00 Asia/Kuwait.")
    while True:
      await asyncio.sleep(3600)
  except ImportError:
    print("APScheduler not installed; using built-in asyncio Sunday 06:00 Asia/Kuwait timer.")
    while True:
      wait_seconds = seconds_until_next_sunday_6am()
      print(f"Next run scheduled in {wait_seconds / 3600:.2f} hours (Sunday 06:00 Asia/Kuwait).")
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
    print(
        f"\nSummary: presentation_url={result['presentation_url']} | "
        f"judge_score={result['judge_evaluation'].get('overall_score')} | "
        f"email_status={result['self_email_result'].get('status')}"
    )


if __name__ == "__main__":
  main()
