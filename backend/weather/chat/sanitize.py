"""Sanitize tool arguments and outputs before they are persisted or returned.

The chat contract never accepts credentials, but a future tool or an
unexpected argument could carry one. Redaction runs before storage so the
history can never become a secret leak, and it is recursive because tool
payloads are nested JSON objects.
"""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[redacted]"

_SENSITIVE_KEY = re.compile(
    r"(api[_-]?key|token|secret|password|passwd|authorization|credential)", re.IGNORECASE
)
_SECRET_VALUE = re.compile(r"\b(sk|rk|pk|ghp|xox[baprs])[-_][A-Za-z0-9_-]{12,}\b")
_MAX_DEPTH = 12


def sanitize(value: Any, _depth: int = 0) -> Any:
    """Return a JSON-safe copy with secret-like keys and values redacted."""
    if _depth > _MAX_DEPTH:
        return REDACTED
    if isinstance(value, dict):
        return {
            str(key): REDACTED
            if _SENSITIVE_KEY.search(str(key))
            else sanitize(item, _depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [sanitize(item, _depth + 1) for item in value]
    if isinstance(value, str):
        return _SECRET_VALUE.sub(REDACTED, value)
    if isinstance(value, bool | int | float) or value is None:
        return value
    # Decimal and datetime are not JSON primitives; their string form is safe.
    return str(value)
