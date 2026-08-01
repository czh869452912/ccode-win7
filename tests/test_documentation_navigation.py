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
    return set(
        re.findall(r"`(docs/superpowers/(?:specs|plans)/[^`]+[.]md)`", text)
    )


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
