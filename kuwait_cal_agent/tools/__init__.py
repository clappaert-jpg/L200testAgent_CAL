"""Tools for Google Workspace CLI integration, Slide rendering, and Gmail notifications."""

from .gmail_sender import send_dashboard_digest_to_willem, stage_or_send_colleague_reminder
from .google_workspace_cli import (
    fetch_calendar_agenda,
    fetch_gmail_messages,
    read_google_doc,
    read_google_sheet_range,
    read_google_slides,
)
from .slides_renderer import build_six_slide_batch_ops, create_and_populate_dashboard_slides

__all__ = [
    "fetch_calendar_agenda",
    "fetch_gmail_messages",
    "read_google_doc",
    "read_google_sheet_range",
    "read_google_slides",
    "build_six_slide_batch_ops",
    "create_and_populate_dashboard_slides",
    "send_dashboard_digest_to_willem",
    "stage_or_send_colleague_reminder",
]
