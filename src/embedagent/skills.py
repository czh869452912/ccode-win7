from __future__ import annotations

import fnmatch
import os
import re
from typing import Any, Dict, List, Tuple
from xml.sax.saxutils import escape

from embedagent.skill_index import build_skill_index

SKILL_EXTENSIONS = (".md", ".txt")
_VALID_SKILL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$")


def parse_skill_document(text: str) -> Tuple[Dict[str, Any], str]:
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, normalized
    closing_index = -1
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            closing_index = index
            break
    if closing_index < 0:
        return {}, normalized
    metadata = _parse_frontmatter_lines(lines[1:closing_index])
    body = "\n".join(lines[closing_index + 1 :])
    return metadata, body


def discover_skill_resources(
    workspace: str,
    roots: List[str],
    diagnostics: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    items = []  # type: List[Dict[str, Any]]
    seen_names = set()
    for path in _iter_skill_files(roots):
        item = _load_skill_resource(workspace, path, diagnostics)
        if not item:
            continue
        name_key = str(item.get("name") or "").lower()
        if name_key in seen_names:
            diagnostics.append(
                {
                    "kind": "skill",
                    "path": item.get("path", ""),
                    "error": "duplicate skill name: %s" % item.get("name", ""),
                }
            )
            continue
        seen_names.add(name_key)
        items.append(item)
    return items


def format_skills_for_prompt(skills: List[Dict[str, Any]]) -> str:
    return build_skill_index({"skills": list(skills or [])}).prompt_text()


def expand_skill_invocation(
    text: str,
    resources: Dict[str, Any],
    workspace: str,
) -> Tuple[str, str]:
    command_name, arguments = _parse_skill_command(text)
    if not command_name:
        return "", "not a skill invocation"
    skill = build_skill_index(resources).record_by_name(command_name)
    if not skill:
        return "", "未找到本地 skill：%s" % command_name
    path = _resolve_inside(workspace, skill.path)
    if not path:
        return "", "skill 路径不在工作区内：%s" % skill.path
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text_body = handle.read()
    except OSError as exc:
        return "", "读取 skill 失败：%s" % exc
    _metadata, body = parse_skill_document(text_body)
    body = body.strip()
    display_path = skill.path or _display_path(os.path.realpath(workspace), path)
    base_dir = skill.base_dir or _display_path(os.path.realpath(workspace), os.path.dirname(path))
    lines = [
        '<skill name="%s" location="%s">'
        % (_attribute_escape(command_name), _attribute_escape(display_path)),
        "References are relative to %s." % base_dir,
        "",
        body,
        "</skill>",
    ]
    if arguments:
        lines.extend(["", arguments])
    return "\n".join(lines).strip(), ""


def _load_skill_resource(
    workspace: str,
    path: str,
    diagnostics: List[Dict[str, Any]],
) -> Dict[str, Any]:
    display_path = _display_path(workspace, path)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        diagnostics.append({"kind": "skill", "path": display_path, "error": str(exc)})
        return {}
    metadata, _body = parse_skill_document(text)
    raw_name = str(metadata.get("name") or "").strip()
    default_name = _default_skill_name(path)
    name = raw_name or default_name
    description = str(metadata.get("description") or "").strip()
    disable_model_invocation = _as_bool(
        metadata.get("disable-model-invocation", metadata.get("disable_model_invocation", False))
    )
    has_frontmatter = bool(metadata)
    valid_name = _is_valid_skill_name(name)
    prompt_visible = bool(
        has_frontmatter and valid_name and description and not disable_model_invocation
    )
    if has_frontmatter and not valid_name:
        diagnostics.append(
            {
                "kind": "skill",
                "path": display_path,
                "error": "invalid skill name: %s" % name,
            }
        )
    return {
        "kind": "skill",
        "path": display_path,
        "name": name,
        "description": description,
        "base_dir": _display_path(workspace, os.path.dirname(path)),
        "disable_model_invocation": disable_model_invocation,
        "prompt_visible": prompt_visible,
        "source": "local_resource",
    }


def _parse_frontmatter_lines(lines: List[str]) -> Dict[str, Any]:
    metadata = {}  # type: Dict[str, Any]
    index = 0
    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or ":" not in raw:
            index += 1
            continue
        key, value = raw.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if not key:
            index += 1
            continue
        if value in ("|", ">"):
            block = []  # type: List[str]
            index += 1
            while index < len(lines):
                block_line = lines[index]
                if block_line.strip() and not (
                    block_line.startswith(" ") or block_line.startswith("\t")
                ):
                    break
                block.append(block_line.strip())
                index += 1
            metadata[key] = "\n".join(block).strip()
            continue
        metadata[key] = _unquote(value)
        index += 1
    return metadata


def _iter_skill_files(roots: List[str]) -> List[str]:
    files = []  # type: List[str]
    for root in roots:
        if os.path.isfile(root):
            if root.lower().endswith(SKILL_EXTENSIONS):
                files.append(os.path.realpath(root))
            continue
        if not os.path.isdir(root):
            continue
        ignore_rules = _load_ignore_rules(root)
        for current_root, dir_names, file_names in os.walk(root):
            dir_names[:] = sorted(
                name
                for name in dir_names
                if name not in (".git", "__pycache__")
                and not _is_ignored(
                    _relative_resource_path(root, os.path.join(current_root, name)),
                    True,
                    ignore_rules,
                )
            )
            skill_md = _find_skill_md(current_root, file_names)
            if skill_md and not _is_ignored(
                _relative_resource_path(root, skill_md),
                False,
                ignore_rules,
            ):
                files.append(skill_md)
                dir_names[:] = []
                continue
            for file_name in sorted(file_names):
                absolute_path = os.path.join(current_root, file_name)
                relative_path = _relative_resource_path(root, absolute_path)
                if _is_ignored(relative_path, False, ignore_rules):
                    continue
                if absolute_path.lower().endswith(SKILL_EXTENSIONS):
                    files.append(os.path.realpath(absolute_path))
    files.sort()
    return files


def _load_ignore_rules(root: str) -> List[Dict[str, Any]]:
    rules = []  # type: List[Dict[str, Any]]
    for file_name in (".gitignore", ".ignore", ".fdignore"):
        path = os.path.join(root, file_name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as handle:
                lines = handle.readlines()
        except OSError:
            continue
        for line in lines:
            pattern = str(line or "").strip()
            if not pattern or pattern.startswith("#"):
                continue
            negated = pattern.startswith("!")
            if negated:
                pattern = pattern[1:].strip()
            if not pattern:
                continue
            directory_only = pattern.endswith("/")
            pattern = pattern.strip("/")
            if not pattern:
                continue
            rules.append(
                {
                    "pattern": pattern.replace("\\", "/"),
                    "negated": negated,
                    "directory_only": directory_only,
                }
            )
    return rules


def _is_ignored(relative_path: str, is_dir: bool, rules: List[Dict[str, Any]]) -> bool:
    normalized = str(relative_path or "").replace("\\", "/").strip("/")
    if not normalized:
        return False
    ignored = False
    for rule in rules:
        if bool(rule.get("directory_only")) and not is_dir:
            continue
        pattern = str(rule.get("pattern") or "")
        if not pattern:
            continue
        if _ignore_rule_matches(normalized, pattern, is_dir):
            ignored = not bool(rule.get("negated"))
    return ignored


def _ignore_rule_matches(relative_path: str, pattern: str, is_dir: bool) -> bool:
    del is_dir
    normalized = str(relative_path or "").replace("\\", "/").strip("/")
    pattern = str(pattern or "").replace("\\", "/").strip("/")
    if not normalized or not pattern:
        return False
    if "/" in pattern:
        return fnmatch.fnmatch(normalized, pattern) or normalized == pattern
    parts = normalized.split("/")
    if any(fnmatch.fnmatch(part, pattern) for part in parts):
        return True
    return fnmatch.fnmatch(normalized, pattern) or normalized == pattern


def _relative_resource_path(root: str, path: str) -> str:
    try:
        relative = os.path.relpath(path, root)
    except ValueError:
        return os.path.realpath(path).replace(os.sep, "/")
    return "." if relative == "." else relative.replace(os.sep, "/")


def _find_skill_md(current_root: str, file_names: List[str]) -> str:
    for file_name in sorted(file_names):
        if file_name.lower() == "skill.md":
            return os.path.realpath(os.path.join(current_root, file_name))
    return ""


def _default_skill_name(path: str) -> str:
    base_name = os.path.basename(path)
    if base_name.lower() == "skill.md":
        base_name = os.path.basename(os.path.dirname(path))
    else:
        base_name = os.path.splitext(base_name)[0]
    slug = re.sub(r"[^a-z0-9]+", "-", str(base_name or "").strip().lower()).strip("-")
    return slug or "skill"


def _is_valid_skill_name(name: str) -> bool:
    text = str(name or "").strip()
    if not text or "--" in text:
        return False
    if len(text) > 64:
        return False
    return bool(_VALID_SKILL_NAME.match(text))


def _as_bool(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text in ("1", "true", "yes", "on")


def _unquote(value: str) -> str:
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        return text[1:-1]
    return text


def _display_path(workspace: str, path: str) -> str:
    try:
        relative = os.path.relpath(path, workspace)
    except ValueError:
        return os.path.realpath(path)
    return "." if relative == "." else relative.replace(os.sep, "/")


def _parse_skill_command(text: str) -> Tuple[str, str]:
    raw = str(text or "").strip()
    if not raw.lower().startswith("/skill:"):
        return "", ""
    remainder = raw[len("/skill:") :].strip()
    if not remainder:
        return "", ""
    parts = remainder.split(None, 1)
    return parts[0].strip().lower(), (parts[1].strip() if len(parts) > 1 else "")


def _resolve_inside(workspace: str, relative_or_absolute: str) -> str:
    root = os.path.realpath(workspace)
    text = str(relative_or_absolute or "").strip()
    if not text:
        return ""
    candidate = text if os.path.isabs(text) else os.path.join(root, text)
    path = os.path.realpath(candidate)
    root_norm = os.path.normcase(root)
    path_norm = os.path.normcase(path)
    if path_norm == root_norm or path_norm.startswith(root_norm + os.sep):
        return path
    return ""


def _attribute_escape(value: str) -> str:
    return escape(str(value or ""), {'"': "&quot;"})
