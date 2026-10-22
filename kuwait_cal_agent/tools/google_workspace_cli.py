"""Read-only Google Workspace CLI tool wrappers for Calendar, Gmail, Docs, Sheets, and Slides.

Instrumented with OpenTelemetry distributed tracing (`@traced_tool`),
exponential backoff retry protection (`@retry_with_backoff`) for transient
503/429 errors, and ADK `FunctionToolWrapper` interface descriptors.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

from ..observability.telemetry import traced_tool
from .resilience import FunctionToolWrapper, retry_with_backoff

# Default binary paths on Google gLinux workstations
GCAL_BIN = os.environ.get("GCAL_BIN", "/google/bin/releases/gcal-cli/gcal")
GMAIL_BIN = os.environ.get("GMAIL_BIN", "/google/bin/releases/gmail-cli/gmail")
GDOCS_BIN = os.environ.get("GDOCS_BIN", "/google/bin/releases/gdocs-cli/gdocs")
GSHEETS_BIN = os.environ.get(
    "GSHEETS_BIN", "/google/bin/releases/gsheets/gsheets"
)
GSLIDES_BIN = os.environ.get(
    "GSLIDES_BIN", "/google/bin/releases/gslides-cli/gslides"
)

# Canonical Kuwait CAL Document, Sheet & Presentation IDs
GO_LINKS_DOC_ID = os.environ.get(
    "GO_LINKS_DOC_ID", "1GzG99rCKY8-BAbuULVB5yocrnx2Xlw2gh1TKVcJFTwA"
)
CAL_OVERVIEW_DOC_ID = os.environ.get(
    "CAL_OVERVIEW_DOC_ID", "1l2tqx0jpTUaT_z6VF9QdNJ6D9MCd8nNU5OXvRfrIDi4"
)
ALOTAIBI_MINUTES_DOC_ID = os.environ.get(
    "ALOTAIBI_MINUTES_DOC_ID", "1xAlotaibiMinutesDocIdKuwaitCal"
)
KW_WEEKLY_DECK_ID = os.environ.get(
    "KW_WEEKLY_DECK_ID", "1n-OjnVxa-QM3OTjDtXUpH5P3j3UagNQuxCWfG_SOXwQ"
)
DELIVERY_BOARD_DECK_ID = os.environ.get(
    "DELIVERY_BOARD_DECK_ID", "1DeliveryBoardDeckIdKuwaitCal"
)
COMMIT_ATTAINMENT_SHEET_ID = os.environ.get(
    "COMMIT_ATTAINMENT_SHEET_ID", "1nUuxKCommitAttainmentTrackerKuwaitCal"
)
PSF_TIF_SHEET_ID = os.environ.get(
    "PSF_TIF_SHEET_ID", "1NU0tuExternalPsfAndTifTrackerKuwaitCal"
)


@retry_with_backoff(max_attempts=3, base_delay_sec=0.05)
def _run_cli(cmd: list[str], timeout_sec: int = 45) -> dict[str, Any]:
  """Executes a read-only CLI command safely and returns structured output."""
  if os.environ.get("CAL_AGENT_DRY_RUN", "").lower() in ("1", "true", "yes"):
    return {
        "status": "DRY_RUN",
        "command": " ".join(cmd),
        "output": f"[DRY_RUN] Simulated output for {' '.join(cmd[:3])}",
    }

  binary = cmd[0]
  if not (os.path.exists(binary) or shutil.which(binary)):
    return {
        "status": "CLI_UNAVAILABLE",
        "binary": binary,
        "output": "",
        "error": f"Binary not found: {binary}",
    }
  try:
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=False,
    )
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    return {
        "status": "OK" if proc.returncode == 0 else "ERROR",
        "returncode": proc.returncode,
        "output": stdout,
        "error": stderr if proc.returncode != 0 else "",
    }
  except subprocess.TimeoutExpired:
    return {
        "status": "ERROR",
        "output": "",
        "error": f"DEADLINE_EXCEEDED: Command timed out after {timeout_sec}s",
    }


@traced_tool(
    "fetch_calendar_agenda",
    "Fetch Google Calendar agenda window for Kuwait CAL executive review",
)
def fetch_calendar_agenda(
    days_ahead: int = 14, days_behind: int = 7
) -> dict[str, Any]:
  """Fetches Willem's Google Calendar agenda across the specified window."""
  return _run_cli(
      [
          GCAL_BIN,
          "agenda",
          f"--days-ahead={days_ahead}",
          f"--days-behind={days_behind}",
          "--json",
      ]
  )


@traced_tool(
    "fetch_gmail_messages",
    "Search Gmail messages and Gemini Meet Notes for action items and colleague SLAs",
)
def fetch_gmail_messages(
    query: str, max_results: int = 25, full_body: bool = False
) -> dict[str, Any]:
  """Searches Gmail messages matching `query`."""
  cmd = [
      GMAIL_BIN,
      "search",
      query,
      f"--max-results={max_results}",
      "--json",
  ]
  if full_body:
    cmd.append("--full")
  return _run_cli(cmd)


@traced_tool(
    "read_google_doc",
    "Read Google Docs content (Go Links index, CAL Reference Doc, or Meet minutes)",
)
def read_google_doc(doc_id: str) -> dict[str, Any]:
  """Reads all tabs of a Google Document by document ID."""
  return _run_cli([GDOCS_BIN, "get", doc_id.strip(), "--include-tabs"])


@traced_tool(
    "read_google_sheet_range",
    "Read Commit Period 3 AFA, PSF, and TIF tracker cell ranges from Google Sheets",
)
def read_google_sheet_range(
    spreadsheet_id: str, cell_range: str = "A1:Z100"
) -> dict[str, Any]:
  """Reads a cell range from a Google Spreadsheet."""
  return _run_cli(
      [GSHEETS_BIN, "values", "get", spreadsheet_id.strip(), cell_range]
  )


@traced_tool(
    "read_google_slides",
    "Read Kuwait Weekly Team Deck and Delivery Board slides for portfolio continuity",
)
def read_google_slides(presentation_id: str) -> dict[str, Any]:
  """Reads slide text and speaker notes from a Google Slides deck."""
  return _run_cli([GSLIDES_BIN, "readonly", "show", presentation_id.strip()])


calendar_agenda_tool = FunctionToolWrapper(
    fetch_calendar_agenda, name="fetch_calendar_agenda", read_only=True
)
gmail_search_tool = FunctionToolWrapper(
    fetch_gmail_messages, name="fetch_gmail_messages", read_only=True
)
google_doc_read_tool = FunctionToolWrapper(
    read_google_doc, name="read_google_doc", read_only=True
)
google_sheet_read_tool = FunctionToolWrapper(
    read_google_sheet_range, name="read_google_sheet_range", read_only=True
)
google_slides_read_tool = FunctionToolWrapper(
    read_google_slides, name="read_google_slides", read_only=True
)
