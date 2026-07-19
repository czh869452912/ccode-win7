#!/usr/bin/env python3
"""Compare two independently assembled release bundle trees."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path


def _load_release_identity_module():
    path = Path(__file__).resolve().with_name("release_identity.py")
    spec = importlib.util.spec_from_file_location("embedagent_release_identity", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_RELEASE_IDENTITY = _load_release_identity_module()
EXPECTED_DISTRIBUTIONS = _RELEASE_IDENTITY.EXPECTED_DISTRIBUTIONS
canonical_json = _RELEASE_IDENTITY.canonical_json
compare_release_identity = _RELEASE_IDENTITY.compare_release_identity


DEFAULT_EXCLUDED_PATHS = (
    "manifests/checksums.txt",
    "manifests/cpp-smoke-report.json",
    "manifests/evidence/acceptance-report.json",
    "manifests/evidence/expected-bundle-hashes.json",
    "manifests/evidence/win7-evidence.json",
    "manifests/deps-report.json",
)
DEFAULT_NORMALIZED_JSON_FIELDS = {
    "manifests/bundle-manifest.json": (
        "generated_at",
        "built_at",
        "project_root",
        "build_root",
        "bundle_root",
        "staging_bundle_root",
        "sources_root",
        "zip_path",
        "asset_manifest_path",
        "source_path",
        "cache_archive_path",
        "wheelhouse_path",
        "identity_path",
        "deps_report_path",
        "report_path",
        "output_root",
        "staged_path",
        "staging_bundle_root",
        "sources_root",
        "zip_path",
        "built_at",
    )
}


def _sha256_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_json(value, ignored_keys):
    if isinstance(value, dict):
        return {
            key: _normalize_json(child, ignored_keys)
            for key, child in value.items()
            if key not in ignored_keys
        }
    if isinstance(value, list):
        return [_normalize_json(child, ignored_keys) for child in value]
    return value


def _comparison_settings(fixture_path=None):
    excluded = list(DEFAULT_EXCLUDED_PATHS)
    normalized = {path: tuple(fields) for path, fields in DEFAULT_NORMALIZED_JSON_FIELDS.items()}
    if fixture_path:
        fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
        excluded = [
            str(item).replace("\\", "/") for item in fixture.get("excluded_paths", excluded)
        ]
        normalized = {
            str(path).replace("\\", "/"): tuple(fields)
            for path, fields in fixture.get("normalized_json_fields", normalized).items()
        }
    return tuple(sorted(set(excluded))), normalized


def canonical_bundle_records(root, excluded_paths=(), normalized_json_fields=None):
    bundle_root = Path(root)
    if not bundle_root.is_dir():
        raise ValueError("bundle root does not exist")
    excluded = {str(item).replace("\\", "/") for item in excluded_paths}
    normalized_json_fields = normalized_json_fields or {}
    records = []
    for path in sorted(bundle_root.rglob("*")):
        if path.is_symlink():
            raise ValueError("bundle contains a symbolic link")
        if not path.is_file():
            continue
        relative = path.relative_to(bundle_root).as_posix()
        if relative in excluded:
            continue
        ignored_keys = set(normalized_json_fields.get(relative, ()))
        if ignored_keys:
            value = json.loads(path.read_text(encoding="utf-8"))
            normalized = _normalize_json(value, ignored_keys)
            digest = _sha256_bytes(canonical_json(normalized).encode("ascii"))
        else:
            digest = _sha256_file(path)
        records.append({"path": relative, "sha256": digest})
    return records


def _read_json(path, label, mismatches):
    candidate = Path(path)
    if not candidate.is_file():
        mismatches.append("%s.missing" % label)
        return None
    try:
        value = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        mismatches.append("%s.invalid" % label)
        return None
    if not isinstance(value, dict):
        mismatches.append("%s.invalid" % label)
        return None
    return value


def _validate_report(report, label, mismatches):
    if report is None:
        return
    required = {
        "profile": "release",
        "execution_kind": "release",
        "config_origin": "production",
    }
    for field, expected in required.items():
        if report.get(field) != expected:
            mismatches.append("%s.%s" % (label, field))
    if report.get("final_status") not in ("READY", "TARGET_READY"):
        mismatches.append("%s.final_status" % label)


def _validate_identity(identity, label, mismatches):
    if identity is None:
        return
    distributions = tuple(identity.get("project_distributions") or ())
    wheels = identity.get("wheels") or ()
    wheel_names = tuple(item.get("name") for item in wheels if isinstance(item, dict))
    if distributions != EXPECTED_DISTRIBUTIONS:
        mismatches.append("%s.project_distributions" % label)
    if wheel_names != EXPECTED_DISTRIBUTIONS or len(wheels) != 6:
        mismatches.append("%s.wheels" % label)


def _tree_digest(records):
    return _sha256_bytes(canonical_json(records).encode("ascii"))


def compare_release_runs(
    first_report,
    second_report,
    first_root,
    second_root,
    fixture_path=None,
):
    mismatches = []
    excluded_paths, normalized_json_fields = _comparison_settings(fixture_path)
    first_report_value = _read_json(first_report, "report.first", mismatches)
    second_report_value = _read_json(second_report, "report.second", mismatches)
    _validate_report(first_report_value, "report.first", mismatches)
    _validate_report(second_report_value, "report.second", mismatches)

    if first_report_value and second_report_value:
        for field in ("source_revision", "profile"):
            if first_report_value.get(field) != second_report_value.get(field):
                mismatches.append("report.%s" % field)

    first_identity = _read_json(
        Path(first_root) / "manifests" / "release-identity.json",
        "identity.first",
        mismatches,
    )
    second_identity = _read_json(
        Path(second_root) / "manifests" / "release-identity.json",
        "identity.second",
        mismatches,
    )
    _validate_identity(first_identity, "identity.first", mismatches)
    _validate_identity(second_identity, "identity.second", mismatches)
    if first_identity and first_report_value:
        if first_identity.get("source_revision") != first_report_value.get("source_revision"):
            mismatches.append("provenance.first.source_revision")
        if first_identity.get("profile") != first_report_value.get("profile"):
            mismatches.append("provenance.first.profile")
    if second_identity and second_report_value:
        if second_identity.get("source_revision") != second_report_value.get("source_revision"):
            mismatches.append("provenance.second.source_revision")
        if second_identity.get("profile") != second_report_value.get("profile"):
            mismatches.append("provenance.second.profile")
    if first_identity and second_identity:
        mismatches.extend(
            "identity.%s" % path
            for path in compare_release_identity(first_identity, second_identity)["mismatches"]
        )

    first_records = None
    second_records = None
    try:
        first_records = canonical_bundle_records(
            first_root,
            excluded_paths=excluded_paths,
            normalized_json_fields=normalized_json_fields,
        )
    except (OSError, ValueError):
        mismatches.append("bundle.first.missing")
    try:
        second_records = canonical_bundle_records(
            second_root,
            excluded_paths=excluded_paths,
            normalized_json_fields=normalized_json_fields,
        )
    except (OSError, ValueError):
        mismatches.append("bundle.second.missing")

    if first_records is not None and second_records is not None:
        first_map = {record["path"]: record["sha256"] for record in first_records}
        second_map = {record["path"]: record["sha256"] for record in second_records}
        for relative in sorted(set(first_map) | set(second_map)):
            if first_map.get(relative) != second_map.get(relative):
                mismatches.append("bundle.%s" % relative)

    unique_mismatches = sorted(set(mismatches))
    return {
        "schema_version": 1,
        "ok": not unique_mismatches,
        "mismatches": unique_mismatches,
        "excluded_paths": list(excluded_paths),
        "first_bundle_sha256": _tree_digest(first_records) if first_records is not None else None,
        "second_bundle_sha256": (
            _tree_digest(second_records) if second_records is not None else None
        ),
    }


def _write_json(path, payload):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp.%s" % os.getpid())
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(str(temporary), str(destination))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-report", required=True)
    parser.add_argument("--second-report", required=True)
    parser.add_argument("--first-root", required=True)
    parser.add_argument("--second-root", required=True)
    parser.add_argument("--fixture", default="")
    parser.add_argument("--json-report", required=True)
    args = parser.parse_args(argv)
    try:
        payload = compare_release_runs(
            args.first_report,
            args.second_report,
            args.first_root,
            args.second_root,
            fixture_path=args.fixture or None,
        )
    except (OSError, ValueError):
        payload = {
            "schema_version": 1,
            "ok": False,
            "mismatches": ["comparison.invalid_configuration"],
            "excluded_paths": [],
            "first_bundle_sha256": None,
            "second_bundle_sha256": None,
        }
    _write_json(args.json_report, payload)
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
