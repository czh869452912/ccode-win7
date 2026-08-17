"""Shared validation for compiled bundle-plan payloads."""

from __future__ import annotations

import json
from pathlib import Path


def normalize_distribution_name(name):
    return str(name or "").replace("_", "-").replace(".", "-").lower()


def load_bundle_plan(path):
    plan_path = Path(path)
    if not plan_path.is_file():
        raise ValueError("bundle plan not found")
    try:
        payload = json.loads(plan_path.read_text(encoding="ascii"))
    except (OSError, ValueError) as exc:
        raise ValueError("bundle plan is invalid: %s" % exc)
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("unsupported bundle plan")
    raw_distributions = payload.get("project_distribution_ids")
    if not isinstance(raw_distributions, list) or not raw_distributions:
        raise ValueError("bundle plan project distributions are required")
    distributions = tuple(str(item or "").strip() for item in raw_distributions)
    if any(not item for item in distributions):
        raise ValueError("bundle plan project distributions are invalid")
    normalized = tuple(normalize_distribution_name(item) for item in distributions)
    if len(set(normalized)) != len(normalized):
        raise ValueError("bundle plan project distributions are duplicated")
    payload["project_distribution_ids"] = list(distributions)
    return payload, distributions
