"""Stage 1: Parallel data-ingestion FunctionNodes for the Kuwait CAL Workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .._adk_compat import Context, Event, node
from ..tools.google_workspace_cli import (
    ALOTAIBI_MINUTES_DOC_ID,
    CAL_OVERVIEW_DOC_ID,
    COMMIT_ATTAINMENT_SHEET_ID,
    DELIVERY_BOARD_DECK_ID,
    GO_LINKS_DOC_ID,
    KW_WEEKLY_DECK_ID,
    PSF_TIF_SHEET_ID,
    fetch_calendar_agenda,
    fetch_gmail_messages,
    read_google_doc,
    read_google_sheet_range,
    read_google_slides,
)


@node(name="collect_agenda_and_emails")
def collect_agenda_and_emails(node_input: str) -> Event:
  """Collects Willem's Google Calendar agenda, Inbox, Sent Mail, and Gemini Meet Notes."""
  agenda = fetch_calendar_agenda(days_ahead=14, days_behind=7)
  inbox = fetch_gmail_messages("to:me newer_than:7d", max_results=25)
  sent = fetch_gmail_messages("from:me newer_than:14d", max_results=30)
  meet_notes = fetch_gmail_messages(
      "from:gemini-notes@google.com newer_than:14d",
      max_results=15,
      full_body=True,
  )
  payload = {
      "request": node_input,
      "agenda": agenda.get("output", ""),
      "inbox": inbox.get("output", ""),
      "sent": sent.get("output", ""),
      "meet_notes": meet_notes.get("output", ""),
  }
  return Event(output=payload, state={"agenda_and_emails": payload})


@node(name="collect_afa_consumption")
def collect_afa_consumption(node_input: str) -> Event:
  """Collects Commit Period 3 (CP3) GCP, PSO, Workspace, PSF, TIF, and Credit trackers."""
  del node_input
  commit_sheet = read_google_sheet_range(COMMIT_ATTAINMENT_SHEET_ID, "Commit attainment!A1:N40")
  incentives_sheet = read_google_sheet_range(COMMIT_ATTAINMENT_SHEET_ID, "Incentives!A1:M50")
  psf_sheet = read_google_sheet_range(PSF_TIF_SHEET_ID, "PSF!A1:P50")
  tif_sheet = read_google_sheet_range(PSF_TIF_SHEET_ID, "TIF!A1:P40")
  payload = {
      "commit_attainment": commit_sheet.get("output", ""),
      "incentives": incentives_sheet.get("output", ""),
      "psf_tracker": psf_sheet.get("output", ""),
      "tif_tracker": tif_sheet.get("output", ""),
  }
  return Event(output=payload, state={"afa_sheets": payload})


@node(name="collect_project_and_gov_docs")
def collect_project_and_gov_docs(node_input: str) -> Event:
  """Collects Go Links, CAL overview doc, Alotaibi minutes, KW Weekly deck, and Delivery Board."""
  del node_input
  go_links = read_google_doc(GO_LINKS_DOC_ID)
  cal_doc = read_google_doc(CAL_OVERVIEW_DOC_ID)
  alotaibi_min = read_google_doc(ALOTAIBI_MINUTES_DOC_ID)
  kw_weekly = read_google_slides(KW_WEEKLY_DECK_ID)
  delivery_board = read_google_slides(DELIVERY_BOARD_DECK_ID)
  payload = {
      "go_links": go_links.get("output", ""),
      "cal_doc": cal_doc.get("output", ""),
      "alotaibi_minutes": alotaibi_min.get("output", ""),
      "kw_weekly_deck": kw_weekly.get("output", ""),
      "delivery_board": delivery_board.get("output", ""),
  }
  return Event(output=payload, state={"project_and_gov_docs": payload})


@node(name="collect_kuwait_innovation_context")
def collect_kuwait_innovation_context(node_input: str) -> Event:
  """Provides Kuwait Vision 2035 & 3-Layer National AI Factory context for weekly ideation."""
  del node_input
  payload = {
      "vision_framework": "New Kuwait Vision 2035 & CAIT 3-Layer National AI Factory (2027)",
      "layers": [
          "Layer 1: Nationwide Citizen (PACI Mobile ID / Sahel) & Civil Servant (CSC 1,200 VMs) Agents",
          "Layer 2: Entity-Specific Agents (MoF, CAPT, MoE, KU, MoJ, MoH)",
          "Layer 3: Project-Embedded Agents (ServiceNow $60M, MEW Smart Grid, KOC/KPC, Iron Mountain)",
      ],
      "as_of_date": datetime.now(timezone.utc).strftime("%b %d, %Y"),
  }
  return Event(output=payload, state={"innovation_context": payload})


@node(name="store_joined_context")
def store_joined_context(ctx: Context, node_input: dict[str, Any]) -> Event:
  """Stores the joined outputs from all 4 Stage-1 data collectors into session state."""
  del ctx
  return Event(
      message="Completed parallel ingestion of Calendar, Gmail, Meet Notes, AFA Sheets, and Governance Docs.",
      output=node_input,
      state={"raw_context": node_input},
  )
