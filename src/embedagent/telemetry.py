from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

_SENSITIVE_KEY_PARTS = (
    "api_key",
    "approval",
    "authorization",
    "content",
    "credential",
    "key",
    "message",
    "messages",
    "permission_payload",
    "prompt",
    "raw",
    "secret",
    "source",
    "source_text",
    "text",
    "token",
    "tool_output",
)


def build_safe_telemetry_envelope(
    event_type: str,
    metadata: Dict[str, Any],
    source_type: str = "",
    source_id: str = "",
) -> Dict[str, Any]:
    return {
        "event_type": str(event_type or ""),
        "created_at": _utc_timestamp(),
        "source_type": str(source_type or ""),
        "source_id": str(source_id or ""),
        "metadata": sanitize_telemetry_metadata(metadata),
    }


def sanitize_telemetry_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    result = {}
    for key, value in metadata.items():
        clean_key = str(key or "")
        if not clean_key:
            continue
        if _is_sensitive_key(clean_key):
            result[clean_key] = "<redacted>"
            continue
        result[clean_key] = _safe_value(value)
    return result


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower()
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= 200 else value[:200] + "...<truncated>"
    if isinstance(value, dict):
        if _dict_is_scalar(value):
            return dict(value)
        return {"type": "dict", "count": len(value)}
    if isinstance(value, (list, tuple)):
        return {"type": "list", "count": len(value)}
    return str(type(value).__name__)


def _dict_is_scalar(value: Dict[str, Any]) -> bool:
    for item in value.values():
        if not (item is None or isinstance(item, (bool, int, float, str))):
            return False
    return True


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
