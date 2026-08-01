from __future__ import unicode_literals

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ACTIVE_LEDGER_PATHS = (
    "docs/development-tracker.md",
    "docs/design-change-log.md",
)

HISTORY_SNAPSHOTS = (
    "docs/archive/documentation-history/development-tracker-2026-08-01.md",
    "docs/archive/documentation-history/design-change-log-2026-08-01.md",
    "docs/archive/documentation-history/implementation-roadmap-2026-08-01.md",
)


def _read(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _active_superpowers_files():
    files = set()
    for relative_root in ("docs/superpowers/specs", "docs/superpowers/plans"):
        root = ROOT / relative_root
        for path in root.glob("*.md"):
            files.add(path.relative_to(ROOT).as_posix())
    return files


def _indexed_superpowers_files():
    text = _read("docs/superpowers/README.md")
    return set(re.findall(r"`(docs/superpowers/(?:specs|plans)/[^`]+[.]md)`", text))


def test_historical_progress_ledgers_are_archived():
    for relative_path in ACTIVE_LEDGER_PATHS:
        assert not (ROOT / relative_path).exists()
    for relative_path in HISTORY_SNAPSHOTS:
        assert (ROOT / relative_path).is_file()


def test_active_superpowers_index_matches_active_slice_files():
    assert (ROOT / "docs/superpowers/README.md").is_file()
    assert _indexed_superpowers_files() == _active_superpowers_files()


def test_current_work_docs_do_not_contain_completion_ledgers():
    for relative_path in (
        "docs/current-status.md",
        "docs/implementation-roadmap.md",
    ):
        text = _read(relative_path)
        forbidden_headings = re.findall(
            r"(?mi)^#{2,3}[^\n]*(?:completion|completed|closeout|已完成|已收口)[^\n]*$",
            text,
        )
        assert forbidden_headings == []


DEFAULT_CONTEXT_BUDGETS = {
    "README.md": 1500,
    "AGENTS.md": 2500,
    "docs/README.md": 1000,
}

REQUIRED_MAP_TARGETS = (
    "docs/overall-solution-architecture.md",
    "docs/implementation-roadmap.md",
    "docs/current-status.md",
    "docs/platform/README.md",
    "docs/platform/agent-core.md",
    "docs/platform/session-runtime.md",
    "docs/platform/tools-and-extensions.md",
    "docs/platform/tool-contracts.md",
    "docs/platform/permissions-and-context.md",
    "docs/platform/permission-model.md",
    "docs/platform/protocol.md",
    "docs/platform/frontend-protocol.md",
    "docs/platform/frontend-gui.md",
    "docs/platform/frontend-tui.md",
    "docs/platform/mode-contract.md",
    "docs/platform/agent-platform-blueprint.md",
    "docs/applications/README.md",
    "docs/applications/cpp-workflow.md",
    "docs/product/README.md",
    "docs/product/packaging-and-deployment.md",
    "docs/guides/win7-release-runbook.md",
    "docs/workflows/code-doc-sync.md",
    "docs/adrs/README.md",
    "docs/archive/README.md",
)


def _word_count(text):
    return len(re.findall(r"\S+", text))


def test_default_loaded_documents_stay_within_context_budgets():
    for relative_path, maximum in DEFAULT_CONTEXT_BUDGETS.items():
        assert _word_count(_read(relative_path)) <= maximum, relative_path


def test_documentation_map_routes_to_existing_authorities():
    map_text = _read("docs/README.md")
    for relative_path in REQUIRED_MAP_TARGETS:
        assert relative_path in map_text
        assert (ROOT / relative_path).is_file()


def test_agent_constitution_keeps_non_negotiable_constraints_reachable():
    text = _read("AGENTS.md")
    for token in (
        "Windows 7",
        ">=3.8,<3.9",
        "offline",
        "C/C++",
        "embedagent-core",
        "embedagent-protocol",
        "embedagent-host",
        "embedagent-composition",
        "embedagent-workflow-cpp",
        "docs/README.md",
    ):
        assert token in text


AUTHORITY_BUDGETS = {
    "docs/overall-solution-architecture.md": 3000,
    "docs/implementation-roadmap.md": 1000,
    "docs/current-status.md": 750,
}

RETIRED_ACTIVE_HISTORY = (
    "docs/pre-release-architecture-debt-audit.md",
    "docs/guides/t3-gui-parity-ledger.md",
)


def test_global_authorities_stay_within_context_budgets():
    for relative_path, maximum in AUTHORITY_BUDGETS.items():
        assert _word_count(_read(relative_path)) <= maximum, relative_path


def test_closed_audits_and_parity_ledgers_are_archived():
    for relative_path in RETIRED_ACTIVE_HISTORY:
        assert not (ROOT / relative_path).exists()
    assert (
        ROOT
        / "docs/archive/pre-release-debt-cleanup/2026-06-25-pre-release-architecture-debt-audit.md"
    ).is_file()
    assert (ROOT / "docs/archive/t3-gui-parity-shell/2026-07-18-t3-gui-parity-ledger.md").is_file()


def test_pi_blueprint_describes_direction_without_completed_phase_ledger():
    text = _read("docs/platform/agent-platform-blueprint.md")
    assert "## Migration Program" not in text
    assert "Phase A:" not in text
    assert "QueryEngine" not in text


RETIRED_ACTIVE_AUTHORITIES = (
    "docs/development-tracker.md",
    "docs/design-change-log.md",
    "docs/pre-release-architecture-debt-audit.md",
    "docs/guides/t3-gui-parity-ledger.md",
)


def _active_global_docs():
    roots = (ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "docs")
    for root in roots:
        candidates = (root,) if root.is_file() else root.rglob("*.md")
        for path in candidates:
            relative_path = path.relative_to(ROOT).as_posix()
            if relative_path.startswith("docs/archive/"):
                continue
            if relative_path.startswith("docs/superpowers/"):
                continue
            yield path


def test_active_global_docs_do_not_route_to_retired_authorities():
    offenders = []
    for path in _active_global_docs():
        text = path.read_text(encoding="utf-8")
        for token in RETIRED_ACTIVE_AUTHORITIES:
            if token in text:
                offenders.append("%s references %s" % (path.relative_to(ROOT).as_posix(), token))
    assert offenders == []


RETIRED_DOMAIN_PATHS = (
    "docs/agent-harness-v2.md",
    "docs/frontend-protocol.md",
    "docs/mode-schema.md",
    "docs/modules",
    "docs/permission-model.md",
    "docs/pi-inspired-agent-core-blueprint.md",
    "docs/tool-contracts.md",
)


def test_stable_authorities_use_domain_paths_without_compatibility_redirects():
    for relative_path in RETIRED_DOMAIN_PATHS:
        assert not (ROOT / relative_path).exists(), relative_path




def test_stable_authority_filenames_do_not_encode_lifecycle_versions():
    for path in _active_global_docs():
        assert not re.search(r"(?:^|[-_])v[0-9]+(?:[-_.]|$)", path.name, re.IGNORECASE), path
