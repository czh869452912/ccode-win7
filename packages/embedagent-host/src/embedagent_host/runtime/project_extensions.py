import importlib.util
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

from embedagent_core.permissions import OFFICIAL_PERMISSION_CATEGORIES

DEFAULT_EXTENSION_RELPATH = os.path.join(".embedagent", "extensions")
_VALID_EXTENSION_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_ALLOWED_PERMISSIONS = OFFICIAL_PERMISSION_CATEGORIES
_LOAD_FAILURE_TYPES = (
    OSError,
    ValueError,
    RuntimeError,
    TypeError,
    ImportError,
    SyntaxError,
    AttributeError,
    NameError,
)


class ProjectExtensionApi(object):
    def __init__(self, workspace: str, extension_id: str, manifest: Dict[str, Any]) -> None:
        from embedagent_core.extensions import (
            ContextPatch,
            ExtensionCapability,
            PromptPatch,
            ResourcesDiscoverResult,
            ToolCallDecision,
            ToolRegistrationResult,
            ToolResultPatch,
            WorkflowPatch,
        )
        from embedagent_core.session import Observation

        from embedagent_host.runtime.tools import ToolDefinition

        self.workspace = os.path.realpath(workspace)
        self.extension_id = str(extension_id or "")
        self.manifest = dict(manifest)
        self.permissions = list(manifest.get("permissions") or [])
        self.ContextPatch = ContextPatch
        self.ExtensionCapability = ExtensionCapability
        self.Observation = Observation
        self.PromptPatch = PromptPatch
        self.ResourcesDiscoverResult = ResourcesDiscoverResult
        self.ToolCallDecision = ToolCallDecision
        self.ToolDefinition = ToolDefinition
        self.ToolRegistrationResult = ToolRegistrationResult
        self.ToolResultPatch = ToolResultPatch
        self.WorkflowPatch = WorkflowPatch

    def safe_join(self, *parts: str) -> str:
        path = os.path.join(*[str(part or "") for part in parts]) if parts else "."
        return _resolve_inside(self.workspace, path)

    def read_text(self, relative_path: str, max_chars: int = 40000) -> str:
        limit = int(max_chars)
        if limit < 0:
            raise ValueError("max_chars must be non-negative")
        path = self.safe_join(relative_path)
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read(limit)


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
        entry = _load_manifest_entry(
            workspace_root,
            extension_dir,
            diagnostics,
            loaded_extensions,
        )
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
    loaded_extensions: List[Any],
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
        return _failed_entry(
            base_entry, diagnostics, "manifest", "extension manifest must be an object"
        )
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
    try:
        extension = _load_enabled_extension(
            workspace,
            extension_id,
            manifest,
            entrypoint_path,
        )
    except _LOAD_FAILURE_TYPES as exc:
        return _failed_entry(base_entry, diagnostics, extension_id, str(exc))
    loaded_extensions.append(extension)
    base_entry["status"] = "loaded"
    return base_entry


def _load_enabled_extension(
    workspace: str,
    extension_id: str,
    manifest: Dict[str, Any],
    entrypoint_path: str,
) -> Any:
    if not os.path.isfile(entrypoint_path):
        raise OSError("extension entrypoint does not exist: %s" % entrypoint_path)
    module_name = _module_name(extension_id, entrypoint_path)
    spec = importlib.util.spec_from_file_location(module_name, entrypoint_path)
    if spec is None or spec.loader is None:
        raise ImportError("could not create module spec for extension entrypoint")
    module = importlib.util.module_from_spec(spec)
    previous_module = sys.modules.get(module_name)
    sys.modules[module_name] = module
    loaded = False
    try:
        spec.loader.exec_module(module)
        loaded = True
    finally:
        if not loaded:
            if previous_module is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = previous_module
    extension = None
    factory = getattr(module, "create_extension", None)
    if callable(factory):
        api = ProjectExtensionApi(workspace, extension_id, manifest)
        extension = factory(api)
    else:
        extension = getattr(module, "EXTENSION", None)
    if extension is None:
        raise RuntimeError("extension entrypoint must define create_extension(api) or EXTENSION")
    _mark_project_extension(extension, extension_id)
    return extension


def _module_name(extension_id: str, entrypoint_path: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_]", "_", str(extension_id or "project_extension"))
    return "_embedagent_project_extension_%s_%s" % (token, abs(hash(entrypoint_path)))


def _mark_project_extension(extension: Any, extension_id: str) -> None:
    if not str(getattr(extension, "extension_id", "") or "").strip():
        setattr(extension, "extension_id", extension_id)
    setattr(extension, "builtin_extension", False)
    setattr(extension, "project_extension", True)


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
