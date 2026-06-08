from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

DEFAULT_EXTENSION_RELPATH = os.path.join(".embedagent", "extensions")
_VALID_EXTENSION_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_ALLOWED_PERMISSIONS = set(["read", "workspace_write", "shell_exec", "toolchain_exec", "git_write"])


def load_project_extensions(
    workspace: str,
    extensions_path: Optional[str] = None,
) -> Dict[str, Any]:
    workspace_root = os.path.realpath(workspace)
    diagnostics = []  # type: List[Dict[str, Any]]
    entries = []  # type: List[Dict[str, Any]]
    loaded_extensions = []  # type: List[Any]
    try:
        root = _resolve_inside(workspace_root, extensions_path or DEFAULT_EXTENSION_RELPATH)
    except ValueError as exc:
        diagnostics.append(
            {
                "extension_id": "",
                "event": "load_project_extensions",
                "error": str(exc),
                "severity": "error",
                "source": "project",
                "metadata": {"path": str(extensions_path or DEFAULT_EXTENSION_RELPATH)},
            }
        )
        return _payload(workspace_root, entries, diagnostics, loaded_extensions)
    if not os.path.isdir(root):
        return _payload(workspace_root, entries, diagnostics, loaded_extensions)
    for extension_dir in _iter_extension_dirs(root):
        entry = _load_manifest_entry(workspace_root, extension_dir, diagnostics)
        entries.append(entry)
    return _payload(workspace_root, entries, diagnostics, loaded_extensions)


def _iter_extension_dirs(root: str) -> List[str]:
    items = []  # type: List[str]
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return items
    for name in names:
        path = os.path.realpath(os.path.join(root, name))
        if os.path.isdir(path):
            items.append(path)
    return items


def _load_manifest_entry(
    workspace: str,
    extension_dir: str,
    diagnostics: List[Dict[str, Any]],
) -> Dict[str, Any]:
    manifest_path = os.path.join(extension_dir, "extension.json")
    base_entry = {
        "id": os.path.basename(extension_dir),
        "status": "failed",
        "manifest_path": _display_path(workspace, manifest_path),
        "entrypoint": "",
        "permissions": [],
    }
    try:
        with open(manifest_path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError) as exc:
        return _failed_entry(base_entry, diagnostics, "manifest", str(exc))
    if not isinstance(manifest, dict):
        return _failed_entry(base_entry, diagnostics, "manifest", "extension manifest must be an object")
    error = _validate_manifest(manifest)
    extension_id = str(manifest.get("id") or base_entry["id"]).strip()
    base_entry["id"] = extension_id
    base_entry["permissions"] = list(manifest.get("permissions") or [])
    entrypoint = str(manifest.get("entrypoint") or "extension.py").strip()
    try:
        entrypoint_path = _resolve_inside(extension_dir, entrypoint)
        base_entry["entrypoint"] = _display_path(workspace, entrypoint_path)
    except ValueError as exc:
        return _failed_entry(base_entry, diagnostics, extension_id, str(exc))
    if error:
        return _failed_entry(base_entry, diagnostics, extension_id, error)
    if not bool(manifest.get("enabled", False)):
        base_entry["status"] = "disabled"
        return base_entry
    return _failed_entry(base_entry, diagnostics, extension_id, "extension loading not implemented")


def _validate_manifest(manifest: Dict[str, Any]) -> str:
    extension_id = str(manifest.get("id") or "").strip()
    if not extension_id:
        return "extension manifest requires id"
    if not _VALID_EXTENSION_ID_RE.match(extension_id):
        return "invalid extension id: %s" % extension_id
    enabled = bool(manifest.get("enabled", False))
    permissions = manifest.get("permissions")
    if enabled and not isinstance(permissions, list):
        return "enabled extension manifest requires permissions"
    for permission in list(permissions or []):
        text = str(permission or "").strip()
        if text not in _ALLOWED_PERMISSIONS:
            return "unsupported extension permission: %s" % (text or "<empty>")
    return ""


def _failed_entry(
    entry: Dict[str, Any],
    diagnostics: List[Dict[str, Any]],
    extension_id: str,
    error: str,
) -> Dict[str, Any]:
    item = dict(entry)
    item["status"] = "failed"
    diagnostics.append(
        {
            "extension_id": str(extension_id or item.get("id") or ""),
            "event": "load_project_extension",
            "error": str(error or ""),
            "severity": "error",
            "source": "project",
            "metadata": {
                "manifest_path": str(item.get("manifest_path") or ""),
                "entrypoint": str(item.get("entrypoint") or ""),
            },
        }
    )
    return item


def _resolve_inside(root: str, path: str) -> str:
    base = os.path.realpath(root)
    candidate = path if os.path.isabs(path) else os.path.join(base, path)
    resolved = os.path.realpath(candidate)
    base_norm = os.path.normcase(base)
    resolved_norm = os.path.normcase(resolved)
    if resolved_norm == base_norm or resolved_norm.startswith(base_norm + os.sep):
        return resolved
    raise ValueError("path is outside extension root: %s" % path)


def _display_path(workspace: str, path: str) -> str:
    try:
        relative = os.path.relpath(path, workspace)
    except ValueError:
        return os.path.realpath(path)
    return "." if relative == "." else relative.replace(os.sep, "/")


def _payload(
    workspace: str,
    entries: List[Dict[str, Any]],
    diagnostics: List[Dict[str, Any]],
    loaded_extensions: List[Any],
) -> Dict[str, Any]:
    counts = {
        "discovered": len(entries),
        "loaded": len([item for item in entries if item.get("status") == "loaded"]),
        "disabled": len([item for item in entries if item.get("status") == "disabled"]),
        "failed": len([item for item in entries if item.get("status") == "failed"]),
        "diagnostics": len(diagnostics),
    }
    return {
        "workspace": os.path.realpath(workspace),
        "counts": counts,
        "extensions": list(entries),
        "diagnostics": list(diagnostics),
        "loaded_extensions": list(loaded_extensions),
    }
