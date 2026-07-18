from __future__ import annotations

from typing import Any, Dict, List, Optional

AGENT_SESSION_PROTOCOL = "agent_session_v1"
CAPABILITY_PROTOCOL = "capability_v1"
IDE_SERVICE_PROTOCOL = "ide_service_v1"
APP_SHELL_PROTOCOL = "app_shell_v1"

PROTOCOL_VERSIONS = (
    AGENT_SESSION_PROTOCOL,
    CAPABILITY_PROTOCOL,
    IDE_SERVICE_PROTOCOL,
    APP_SHELL_PROTOCOL,
)

_SENSITIVE_KEY_PARTS = (
    "api_key",
    "authorization",
    "password",
    "secret",
    "token",
)
_BLOCKED_KEYS = ("prompt", "transcript", "tool_output")


def _is_json_safe(value: Any) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json_safe(item) for key, item in value.items())
    if isinstance(value, list):
        return all(_is_json_safe(item) for item in value)
    return False


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in _BLOCKED_KEYS or any(part in lowered for part in _SENSITIVE_KEY_PARTS):
                return True
            if _contains_sensitive_key(item):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def make_protocol_envelope(
    protocol: str,
    payload: Dict[str, Any],
    sequence: int = 0,
    revision: str = "",
) -> Dict[str, Any]:
    return {
        "protocol": str(protocol or ""),
        "version": 1,
        "sequence": sequence,
        "revision": str(revision or ""),
        "payload": dict(payload or {}),
    }


def validate_protocol_envelope(
    value: Any,
    expected_protocol: Optional[str] = None,
) -> Dict[str, Any]:
    errors: List[str] = []
    if not isinstance(value, dict):
        return {"valid": False, "errors": ["envelope"], "envelope": None}

    protocol = value.get("protocol")
    if not isinstance(protocol, str) or not protocol.strip():
        errors.append("protocol")
    elif expected_protocol and protocol != expected_protocol:
        errors.append("protocol")
    if value.get("version") != 1:
        errors.append("version")
    sequence = value.get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        errors.append("sequence")
    revision = value.get("revision")
    if not isinstance(revision, str) or not revision.strip():
        errors.append("revision")
    payload = value.get("payload")
    if not isinstance(payload, dict) or not _is_json_safe(payload):
        errors.append("payload")
    elif _contains_sensitive_key(payload):
        errors.append("sensitive")

    if errors:
        return {"valid": False, "errors": errors, "envelope": None}
    return {
        "valid": True,
        "errors": [],
        "envelope": {
            "protocol": protocol,
            "version": 1,
            "sequence": sequence,
            "revision": revision,
            "payload": dict(payload),
        },
    }
