#!/usr/bin/env python3
"""Validate Python wheel boundaries for the split EmbedAgent distributions."""

import argparse
import json
import re
import sys
import zipfile
from email import policy
from email.parser import BytesParser
from pathlib import Path

EXPECTED = (
    {
        "name": "embedagent-core",
        "version": "0.1.0",
        "required_prefixes": ("embedagent_core/",),
        "forbidden_prefixes": (
            "embedagent_host/",
            "embedagent_protocol/",
            "embedagent/",
        ),
        "forbidden_dependencies": ("fastapi", "pywebview", "uvicorn", "websockets"),
    },
    {
        "name": "embedagent-protocol",
        "version": "0.1.0",
        "required_prefixes": ("embedagent_protocol/",),
        "forbidden_prefixes": (
            "embedagent_core/",
            "embedagent_host/",
            "embedagent/",
        ),
        "forbidden_dependencies": (),
    },
    {
        "name": "embedagent-host",
        "version": "0.1.0",
        "required_prefixes": ("embedagent_host/",),
        "forbidden_prefixes": (
            "embedagent/frontend/",
            "embedagent/workflow_packages/",
        ),
        "forbidden_dependencies": ("pywebview",),
    },
    {
        "name": "embedagent-composition",
        "version": "0.1.0",
        "required_prefixes": ("embedagent_composition/",),
        "forbidden_prefixes": (
            "embedagent_core/",
            "embedagent_host/",
            "embedagent_protocol/",
            "embedagent/",
        ),
        "forbidden_dependencies": (),
    },
)

DEPENDENCY_NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")
WHEEL_COMPONENT = re.compile(r"^[A-Za-z0-9_.]+$")
WHEEL_BUILD_TAG = re.compile(r"^(\d+)(.*)$")
WINDOWS_FORBIDDEN_CHARS = frozenset('<>:"\\|?*')
WINDOWS_RESERVED_DEVICE_NAMES = frozenset(
    ("CON", "NUL", "PRN", "AUX", "CLOCK$")
    + tuple("COM%d" % number for number in range(1, 10))
    + tuple("LPT%d" % number for number in range(1, 10))
)
MAX_ARTIFACT_SIZE = 256 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 10000
MAX_FILENAME_BYTES = 4 * 1024 * 1024
MAX_METADATA_SIZE = 1024 * 1024


def normalize_distribution_name(name):
    return re.sub(r"[-_.]+", "-", str(name or "")).lower()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", required=True, help="Directory containing wheel files")
    return parser.parse_args(argv)


def error(code, detail):
    return {"code": code, "detail": detail}


def wheel_distribution_name(path):
    filename = path.name
    if not filename.lower().endswith(".whl"):
        return ""
    stem = filename[:-4]
    parts = stem.split("-")
    if len(parts) < 5:
        return ""
    return normalize_distribution_name(parts[0])


def wheel_filename_identity(path):
    filename = path.name
    if not filename.endswith(".whl"):
        return None
    parts = filename[:-4].split("-")
    if len(parts) == 5:
        distribution, version, python_tag, abi_tag, platform_tag = parts
    elif len(parts) == 6:
        distribution, version, build_tag, python_tag, abi_tag, platform_tag = parts
        if WHEEL_BUILD_TAG.fullmatch(build_tag) is None:
            return None
    else:
        return None
    components = (distribution, version, python_tag, abi_tag, platform_tag)
    if any(WHEEL_COMPONENT.fullmatch(component) is None for component in components):
        return None
    return {"distribution": distribution, "version": version}


def metadata_path(name):
    return name.count("/") == 1 and name.endswith(".dist-info/METADATA")


def portable_case_key(value):
    key = []
    for character in value:
        candidates = [character]
        lower = character.lower()
        upper = character.upper()
        if len(lower) == 1:
            candidates.append(lower)
        if len(upper) == 1:
            candidates.append(upper)
        key.append(min(candidates, key=ord))
    return "".join(key)


def is_windows_reserved_device_name(segment):
    base = segment.split(".", 1)[0].rstrip(" ")
    return portable_case_key(base) in WINDOWS_RESERVED_DEVICE_NAMES


def canonical_member_path(raw_name):
    if not raw_name or raw_name.startswith("/") or "\x00" in raw_name or "\\" in raw_name:
        return None
    if any(ord(character) < 32 for character in raw_name):
        return None
    if any(character in WINDOWS_FORBIDDEN_CHARS for character in raw_name):
        return None
    raw_parts = raw_name.split("/")
    if any(part in (".", "..") for part in raw_parts):
        return None
    canonical_parts = []
    for part in raw_parts:
        if not part:
            continue
        trimmed_part = part.rstrip(" .")
        if not trimmed_part or is_windows_reserved_device_name(trimmed_part):
            return None
        canonical_part = portable_case_key(trimmed_part)
        canonical_parts.append(canonical_part)
    if not canonical_parts:
        return None
    return "/".join(canonical_parts)


def canonical_prefix(prefix):
    return canonical_member_path(prefix.rstrip("/"))


def path_has_prefix(path, prefix):
    canonical = canonical_prefix(prefix)
    return canonical is not None and (path == canonical or path.startswith(canonical + "/"))


def validate_archive_members(infos, report):
    canonical_paths = []
    seen = {}
    for info in infos:
        raw_name = info.orig_filename
        canonical = canonical_member_path(raw_name)
        if canonical is None:
            report["errors"].append(
                error("member_path_invalid", "wheel contains an unsafe member path")
            )
            return None
        if canonical in seen:
            report["errors"].append(
                error("member_path_collision", "wheel member paths collide on Windows")
            )
            return None
        seen[canonical] = raw_name
        canonical_paths.append((info, raw_name, canonical))
    return canonical_paths


def dependency_name(requirement):
    match = DEPENDENCY_NAME.match(str(requirement or "").lstrip())
    if match is None:
        return ""
    return normalize_distribution_name(match.group(1))


def empty_distribution_report(spec):
    return {
        "name": spec["name"],
        "wheel": "",
        "metadata_name": "",
        "requires_dist": [],
        "required_prefixes": list(spec["required_prefixes"]),
        "forbidden_prefixes": list(spec["forbidden_prefixes"]),
        "errors": [],
    }


def parse_metadata(wheel, info, report, spec):
    if info.file_size > MAX_METADATA_SIZE:
        report["errors"].append(
            error("metadata_invalid", "METADATA exceeds the 1 MiB validation limit")
        )
        return

    try:
        payload = wheel.read(info)
        message = BytesParser(policy=policy.default).parsebytes(payload, headersonly=True)
    except Exception:
        report["errors"].append(error("metadata_invalid", "METADATA could not be parsed"))
        return

    names = message.get_all("Name", [])
    metadata_versions = message.get_all("Metadata-Version", [])
    versions = message.get_all("Version", [])
    required_values = names + metadata_versions + versions
    if (
        message.defects
        or len(names) != 1
        or len(metadata_versions) != 1
        or len(versions) != 1
        or any(not str(value).strip() for value in required_values)
    ):
        report["errors"].append(
            error(
                "metadata_invalid",
                "METADATA must contain one valid Name, Version, and Metadata-Version",
            )
        )
        return

    reported_name = str(names[0]).strip()
    report["metadata_name"] = reported_name
    if normalize_distribution_name(reported_name) != normalize_distribution_name(spec["name"]):
        report["errors"].append(
            error(
                "metadata_name_mismatch", "METADATA Name does not match the expected distribution"
            )
        )

    reported_version = str(versions[0]).strip()
    if reported_version != spec["version"]:
        report["errors"].append(
            error(
                "metadata_version_mismatch",
                "METADATA Version does not match the expected distribution version",
            )
        )

    requirements = [str(value).strip() for value in message.get_all("Requires-Dist", [])]
    report["requires_dist"] = requirements
    forbidden_dependencies = set(spec["forbidden_dependencies"])
    seen_forbidden = []
    for requirement in requirements:
        normalized_name = dependency_name(requirement)
        if normalized_name in forbidden_dependencies and normalized_name not in seen_forbidden:
            seen_forbidden.append(normalized_name)
    for normalized_name in sorted(seen_forbidden):
        report["errors"].append(
            error("forbidden_dependency", "forbidden dependency: %s" % normalized_name)
        )


def inspect_wheel(path, spec, report):
    try:
        artifact_size = path.stat().st_size
    except OSError:
        report["errors"].append(error("wheel_invalid", "wheel could not be read"))
        return
    if artifact_size > MAX_ARTIFACT_SIZE:
        report["errors"].append(
            error("artifact_too_large", "wheel exceeds the artifact size limit")
        )
        return

    try:
        with zipfile.ZipFile(str(path), "r") as wheel:
            infos = wheel.infolist()
            if len(infos) > MAX_ARCHIVE_ENTRIES:
                report["errors"].append(
                    error("archive_entry_limit", "wheel exceeds the archive entry limit")
                )
                return
            try:
                filename_bytes = sum(len(info.orig_filename.encode("utf-8")) for info in infos)
            except UnicodeError:
                report["errors"].append(
                    error("member_path_invalid", "wheel contains an invalid member name")
                )
                return
            if filename_bytes > MAX_FILENAME_BYTES:
                report["errors"].append(
                    error(
                        "archive_filename_limit",
                        "wheel exceeds the total filename byte limit",
                    )
                )
                return

            members = validate_archive_members(infos, report)
            if members is None:
                return
            archive_paths = [canonical for _info, _raw, canonical in members]
            metadata_members = [
                (info, raw_name)
                for info, raw_name, _canonical in members
                if metadata_path(raw_name)
            ]

            for prefix in spec["required_prefixes"]:
                if not any(path_has_prefix(name, prefix) for name in archive_paths):
                    report["errors"].append(
                        error("required_prefix_missing", "required prefix missing: %s" % prefix)
                    )
            for prefix in spec["forbidden_prefixes"]:
                if any(path_has_prefix(name, prefix) for name in archive_paths):
                    report["errors"].append(
                        error("forbidden_prefix", "forbidden prefix present: %s" % prefix)
                    )

            if not metadata_members:
                report["errors"].append(error("metadata_missing", "wheel has no METADATA"))
            elif len(metadata_members) > 1:
                report["errors"].append(
                    error("metadata_ambiguous", "wheel has more than one METADATA entry")
                )
            else:
                metadata_info, metadata_name = metadata_members[0]
                metadata_root = metadata_name.split("/", 1)[0]
                dist_info_roots = {
                    raw_name.split("/", 1)[0]
                    for _info, raw_name, _canonical in members
                    if raw_name.split("/", 1)[0].endswith(".dist-info")
                }
                if dist_info_roots != {metadata_root}:
                    report["errors"].append(
                        error(
                            "dist_info_identity_mismatch",
                            "wheel must contain one matching dist-info identity",
                        )
                    )
                    return
                dist_info_stem = metadata_root[: -len(".dist-info")]
                if "-" not in dist_info_stem:
                    report["errors"].append(
                        error(
                            "dist_info_identity_mismatch",
                            "dist-info identity does not match the expected distribution",
                        )
                    )
                    return
                dist_info_name, dist_info_version = dist_info_stem.rsplit("-", 1)
                if (
                    normalize_distribution_name(dist_info_name)
                    != normalize_distribution_name(spec["name"])
                    or dist_info_version != spec["version"]
                ):
                    report["errors"].append(
                        error(
                            "dist_info_identity_mismatch",
                            "dist-info identity does not match the expected distribution",
                        )
                    )
                    return
                parse_metadata(wheel, metadata_info, report, spec)
    except Exception:
        report["errors"].append(error("wheel_invalid", "wheel could not be read as a ZIP archive"))


def inspect_distribution(spec, wheels):
    report = empty_distribution_report(spec)
    expected_name = normalize_distribution_name(spec["name"])
    candidates = [path for path in wheels if wheel_distribution_name(path) == expected_name]

    if not candidates:
        report["errors"].append(error("wheel_missing", "expected wheel was not found"))
        return report
    if len(candidates) > 1:
        report["errors"].append(
            error(
                "wheel_ambiguous",
                "multiple wheels found: %s" % ", ".join(path.name for path in candidates),
            )
        )
        return report

    report["wheel"] = candidates[0].name
    identity = wheel_filename_identity(candidates[0])
    if (
        identity is None
        or normalize_distribution_name(identity["distribution"])
        != normalize_distribution_name(spec["name"])
        or identity["version"] != spec["version"]
    ):
        report["errors"].append(
            error(
                "wheel_filename_invalid",
                "wheel filename identity does not match the expected distribution",
            )
        )
        return report
    inspect_wheel(candidates[0], spec, report)
    return report


def build_report(dist_dir):
    wheels = []
    if dist_dir.is_dir():
        wheels = sorted(dist_dir.glob("*.whl"), key=lambda path: path.name)
    distributions = [inspect_distribution(spec, wheels) for spec in EXPECTED]
    return {
        "schema_version": 1,
        "dist_dir": str(dist_dir),
        "ok": all(not item["errors"] for item in distributions),
        "distributions": distributions,
    }


def main(argv=None):
    args = parse_args(argv)
    report = build_report(Path(args.dist_dir))
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
