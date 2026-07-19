"""Canonical release identity helpers for offline packaging."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

EXPECTED_DISTRIBUTIONS = (
    "embedagent-core",
    "embedagent-protocol",
    "embedagent-host",
    "embedagent-composition",
    "embedagent-workflow-cpp",
    "embedagent",
)
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


def _normalize_wheels(wheels):
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
    normalized.sort(key=lambda item: EXPECTED_DISTRIBUTIONS.index(item["name"]) if item["name"] in EXPECTED_DISTRIBUTIONS else len(EXPECTED_DISTRIBUTIONS))
    names = [item["name"] for item in normalized]
    if tuple(names) != EXPECTED_DISTRIBUTIONS:
        raise ValueError("wheel set must contain the exact six project distributions")
    return normalized


def _optional_hash(path, tree=False, excluded_names=()):
    if path is None:
        return None
    candidate = Path(path)
    if not candidate.exists():
        return None
    return sha256_tree(candidate, excluded_names) if tree else sha256_file(candidate)


def build_release_identity(
    source_revision,
    version,
    profile,
    wheels,
    gui_static_root,
    asset_manifest_path,
    runtime_contract_path,
    bundle_root=None,
    zip_path=None,
    tool_metadata=None,
):
    normalized_wheels = _normalize_wheels(wheels)
    if not str(source_revision).strip() or not str(version).strip():
        raise ValueError("source revision and version are required")
    identity = {
        "schema_version": 1,
        "source_revision": str(source_revision).strip(),
        "version": str(version).strip(),
        "profile": str(profile).strip(),
        "project_distributions": list(EXPECTED_DISTRIBUTIONS),
        "wheels": normalized_wheels,
        "gui_static_sha256": _optional_hash(gui_static_root, tree=True),
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
