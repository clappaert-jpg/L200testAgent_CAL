"""Read-only tool wrappers around Google Workspace CLIs for ADK LlmAgents & FunctionNodes.

Every tool function has explicit type annotations and a descriptive docstring
as required by Google ADK (`getting-started.md`).
"""

from __future__ import annotations

import os
import subprocess

GCAL_BIN = "/google/bin/releases/gemini-agents-gcalendar/gcalendar"
GMAIL_BIN = "/google/bin/releases/gemini-agents-gmail/gmail"
GDOCS_BIN = "/google/bin/releases/gemini-agents-gdocs/gdocs"
GSHEETS_BIN = "/google/bin/releases/gemini-agents-gsheets/gsheets"
GSLIDES_BIN = "/google/bin/releases/gemini-agents-gslides/gslides"

# Master Kuwait CAL Reference Document & Sheet IDs
GO_LINKS_DOC_ID = "1GzG99rCKY8-BAbuULVB5yocrnx2Xlw2gh1TKVcJFTwA"
CAL_OVERVIEW_DOC_ID = "1l2tqx0jpTUaT_z6VF9QdNJ6D9MCd8nNU5OXvRfrIDi4"
ALOTAIBI_MINUTES_DOC_ID = "1mmwB6UqQ36Ud3sk3hT02qQb5eGs39KCT5JZVi5Jrtjg"
KW_WEEKLY_DECK_ID = "1n-OjnVxa-QM3OTjDtXUpH5P3j3UagNQuxCWfG_SOXwQ"
COMMIT_ATTAINMENT_SHEET_ID = "1nUuxK7XUJ159gV_S7Tj9ogd1koad8u3uyEhDeFghUrk"
PSF_TIF_SHEET_ID = "1NU0tuiXAEAwk2RtiL_5_972fLiuve8_DhtG9gKHi8x4"
DELIVERY_BOARD_DECK_ID = "13lVJ6DpPbYecmjBCMwTOTXaKUeY7FrFAW3yh_u8VHZ4"


def _run_cli(args: list[str], timeout_sec: int = 45) -> dict[str, str]:
  """Runs a Google Workspace CLI binary safely and returns stdout/stderr."""
  if os.environ.get("CAL_AGENT_DRY_RUN", "").lower() in ("1", "true", "yes"):
    return {"status": "dry_run", "command": " ".join(args), "output": ""}
  try:
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=False,
    )
    if proc.returncode == 0:
      return {"status": "success", "output": proc.stdout.strip()}
    return {
        "status": "error",
        "output": proc.stdout.strip(),
        "error": proc.stderr.strip() or f"Exit code {proc.returncode}",
    }
  except Exception as exc:  # pylint: disable=broad-except
    return {"status": "error", "output": "", "error": str(exc)}


def fetch_calendar_agenda(days_ahead: int = 14, days_behind: int = 7) -> dict[str, str]:
  """Fetches Willem Clappaert's Google Calendar events for the past and upcoming weeks.

  Args:
    days_ahead: Number of upcoming days to retrieve.
    days_behind: Number of past days to retrieve.

  Returns:
    A dictionary containing `status` and `output` with calendar event details.
  """
  return _run_cli([
      GCAL_BIN,
      "readonly",
      "list",
      "--days",
      str(days_ahead),
      "--past-days",
      str(days_behind),
  ])


def fetch_gmail_messages(query: str, max_results: int = 20, full_body: bool = False) -> dict[str, str]:
  """Searches or reads Gmail messages matching the given query string.

  Args:
    query: Gmail search query (e.g., 'to:me newer_than:7d' or 'from:me newer_than:14d').
    max_results: Maximum number of messages to retrieve (uses --max).
    full_body: If True, uses `readonly read` for full plain-text bodies instead of `search`.

  Returns:
    A dictionary containing `status` and `output` with matching Gmail messages.
  """
  subcmd = "read" if full_body else "search"
  return _run_cli([
      GMAIL_BIN,
      "readonly",
      subcmd,
      query,
      "--max",
      str(max_results),
  ])


def read_google_doc(document_id: str) -> dict[str, str]:
  """Reads the full text content of a Google Doc by its document ID.

  Args:
    document_id: The Google Docs file ID.

  Returns:
    A dictionary containing `status` and `output` with the document text.
  """
  return _run_cli([GDOCS_BIN, "readonly", "read", document_id])


def read_google_sheet_range(spreadsheet_id: str, sheet_range: str) -> dict[str, str]:
  """Reads a cell range from a Google Sheet (such as the CP3 AFA Commit or PSF/TIF Tracker).

  Args:
    spreadsheet_id: The Google Sheets file ID.
    sheet_range: A1 notation range, e.g. 'Commit attainment!A1:N40' or 'PSF!A1:P50'.

  Returns:
    A dictionary containing `status` and `output` with the tabular values.
  """
  return _run_cli([GSHEETS_BIN, "readonly", "read", spreadsheet_id, sheet_range])


def read_google_slides(presentation_id: str) -> dict[str, str]:
  """Reads all slides as plain text from a Google Slides presentation.

  Args:
    presentation_id: The Google Slides presentation ID.

  Returns:
    A dictionary containing `status` and `output` with the extracted slide text.
  """
  return _run_cli([GSLIDES_BIN, "readonly", "read", presentation_id])
