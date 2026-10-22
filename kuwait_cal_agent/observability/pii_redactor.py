"""PII Redaction middleware for structured logs and OpenTelemetry trace spans.

Automatically scrubs email addresses, Kuwait Civil IDs, phone numbers, and
sensitive authentication secrets/tokens from strings, dictionaries, lists, and
Python logging.LogRecord instances before emission.
"""

from __future__ import annotations

import logging
import re
from typing import Any

# Regex patterns for PII and secret detection
_EMAIL_PATTERN = re.compile(
    r"\b([A-Za-z0-9._%+-])([A-Za-z0-9._%+-]*)"
    r"@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"
)
# Kuwait Civil IDs are 12-digit numbers starting with century digit 2 or 3
_KUWAIT_CIVIL_ID_PATTERN = re.compile(r"\b[23]\d{11}\b")
# International / Kuwait phone numbers (e.g., +965 5555 1234)
_PHONE_PATTERN = re.compile(
    r"(?:\+965[\s\-]?\d{4}[\s\-]?\d{4}|\+\d{1,3}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4})\b"
)
# Bearer tokens, OAuth access tokens, GitHub PATs, Google API keys
_TOKEN_PATTERN = re.compile(
    r"(?:Bearer\s+[A-Za-z0-9._\-~+/]+=*|gh[pousr]_[A-Za-z0-9_]{16,}|"
    r"ya29\.[A-Za-z0-9._\-]+|AIza[0-9A-Za-z\-_]{35})"
)

_SENSITIVE_KEY_NAMES = frozenset({
    "password",
    "passwd",
    "secret",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "device_code",
    "authorization",
    "private_key",
    "client_secret",
    "civil_id",
    "ssn",
})


def _mask_email(match: re.Match[str]) -> str:
  first_char = match.group(1)
  domain = match.group(3)
  return f"{first_char}***@{domain}"


class PiiRedactor:
  """Stateless PII and secret scrubber for logs, spans, and session payloads."""

  @classmethod
  def redact_text(cls, text: str) -> str:
    """Scrubs emails, Kuwait Civil IDs, phone numbers, and tokens from text."""
    if not text:
      return text
    scrubbed = _TOKEN_PATTERN.sub("[REDACTED_TOKEN]", text)
    scrubbed = _EMAIL_PATTERN.sub(_mask_email, scrubbed)
    scrubbed = _KUWAIT_CIVIL_ID_PATTERN.sub("[REDACTED_KUWAIT_CIVIL_ID]", scrubbed)
    scrubbed = _PHONE_PATTERN.sub("[REDACTED_PHONE]", scrubbed)
    return scrubbed

  @classmethod
  def redact_value(cls, value: Any, key_hint: str | None = None) -> Any:
    """Recursively scrubs PII and sensitive keys across nested structures."""
    if key_hint and key_hint.lower() in _SENSITIVE_KEY_NAMES:
      return "[REDACTED_SECRET]"
    if isinstance(value, str):
      return cls.redact_text(value)
    if isinstance(value, dict):
      return {
          str(k): cls.redact_value(v, key_hint=str(k))
          for k, v in value.items()
      }
    if isinstance(value, list):
      return [cls.redact_value(item) for item in value]
    if isinstance(value, tuple):
      return tuple(cls.redact_value(item) for item in value)
    return value


def scrub_pii(payload: Any) -> Any:
  """Convenience entrypoint for scrubbing arbitrary strings or dicts."""
  return PiiRedactor.redact_value(payload)


class PiiRedactingFilter(logging.Filter):
  """Python logging.Filter that enforces PII redaction on every LogRecord."""

  def filter(self, record: logging.LogRecord) -> bool:
    if isinstance(record.msg, str):
      record.msg = PiiRedactor.redact_text(record.msg)
    elif isinstance(record.msg, dict):
      record.msg = PiiRedactor.redact_value(record.msg)

    if record.args:
      if isinstance(record.args, dict):
        record.args = PiiRedactor.redact_value(record.args)
      elif isinstance(record.args, tuple):
        record.args = tuple(PiiRedactor.redact_value(a) for a in record.args)

    for attr in ("intent", "outcome", "metadata", "metrics", "payload"):
      if hasattr(record, attr):
        setattr(record, attr, PiiRedactor.redact_value(getattr(record, attr)))
    return True
