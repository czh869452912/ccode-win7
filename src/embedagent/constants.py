"""Shared constants used across embedagent packages."""

from __future__ import annotations

SKIP_DIR_NAMES = frozenset({".git", ".hg", ".svn", "__pycache__"})
SKIP_RELATIVE_DIRS = frozenset({".embedagent/memory"})
TEXT_ENCODINGS = ("utf-8", "utf-8-sig", "gbk", "cp936")


def normalize_relative_path(path: str) -> str:
    return str(path or "").replace("\\", "/").strip("/")


def should_skip_directory(name: str, relative_path: str = "") -> bool:
    if name in SKIP_DIR_NAMES:
        return True
    normalized = normalize_relative_path(relative_path)
    return normalized in SKIP_RELATIVE_DIRS
