from __future__ import annotations

import os
from typing import Dict, List, Set

from embedagent.constants import SKIP_DIR_NAMES
from embedagent.workspace_recipes import list_workspace_recipes

_DOC_DIR_NAMES = {
    "doc",
    "docs",
    "documentation",
    "wiki",
    "adr",
    "adrs",
    "plans",
    "design",
}
_TEST_DIR_NAMES = {
    "test",
    "tests",
    "testing",
    "unittest",
    "integration",
    "e2e",
    "spec",
    "specs",
}
_CODE_EXTENSIONS = {
    ".py",
    ".pyi",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
}
_TEST_FILE_HINTS = ("test_", "_test", "_spec", "spec_")
_INTERNAL_DIR_NAMES = {".embedagent", ".venv", "build"}


def profile_workspace(
    workspace: str,
    max_depth: int = 3,
    max_entries: int = 400,
    detectors: object = None,
) -> Dict[str, object]:
    workspace = os.path.realpath(workspace)
    doc_roots = set()  # type: Set[str]
    code_roots = set()  # type: Set[str]
    test_roots = set()  # type: Set[str]
    root_entries = []  # type: List[str]
    scanned = 0
    visible_count = 0

    try:
        root_names = sorted(os.listdir(workspace), key=lambda item: item.lower())
    except OSError:
        root_names = []

    for name in root_names:
        if name in SKIP_DIR_NAMES:
            continue
        visible_count += 1
        label = name + ("/" if os.path.isdir(os.path.join(workspace, name)) else "")
        root_entries.append(label)
        if len(root_entries) >= 12:
            break

    queue = [(".", workspace, 0)]  # type: List[Tuple[str, str, int]]
    while queue and scanned < max_entries:
        relative_root, absolute_root, depth = queue.pop(0)
        try:
            names = sorted(os.listdir(absolute_root), key=lambda item: item.lower())
        except OSError:
            continue
        lowered_root_name = os.path.basename(absolute_root).lower()
        if lowered_root_name in _DOC_DIR_NAMES and relative_root != ".":
            doc_roots.add(relative_root.replace("\\", "/"))
        if lowered_root_name in _TEST_DIR_NAMES and relative_root != ".":
            test_roots.add(relative_root.replace("\\", "/"))
        local_has_code = False
        local_has_tests = False
        for name in names:
            if scanned >= max_entries:
                break
            candidate = os.path.join(absolute_root, name)
            if os.path.isdir(candidate):
                if name in SKIP_DIR_NAMES or name in _INTERNAL_DIR_NAMES:
                    continue
                if depth < max_depth:
                    child_relative = (
                        name if relative_root == "." else os.path.join(relative_root, name)
                    )
                    queue.append((child_relative, candidate, depth + 1))
                continue
            scanned += 1
            ext = os.path.splitext(name)[1].lower()
            lower_name = name.lower()
            if ext in _CODE_EXTENSIONS:
                local_has_code = True
            if (
                lower_name.endswith((".json", ".yaml", ".yml"))
                and lowered_root_name in _TEST_DIR_NAMES
            ):
                local_has_tests = True
            if ext in _CODE_EXTENSIONS and any(hint in lower_name for hint in _TEST_FILE_HINTS):
                local_has_tests = True
            detector_signals = _detector_file_signals(
                detectors,
                name=name,
                absolute_path=candidate,
                relative_root=relative_root,
                root_name=lowered_root_name,
            )
            if detector_signals.get("code"):
                local_has_code = True
            if detector_signals.get("tests"):
                local_has_tests = True
        if local_has_code:
            code_roots.add(relative_root.replace("\\", "/"))
        if local_has_tests:
            test_roots.add(relative_root.replace("\\", "/"))

    return {
        "workspace_empty": visible_count == 0,
        "doc_roots": _sorted_unique(doc_roots),
        "code_roots": _sorted_unique(code_roots),
        "test_roots": _sorted_unique(test_roots),
        "root_entries": root_entries,
    }


def _pending_tasks_hint(workspace: str, session_id: str = "") -> str:
    """Task hints are no longer sourced from sidecar task snapshots."""
    del workspace, session_id
    return ""


def build_workspace_profile_message(
    workspace: str,
    session_id: str = "",
    char_limit: int = 900,
    detectors: object = None,
) -> str:
    profile = profile_workspace(workspace, detectors=detectors)
    recipe_payload = list_workspace_recipes(workspace)
    recipe_items = recipe_payload.get("items") if isinstance(recipe_payload, dict) else []
    if profile.get("workspace_empty"):
        empty_msg = (
            "工作区画像：当前工作区基本为空。"
            "spec 模式如需起草文档，可默认创建 docs/ 作为首个文档目录；"
            "build/debug 模式不要假设 src/ 已存在，应根据用户路径或当前目标决定结构。"
        )
        return empty_msg + _pending_tasks_hint(workspace, session_id=session_id)
    lines = ["工作区画像：请优先复用现有工程结构，不要强行套模板。"]
    doc_roots = profile.get("doc_roots") or []
    code_roots = profile.get("code_roots") or []
    test_roots = profile.get("test_roots") or []
    if doc_roots:
        lines.append("已探测文档目录：%s" % ", ".join(doc_roots[:6]))
    else:
        lines.append("尚未探测到明显文档目录；spec 模式如需新建文档，可默认创建 docs/。")
    if code_roots:
        lines.append("已探测代码/工程目录：%s" % ", ".join(code_roots[:8]))
    if test_roots:
        lines.append("已探测测试目录：%s" % ", ".join(test_roots[:6]))
    root_entries = profile.get("root_entries") or []
    if root_entries:
        lines.append("根目录样本：%s" % ", ".join(root_entries[:10]))
    if recipe_items:
        samples = []
        for item in recipe_items[:4]:
            if not isinstance(item, dict):
                continue
            samples.append("%s[%s]" % (str(item.get("id") or ""), str(item.get("tool_name") or "")))
        if samples:
            lines.append("已探测 recipe：%s" % ", ".join(samples))
    message = "\n".join(lines)
    message += _pending_tasks_hint(workspace, session_id=session_id)
    if len(message) <= char_limit:
        return message
    return message[:char_limit] + "\n...[truncated]"


def _sorted_unique(values: Set[str]) -> List[str]:
    normalized = []
    for item in values:
        value = item or "."
        if value == ".":
            continue
        normalized.append(value.replace("\\", "/"))
    normalized.sort(key=lambda item: (item.count("/"), item.lower()))
    return normalized


def _detector_file_signals(
    detectors: object,
    name: str,
    absolute_path: str,
    relative_root: str,
    root_name: str,
) -> Dict[str, bool]:
    aggregate = {"code": False, "tests": False}
    try:
        detector_items = list(detectors or ())
    except TypeError:
        detector_items = []
    for detector in detector_items:
        detect_file = getattr(detector, "detect_file", None)
        try:
            if callable(detect_file):
                signals = detect_file(
                    name=name,
                    absolute_path=absolute_path,
                    relative_root=relative_root.replace("\\", "/"),
                    root_name=root_name,
                )
            elif callable(detector):
                signals = detector(
                    name=name,
                    absolute_path=absolute_path,
                    relative_root=relative_root.replace("\\", "/"),
                    root_name=root_name,
                )
            else:
                signals = {}
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            signals = {}
        if not isinstance(signals, dict):
            continue
        if signals.get("code"):
            aggregate["code"] = True
        if signals.get("tests"):
            aggregate["tests"] = True
    return aggregate
