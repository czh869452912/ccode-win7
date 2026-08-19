"""Shared validation for compiled bundle-plan payloads."""

from __future__ import annotations

import json
from pathlib import Path


def normalize_distribution_name(name):
    return str(name or "").replace("_", "-").replace(".", "-").lower()


def _required_unique_ids(payload, field_name, normalize=None):
    raw_values = payload.get(field_name)
    if not isinstance(raw_values, list) or not raw_values:
        raise ValueError("bundle plan %s are required" % field_name.replace("_", " "))
    values = tuple(str(item or "").strip() for item in raw_values)
    if any(not item for item in values):
        raise ValueError("bundle plan %s are invalid" % field_name.replace("_", " "))
    identity = tuple((normalize or (lambda item: item))(item) for item in values)
    if len(set(identity)) != len(identity):
        raise ValueError("bundle plan %s are duplicated" % field_name.replace("_", " "))
    payload[field_name] = list(values)
    return values


def load_bundle_plan(path, application_isolated=False):
    plan_path = Path(path)
    if not plan_path.is_file():
        raise ValueError("bundle plan not found")
    try:
        payload = json.loads(plan_path.read_text(encoding="ascii"))
    except (OSError, ValueError) as exc:
        raise ValueError("bundle plan is invalid: %s" % exc)
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("unsupported bundle plan")
    distributions = _required_unique_ids(
        payload,
        "project_distribution_ids",
        normalize=normalize_distribution_name,
    )
    if application_isolated:
        application_distributions = _required_unique_ids(
            payload,
            "application_project_distribution_ids",
            normalize=normalize_distribution_name,
        )
        application_requirements = _required_unique_ids(
            payload,
            "application_runtime_requirements",
        )
        application_entries = _required_unique_ids(
            payload,
            "application_registration_entries",
        )
        project_names = set(normalize_distribution_name(item) for item in distributions)
        if any(
            normalize_distribution_name(item) not in project_names
            for item in application_distributions
        ):
            raise ValueError("bundle plan application distributions are outside project closure")
        runtime_capabilities = set(
            _required_unique_ids(payload, "runtime_capability_ids")
        )
        if any(item not in runtime_capabilities for item in application_requirements):
            raise ValueError("bundle plan application requirements are outside runtime closure")
        registration_entries = set(_required_unique_ids(payload, "registration_entries"))
        if any(item not in registration_entries for item in application_entries):
            raise ValueError("bundle plan application entries are outside registration closure")
        distributions = application_distributions
    return payload, distributions
