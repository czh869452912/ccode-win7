from __future__ import annotations

import os
from typing import Dict, List, Set, Tuple

from embedagent.tools._base import SKIP_DIR_NAMES


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
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hh",
    ".hpp",
    ".hxx",
    ".py",
    ".pyi",
    ".js",
    ".ts",
    ".tsx",
}
_TEST_FILE_HINTS = ("test_", "_test", "_spec", "spec_")
_BUILD_FILE_NAMES = {"CMakeLists.txt", "Makefile", "makefile", "meson.build"}
_INTERNAL_DIR_NAMES = {".embedagent", ".venv", "build"}


def profile_workspace(workspace: str, max_depth: int = 3, max_entries: int = 400) -> Dict[str, object]:
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
                    child_relative = name if relative_root == "." else os.path.join(relative_root, name)
                    queue.append((child_relative, candidate, depth + 1))
                continue
            scanned += 1
            ext = os.path.splitext(name)[1].lower()
            lower_name = name.lower()
            if name in _BUILD_FILE_NAMES or ext in _CODE_EXTENSIONS:
                local_has_code = True
            if lower_name.endswith((".json", ".yaml", ".yml")) and lowered_root_name in _TEST_DIR_NAMES:
                local_has_tests = True
            if ext in _CODE_EXTENSIONS and any(hint in lower_name for hint in _TEST_FILE_HINTS):
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


def build_workspace_profile_message(workspace: str, char_limit: int = 900) -> str:
    profile = profile_workspace(workspace)
    if profile.get("workspace_empty"):
        return (
            "工作区画像：当前工作区基本为空。"
            "spec 模式如需起草文档，可默认创建 docs/ 作为首个文档目录；"
            "code/test/debug 模式不要假设 src/ 或 tests/ 已存在，应根据用户路径或当前目标决定结构。"
        )
    lines = ["工作区画像：请优先复用现有工程结构，不要强行套模板。"]
    doc_roots = profile.get("doc_roots") or []
    code_roots = profile.get("code_roots") or []
    test_roots = profile.get("test_roots") or []
    if doc_roots:
        lines.append("已探测文档目录：%s" % ", ".join(doc_roots[:6]))
    else:
        lines.append("尚未探测到明显文档目录；spec 模式如需新建文档，可默认创建 docs/。")
    if code_roots:
        lines.append("已探测代码/构建目录：%s" % ", ".join(code_roots[:8]))
    if test_roots:
        lines.append("已探测测试目录：%s" % ", ".join(test_roots[:6]))
    root_entries = profile.get("root_entries") or []
    if root_entries:
        lines.append("根目录样本：%s" % ", ".join(root_entries[:10]))
    message = "\n".join(lines)
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
