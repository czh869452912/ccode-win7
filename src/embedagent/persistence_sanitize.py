from __future__ import annotations

import re
from typing import Any


_OPENAI_KEY_RE = re.compile(r"sk-[A-Za-z0-9_-]{12,}")
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)
_AUTH_HEADER_RE = re.compile(r"(?im)^(Authorization\s*:\s*)(.+)$")
_API_KEY_RE = re.compile(
    r"(?i)((?:api[_-]?key|access[_-]?token|secret|password)\s*[=:]\s*[\"']?)([^\s\"',;]+)"
)


def sanitize_text(text: Any) -> str:
    value = str(text or "")
    value = _OPENAI_KEY_RE.sub("<redacted-openai-key>", value)
    value = _BEARER_RE.sub("Bearer <redacted>", value)
    value = _AUTH_HEADER_RE.sub(r"\1<redacted>", value)
    value = _API_KEY_RE.sub(r"\1<redacted>", value)
    return value


def sanitize_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return dict((key, sanitize_jsonable(item)) for key, item in value.items())
    if isinstance(value, list):
        return [sanitize_jsonable(item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value)
    return value
