from __future__ import annotations

import os
from typing import Iterable, Optional, Sequence


_BUNDLE_MARKER_RELATIVE_PATHS = (
    os.path.join("app", "embedagent"),
    os.path.join("runtime", "python"),
    "bin",
)


def _normalize_candidate(path: str) -> str:
    if not path:
        return ""
    return os.path.realpath(path)


def is_bundle_root(path: str) -> bool:
    resolved = _normalize_candidate(path)
    if not resolved or not os.path.isdir(resolved):
        return False
    for relative in _BUNDLE_MARKER_RELATIVE_PATHS:
        if not os.path.exists(os.path.join(resolved, relative)):
            return False
    return True


def _append_candidate(candidates: list, seen: set, value: str) -> None:
    resolved = _normalize_candidate(value)
    if not resolved or resolved in seen:
        return
    candidates.append(resolved)
    seen.add(resolved)


def _anchor_candidates(anchor_path: str, anchor_levels: Sequence[int]) -> Iterable[str]:
    anchor = _normalize_candidate(anchor_path)
    if not anchor:
        return []
    current = anchor if os.path.isdir(anchor) else os.path.dirname(anchor)
    candidates = []
    for level in anchor_levels or ():
        try:
            depth = max(int(level), 0)
        except (TypeError, ValueError):
            continue
        candidate = current
        for _ in range(depth):
            candidate = os.path.dirname(candidate)
        candidates.append(candidate)
    return candidates


def discover_bundle_root(
    env_root: str = "",
    anchor_path: str = "",
    anchor_levels: Sequence[int] = (),
    extra_candidates: Sequence[str] = (),
) -> Optional[str]:
    candidates = []
    seen = set()
    _append_candidate(candidates, seen, env_root)
    for candidate in _anchor_candidates(anchor_path, anchor_levels):
        _append_candidate(candidates, seen, candidate)
    for candidate in extra_candidates or ():
        _append_candidate(candidates, seen, candidate)
    for candidate in candidates:
        if is_bundle_root(candidate):
            return candidate
    return None


def running_from_bundle(
    env_root: str = "",
    anchor_path: str = "",
    anchor_levels: Sequence[int] = (),
    extra_candidates: Sequence[str] = (),
) -> bool:
    return bool(
        discover_bundle_root(
            env_root=env_root,
            anchor_path=anchor_path,
            anchor_levels=anchor_levels,
            extra_candidates=extra_candidates,
        )
    )
