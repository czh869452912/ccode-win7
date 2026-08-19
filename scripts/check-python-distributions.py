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

try:
    from bundle_plan import load_bundle_plan, normalize_distribution_name
except ImportError:  # pragma: no cover - module loading by a test harness
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from bundle_plan import load_bundle_plan, normalize_distribution_name

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
        "workspace_dependencies": (),
        "allow_other_dependencies": False,
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
        "workspace_dependencies": (),
        "allow_other_dependencies": False,
    },
    {
        "name": "embedagent-host",
        "version": "0.1.0",
        "required_prefixes": ("embedagent_host/",),
        "forbidden_prefixes": ("embedagent/",),
        "forbidden_dependencies": ("pywebview",),
        "workspace_dependencies": ("embedagent-core", "embedagent-protocol"),
        "allow_other_dependencies": False,
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
        "workspace_dependencies": (),
        "allow_other_dependencies": False,
    },
    {
        "name": "embedagent-workflow-cpp",
        "version": "0.1.0",
        "required_prefixes": ("embedagent_workflow_cpp/",),
        "forbidden_prefixes": (
            "embedagent_core/",
            "embedagent_host/",
            "embedagent_protocol/",
            "embedagent/",
        ),
        "forbidden_dependencies": (),
        "workspace_dependencies": ("embedagent-core", "embedagent-protocol"),
        "allow_other_dependencies": False,
    },
    {
        "name": "embedagent-shell",
        "version": "0.1.0",
        "required_prefixes": ("embedagent/",),
        "forbidden_prefixes": (
            "embedagent_core/",
            "embedagent_protocol/",
            "embedagent_host/",
            "embedagent/protocol/",
            "embedagent/frontend/gui/webapp/",
            "embedagent_workflow_cpp/",
        ),
        "forbidden_dependencies": (),
        "workspace_dependencies": (
            "embedagent-core",
            "embedagent-protocol",
            "embedagent-host",
        ),
        "allow_other_dependencies": True,
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
    + ("COM\u00b9", "COM\u00b2", "COM\u00b3", "LPT\u00b9", "LPT\u00b2", "LPT\u00b3")
)
MAX_ARTIFACT_SIZE = 256 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 10000
MAX_FILENAME_BYTES = 4 * 1024 * 1024
MAX_METADATA_SIZE = 1024 * 1024


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", required=True, help="Directory containing wheel files")
    parser.add_argument("--bundle-plan", default="", help="Compiled bundle plan JSON")
    parser.add_argument(
        "--application-isolated",
        action="store_true",
        help="Validate only the plan-selected application runtime wheel closure",
    )
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


def python_module_name(name):
    if not name.endswith(".py"):
        return ""
    module_path = name[:-3]
    if module_path.endswith("/__init__"):
        module_path = module_path[: -len("/__init__")]
    parts = module_path.split("/")
    if not parts or any(not part.isidentifier() for part in parts):
        return ""
    return ".".join(parts)


def portable_case_key(value):
    key = []
    for character in value:
        upper = character.upper()
        if len(upper) == 1:
            key.append(upper)
        else:
            key.append(character)
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


def is_unconditional_exact_workspace_pin(requirement, expected_name, version):
    text = str(requirement or "").strip()
    match = DEPENDENCY_NAME.match(text)
    if match is None or normalize_distribution_name(match.group(1)) != expected_name:
        return False
    remainder = text[match.end() :].strip()
    if ";" in remainder:
        return False
    if remainder.startswith("(") and remainder.endswith(")"):
        remainder = remainder[1:-1].strip()
    return re.fullmatch(r"==\s*%s" % re.escape(version), remainder) is not None


def validate_dependency_contract(requirements, spec, report):
    expected = tuple(spec["workspace_dependencies"])
    expected_set = set(expected)
    forbidden = set(spec["forbidden_dependencies"])
    grouped = {}
    unexpected_names = []
    forbidden_names = []
    for requirement in requirements:
        name = dependency_name(requirement)
        grouped.setdefault(name, []).append(requirement)
        if name in expected_set or spec["allow_other_dependencies"]:
            continue
        destination = forbidden_names if name in forbidden else unexpected_names
        if name not in destination:
            destination.append(name)

    for name in sorted(forbidden_names):
        report["errors"].append(error("forbidden_dependency", "forbidden dependency: %s" % name))
    for name in sorted(unexpected_names):
        report["errors"].append(
            error(
                "unexpected_runtime_dependency",
                "unexpected runtime dependency: %s" % (name or "invalid"),
            )
        )

    for name in expected:
        matches = grouped.get(name, [])
        if not matches:
            report["errors"].append(
                error(
                    "workspace_dependency_missing",
                    "workspace dependency missing: %s==%s" % (name, spec["version"]),
                )
            )
        elif len(matches) > 1:
            report["errors"].append(
                error(
                    "workspace_dependency_duplicate",
                    "workspace dependency appears more than once: %s" % name,
                )
            )
        elif not is_unconditional_exact_workspace_pin(matches[0], name, spec["version"]):
            report["errors"].append(
                error(
                    "workspace_dependency_invalid",
                    "workspace dependency must be an unconditional exact pin: %s==%s"
                    % (name, spec["version"]),
                )
            )


def empty_distribution_report(spec):
    return {
        "name": spec["name"],
        "wheel": "",
        "metadata_name": "",
        "requires_dist": [],
        "python_modules": [],
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
    validate_dependency_contract(requirements, spec, report)


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
            report["python_modules"] = sorted(
                set(
                    module_name
                    for _info, raw_name, _canonical in members
                    for module_name in (python_module_name(raw_name),)
                    if module_name
                )
            )
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


def _application_scope(plan):
    if not isinstance(plan, dict):
        raise ValueError("application-isolated validation requires a bundle plan")
    distributions = plan.get("application_project_distribution_ids")
    requirements = plan.get("application_runtime_requirements")
    entries = plan.get("application_registration_entries")
    for field_name, values in (
        ("application_project_distribution_ids", distributions),
        ("application_runtime_requirements", requirements),
        ("application_registration_entries", entries),
    ):
        if not isinstance(values, list) or not values:
            raise ValueError("bundle plan %s are required" % field_name.replace("_", " "))
        normalized = tuple(str(item or "").strip() for item in values)
        if any(not item for item in normalized) or len(set(normalized)) != len(normalized):
            raise ValueError("bundle plan %s are invalid" % field_name.replace("_", " "))
    return tuple(str(item).strip() for item in distributions)


def _registration_entry_owner(plan, distributions):
    errors = []
    owners = []
    owners_by_module = {}
    for distribution in distributions:
        distribution_name = normalize_distribution_name(distribution["name"])
        for module_name in distribution.get("python_modules") or ():
            owners_by_module.setdefault(module_name, set()).add(distribution_name)
    for entry in plan.get("application_registration_entries") or ():
        module_name, separator, callable_name = str(entry or "").partition(":")
        matching = (
            sorted(owners_by_module.get(module_name, set())) if separator and callable_name else []
        )
        if len(matching) != 1:
            errors.append(
                error(
                    "application_registration_owner_invalid",
                    "application registration entry must have exactly one selected wheel owner",
                )
            )
        else:
            owners.append(matching[0])
    unique_owners = tuple(sorted(set(owners)))
    if len(unique_owners) != 1:
        errors.append(
            error(
                "application_registration_owner_invalid",
                "application registration entries must resolve to one selected wheel owner",
            )
        )
        return "", errors
    return unique_owners[0], errors


def _application_distribution_closure(
    plan,
    selected,
    distributions,
    expected_by_name,
):
    owner, errors = _registration_entry_owner(plan, distributions)
    if not owner:
        return "", (), errors

    reports_by_name = {
        normalize_distribution_name(item["name"]): item for item in distributions
    }
    ordered = []
    visiting = set()

    def visit(distribution_name):
        if distribution_name in ordered:
            return
        if distribution_name in visiting:
            errors.append(
                error(
                    "application_distribution_dependency_cycle",
                    "application wheel dependencies contain a cycle",
                )
            )
            return
        visiting.add(distribution_name)
        report = reports_by_name.get(distribution_name)
        if report is not None:
            workspace_dependencies = set()
            for requirement in report.get("requires_dist") or ():
                required_name = dependency_name(requirement)
                if required_name in expected_by_name:
                    workspace_dependencies.add(required_name)
            for required_name in sorted(workspace_dependencies):
                visit(required_name)
        visiting.remove(distribution_name)
        ordered.append(distribution_name)

    visit(owner)
    planned = tuple(normalize_distribution_name(item) for item in selected)
    derived = tuple(ordered)
    if set(planned) != set(derived):
        errors.append(
            error(
                "application_distribution_closure_mismatch",
                "application wheel closure does not match registration owner dependencies",
            )
        )
    return owner, derived, errors


def build_report(
    dist_dir,
    selected_distributions=None,
    plan=None,
    application_isolated=False,
):
    if application_isolated:
        selected_distributions = _application_scope(plan)
    if selected_distributions is None:
        selected_distributions = tuple(spec["name"] for spec in EXPECTED)
    selected = tuple(str(item or "").strip() for item in selected_distributions)
    if len(
        set(normalize_distribution_name(item) for item in selected)
    ) != len(selected):
        return {
            "schema_version": 1,
            "dist_dir": str(dist_dir),
            "ok": False,
            "errors": [error("duplicate_planned_distribution", "planned wheel set")],
            "verified_wheels": [],
            "distributions": [],
            "selected_distributions": list(selected),
        }
    expected_by_name = {
        normalize_distribution_name(spec["name"]): spec for spec in EXPECTED
    }
    unknown = [
        item for item in selected if normalize_distribution_name(item) not in expected_by_name
    ]
    if unknown:
        return {
            "schema_version": 1,
            "dist_dir": str(dist_dir),
            "ok": False,
            "errors": [error("unknown_planned_distribution", item) for item in unknown],
            "verified_wheels": [],
            "distributions": [],
            "selected_distributions": list(selected),
        }
    wheels = []
    if dist_dir.is_dir():
        wheels = sorted(dist_dir.glob("*.whl"), key=lambda path: path.name)
    expected_names = {normalize_distribution_name(item): item for item in selected}
    wheel_set_errors = []
    for wheel in wheels:
        identity = wheel_filename_identity(wheel)
        if identity is None:
            wheel_set_errors.append(
                error(
                    "wheel_filename_unrecognized",
                    "unrecognized wheel filename: %s" % wheel.name,
                )
            )
            continue
        normalized_name = normalize_distribution_name(identity["distribution"])
        if normalized_name not in expected_names:
            wheel_set_errors.append(error("unplanned_wheel", "unplanned wheel: %s" % wheel.name))
    distributions = [
        inspect_distribution(expected_by_name[normalize_distribution_name(item)], wheels)
        for item in selected
    ]
    application_owner = ""
    application_closure = ()
    if application_isolated:
        (
            application_owner,
            application_closure,
            application_errors,
        ) = _application_distribution_closure(
            plan,
            selected,
            distributions,
            expected_by_name,
        )
        wheel_set_errors.extend(application_errors)
    report = {
        "schema_version": 1,
        "dist_dir": str(dist_dir),
        "ok": not wheel_set_errors and all(not item["errors"] for item in distributions),
        "errors": wheel_set_errors,
        "verified_wheels": [],
        "distributions": distributions,
        "selected_distributions": list(selected),
    }
    if application_isolated:
        report["scope"] = "application"
        report["application_registration_owner"] = (
            expected_by_name[application_owner]["name"] if application_owner else ""
        )
        report["derived_application_project_distribution_ids"] = [
            expected_by_name[item]["name"] for item in application_closure
        ]
        report["runtime_requirements"] = list(plan["application_runtime_requirements"])
        report["registration_entries"] = list(plan["application_registration_entries"])
    if report["ok"]:
        report["verified_wheels"] = [item["wheel"] for item in distributions]
    return report


def main(argv=None):
    args = parse_args(argv)
    try:
        if args.application_isolated and not args.bundle_plan:
            raise ValueError("application-isolated validation requires a bundle plan")
        selected = None
        plan = None
        if args.bundle_plan:
            plan, selected = load_bundle_plan(
                args.bundle_plan,
                application_isolated=args.application_isolated,
            )
        report = build_report(
            Path(args.dist_dir),
            selected,
            plan=plan,
            application_isolated=args.application_isolated,
        )
    except ValueError as exc:
        report = {
            "schema_version": 1,
            "dist_dir": str(Path(args.dist_dir)),
            "ok": False,
            "errors": [error("bundle_plan_invalid", str(exc))],
            "verified_wheels": [],
            "distributions": [],
        }
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
