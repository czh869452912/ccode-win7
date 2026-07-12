from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple
from xml.sax.saxutils import escape


def prompt_command_specs(resources: Dict[str, Any]) -> List[Any]:
    from embedagent_host.runtime.slash_commands import SlashCommandSpec

    specs = []
    for item in _prompt_records(resources):
        name = str(item.get("name") or "").strip()
        path = str(item.get("path") or "").strip()
        if not name or not path:
            continue
        specs.append(
            SlashCommandSpec(
                "prompt:%s" % name,
                "/prompt:%s [args]" % name,
                "展开本地 prompt：%s" % path,
            )
        )
    return specs


def expand_prompt_invocation(
    text: str,
    resources: Dict[str, Any],
    workspace: str,
) -> Tuple[str, str]:
    prompt_ref, arguments = _parse_prompt_command(text)
    if not prompt_ref:
        return "", "not a prompt invocation"
    prompt, error = _find_prompt(prompt_ref, resources)
    if error:
        return "", error
    path = _resolve_inside(workspace, str(prompt.get("path") or ""))
    if not path:
        return "", "prompt 路径不在工作区内：%s" % str(prompt.get("path") or "")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            body = handle.read().strip()
    except OSError as exc:
        return "", "读取 prompt 失败：%s" % exc
    display_path = str(prompt.get("path") or _display_path(os.path.realpath(workspace), path))
    base_dir = _display_path(os.path.realpath(workspace), os.path.dirname(path))
    name = str(prompt.get("name") or prompt_ref).strip()
    lines = [
        '<prompt name="%s" location="%s">'
        % (_attribute_escape(name), _attribute_escape(display_path)),
        "References are relative to %s." % base_dir,
        "",
        body,
        "</prompt>",
    ]
    if arguments:
        lines.extend(["", arguments])
    return "\n".join(lines).strip(), ""


def _prompt_records(resources: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(resources, dict):
        return []
    records = []
    for item in list(resources.get("prompts") or []):
        if isinstance(item, dict):
            records.append(dict(item))
    return sorted(records, key=lambda item: str(item.get("path") or ""))


def _find_prompt(prompt_ref: str, resources: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    target = _normalize_ref(prompt_ref)
    if not target:
        return {}, "prompt 名称为空"
    matches = []
    for item in _prompt_records(resources):
        name = _normalize_ref(item.get("name"))
        path = _normalize_ref(item.get("path"))
        base = _normalize_ref(os.path.splitext(os.path.basename(str(item.get("path") or "")))[0])
        if target in (name, path, base):
            matches.append(item)
    if not matches:
        return {}, "未找到本地 prompt：%s" % prompt_ref
    if len(matches) > 1:
        paths = ", ".join(str(item.get("path") or "") for item in matches)
        return {}, "prompt 名称不唯一，请使用路径：%s" % paths
    return matches[0], ""


def _parse_prompt_command(text: str) -> Tuple[str, str]:
    raw = str(text or "").strip()
    if not raw.lower().startswith("/prompt:"):
        return "", ""
    remainder = raw[len("/prompt:") :].strip()
    if not remainder:
        return "", ""
    parts = remainder.split(None, 1)
    return parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")


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


def _normalize_ref(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/").strip("/").lower()


def _display_path(workspace: str, path: str) -> str:
    try:
        relative = os.path.relpath(path, workspace)
    except ValueError:
        return os.path.realpath(path)
    return "." if relative == "." else relative.replace(os.sep, "/")


def _attribute_escape(value: str) -> str:
    return escape(str(value or ""), {'"': "&quot;"})
