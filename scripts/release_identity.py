"""Canonical release identity helpers for offline packaging."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "password",
    "secret",
    "token",
    "credential",
    "prompt",
    "raw_output",
)


def canonical_json(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def sha256_file(path):
    file_path = Path(path)
    if not file_path.is_file():
        raise ValueError("file does not exist: %s" % file_path)
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(root, excluded_names=()):
    tree_root = Path(root)
    if not tree_root.is_dir():
        raise ValueError("tree root does not exist: %s" % tree_root)
    excluded = {str(item).replace("\\", "/") for item in excluded_names}
    records = []
    for path in sorted(tree_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(tree_root).as_posix()
        if relative in excluded or path.name in excluded:
            continue
        records.append({"path": relative, "sha256": sha256_file(path)})
    return hashlib.sha256(canonical_json(records).encode("ascii")).hexdigest()


def _assert_safe_value(value, path="root"):
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in _SENSITIVE_KEY_PARTS):
                raise ValueError("sensitive identity key: %s" % key)
            _assert_safe_value(child, "%s.%s" % (path, key))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_safe_value(child, "%s[%s]" % (path, index))


def _normalize_wheels(wheels, expected_distributions):
    if isinstance(wheels, Mapping):
        entries = list(wheels.items())
    else:
        entries = list(wheels)
    normalized = []
    seen = set()
    for entry in entries:
        if isinstance(entry, Mapping):
            name = entry.get("name")
            path = entry.get("path")
        else:
            try:
                name, path = entry
            except (TypeError, ValueError):
                raise ValueError("wheel entry must contain name and path")
        name = str(name or "").strip()
        if not name:
            raise ValueError("wheel name is required")
        if name in seen:
            raise ValueError("duplicate wheel: %s" % name)
        seen.add(name)
        wheel_path = Path(path)
        filename = wheel_path.name
        if not filename or filename in (".", "..") or "/" in filename or "\\" in filename:
            raise ValueError("unsafe wheel filename: %s" % filename)
        normalized.append(
            {"name": name, "filename": filename, "sha256": sha256_file(wheel_path)}
        )
    expected = tuple(expected_distributions)
    normalized.sort(
        key=lambda item: expected.index(item["name"])
        if item["name"] in expected
        else len(expected)
    )
    names = [item["name"] for item in normalized]
    if tuple(names) != expected:
        raise ValueError("wheel set must match bundle plan project distributions")
    return normalized


def _optional_hash(path, tree=False, excluded_names=()):
    if path is None:
        return None
    candidate = Path(path)
    if not candidate.exists():
        return None
    return sha256_tree(candidate, excluded_names) if tree else sha256_file(candidate)


def _load_bundle_plan(path):
    plan_path = Path(path)
    if not plan_path.is_file():
        raise ValueError("bundle plan does not exist: %s" % plan_path)
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError("bundle plan is invalid")
    if not isinstance(plan, dict) or plan.get("schema_version") != 1:
        raise ValueError("bundle plan must use schema version 1")
    for field in ("flavor_id", "target_id", "agent_lock_sha256"):
        if not isinstance(plan.get(field), str) or not plan[field]:
            raise ValueError("bundle plan field is required: %s" % field)
    project_distributions = plan.get("project_distribution_ids")
    if (
        not isinstance(project_distributions, list)
        or not project_distributions
        or any(not isinstance(item, str) or not item for item in project_distributions)
        or len(project_distributions) != len(set(project_distributions))
    ):
        raise ValueError("bundle plan project_distribution_ids is invalid")
    for field in ("shell_ids", "gate_ids"):
        values = plan.get(field)
        if (
            not isinstance(values, list)
            or any(not isinstance(item, str) or not item for item in values)
            or len(values) != len(set(values))
        ):
            raise ValueError("bundle plan array is invalid: %s" % field)
    return plan


def load_bundle_plan(path):
    """Load and validate the compiled plan used by release identity tooling."""
    return _load_bundle_plan(path)


def build_release_identity(
    source_revision,
    version,
    profile,
    wheels,
    gui_static_root,
    asset_manifest_path,
    runtime_contract_path,
    bundle_plan_path,
    bundle_root=None,
    zip_path=None,
    tool_metadata=None,
):
    if not str(source_revision).strip() or not str(version).strip():
        raise ValueError("source revision and version are required")
    plan = _load_bundle_plan(bundle_plan_path)
    project_distributions = tuple(plan["project_distribution_ids"])
    normalized_wheels = _normalize_wheels(wheels, project_distributions)
    has_gui = "gui" in plan["shell_ids"]
    if has_gui:
        if gui_static_root is None or not Path(gui_static_root).is_dir():
            raise ValueError("GUI static root is required by the bundle plan")
        gui_static_sha256 = sha256_tree(gui_static_root)
    else:
        gui_static_sha256 = None
    identity = {
        "schema_version": 2,
        "source_revision": str(source_revision).strip(),
        "version": str(version).strip(),
        "profile": str(profile).strip(),
        "flavor_id": plan["flavor_id"],
        "target_id": plan["target_id"],
        "bundle_plan_sha256": sha256_file(bundle_plan_path),
        "agent_lock_sha256": plan["agent_lock_sha256"],
        "gate_ids": list(plan["gate_ids"]),
        "project_distributions": list(project_distributions),
        "wheels": normalized_wheels,
        "gui_static_sha256": gui_static_sha256,
        "asset_manifest_sha256": _optional_hash(asset_manifest_path),
        "runtime_contract_sha256": _optional_hash(runtime_contract_path),
        "bundle_sha256": _optional_hash(bundle_root, tree=True),
        "zip_sha256": _optional_hash(zip_path),
        "tool_metadata": dict(tool_metadata or {}),
    }
    _assert_safe_value(identity)
    return identity


def _diff_values(expected, actual, path="root", mismatches=None):
    if mismatches is None:
        mismatches = []
    if type(expected) is not type(actual):
        mismatches.append(path)
        return mismatches
    if isinstance(expected, Mapping):
        keys = sorted(set(expected) | set(actual))
        for key in keys:
            if key not in expected or key not in actual:
                mismatches.append("%s.%s" % (path, key))
            else:
                _diff_values(expected[key], actual[key], "%s.%s" % (path, key), mismatches)
    elif isinstance(expected, (list, tuple)):
        if len(expected) != len(actual):
            mismatches.append(path)
        else:
            for index, (left, right) in enumerate(zip(expected, actual)):
                _diff_values(left, right, "%s[%s]" % (path, index), mismatches)
    elif expected != actual:
        mismatches.append(path)
    return mismatches


def compare_release_identity(expected, actual):
    mismatches = _diff_values(expected, actual)
    normalized = [item[5:] if item.startswith("root.") else item for item in mismatches]
    return {"ok": not normalized, "mismatches": normalized}
