from __future__ import annotations

import os
from typing import Iterable, Optional, Sequence

_BUNDLE_MARKER_RELATIVE_PATHS = (
    os.path.join("app", "embedagent"),
    os.path.join("runtime", "python"),
    "bin",
)


def _normalize_candidate(path: str) -> str:
    return os.path.realpath(path) if path else ""


def is_bundle_root(path: str) -> bool:
    resolved = _normalize_candidate(path)
    return bool(
        resolved
        and os.path.isdir(resolved)
        and all(
            os.path.exists(os.path.join(resolved, item)) for item in _BUNDLE_MARKER_RELATIVE_PATHS
        )
    )


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
        for _unused in range(depth):
            candidate = os.path.dirname(candidate)
        candidates.append(candidate)
    return candidates


def discover_bundle_root(
    env_root: str = "",
    anchor_path: str = "",
    anchor_levels: Sequence[int] = (),
    extra_candidates: Sequence[str] = (),
) -> Optional[str]:
    candidates = [env_root]
    candidates.extend(_anchor_candidates(anchor_path, anchor_levels))
    candidates.extend(extra_candidates or ())
    seen = set()
    for value in candidates:
        resolved = _normalize_candidate(value)
        if not resolved or resolved in seen:
            continue
        seen.add(resolved)
        if is_bundle_root(resolved):
            return resolved
    return None
