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
        "required_prefixes": ("embedagent_host/",),
        "forbidden_prefixes": (
            "embedagent/frontend/",
            "embedagent/workflow_packages/",
        ),
        "forbidden_dependencies": ("pywebview",),
    },
    {
        "name": "embedagent-composition",
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


def metadata_path(name):
    normalized = name.replace("\\", "/")
    return normalized.count("/") == 1 and normalized.endswith(".dist-info/METADATA")


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
    if message.defects or len(names) != 1 or len(metadata_versions) != 1 or len(versions) != 1:
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
        with zipfile.ZipFile(str(path), "r") as wheel:
            infos = wheel.infolist()
            archive_paths = [info.filename.replace("\\", "/") for info in infos]
            metadata_infos = [info for info in infos if metadata_path(info.filename)]

            for prefix in spec["required_prefixes"]:
                if not any(name.startswith(prefix) for name in archive_paths):
                    report["errors"].append(
                        error("required_prefix_missing", "required prefix missing: %s" % prefix)
                    )
            for prefix in spec["forbidden_prefixes"]:
                if any(name.startswith(prefix) for name in archive_paths):
                    report["errors"].append(
                        error("forbidden_prefix", "forbidden prefix present: %s" % prefix)
                    )

            if not metadata_infos:
                report["errors"].append(error("metadata_missing", "wheel has no METADATA"))
            elif len(metadata_infos) > 1:
                report["errors"].append(
                    error("metadata_ambiguous", "wheel has more than one METADATA entry")
                )
            else:
                parse_metadata(wheel, metadata_infos[0], report, spec)
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
