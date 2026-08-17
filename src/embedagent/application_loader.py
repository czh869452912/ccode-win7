"""Load only the application registrations selected by a compiled plan."""

from __future__ import annotations

import importlib
import re
from typing import Any, Callable, Dict, List, Tuple

_ENTRY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$")


def _plan_value(plan: Any, name: str, default: Any = None) -> Any:
    if isinstance(plan, dict):
        return plan.get(name, default)
    return getattr(plan, name, default)


def _registration_entries(plan: Any) -> Tuple[str, ...]:
    entries = _plan_value(plan, "registration_entries", ()) or ()
    return tuple(str(item or "").strip() for item in entries)


def _load_entry(entry: str) -> Callable[[Any], Any]:
    module_name, separator, symbol_name = entry.partition(":")
    if not separator or not module_name or not symbol_name or _ENTRY_RE.fullmatch(entry) is None:
        raise ValueError("application_registration_error:%s" % entry)
    try:
        module = importlib.import_module(module_name)
        callback = getattr(module, symbol_name)
    except (ImportError, AttributeError):
        raise ValueError("application_registration_error:%s" % entry)
    if not callable(callback):
        raise ValueError("application_registration_error:%s" % entry)
    return callback


def load_selected_applications(plan: Any, registrar: Any):
    """Import and register exactly the plan's application entry points."""
    if registrar is None:
        raise ValueError("application_registration_error:registrar")
    entries = _registration_entries(plan)
    if len(set(entries)) != len(entries) or any(not entry for entry in entries):
        raise ValueError("application_registration_error:duplicate_or_empty_entry")
    disposers: List[Callable[[], Any]] = []
    try:
        for entry in entries:
            callback = _load_entry(entry)
            result = callback(registrar)
            if callable(result):
                disposers.append(result)
    except (
        AttributeError,
        ImportError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        for disposer in reversed(disposers):
            disposer()
        registrar_dispose = getattr(registrar, "dispose", None)
        if callable(registrar_dispose):
            registrar_dispose()
        if isinstance(exc, ValueError) and str(exc).startswith("application_registration_error:"):
            raise
        raise ValueError("application_registration_error:%s" % entry)

    def dispose() -> None:
        while disposers:
            disposer = disposers.pop()
            disposer()
        registrar_dispose = getattr(registrar, "dispose", None)
        if callable(registrar_dispose):
            registrar_dispose()

    return dispose


def bootstrap_generic_shell(plan: Any, registrar: Any):
    """Bootstrap the generic shell from the selected build plan."""
    allowed = tuple(_plan_value(plan, "allowed_agent_application_ids", ()) or ())
    if not allowed:
        raise ValueError("application_registration_error:application_id")
    return load_selected_applications(plan, registrar)


def compile_generic_shell_descriptor(plan: Any, session_capabilities: Dict[str, Any]):
    from embedagent_core import ApplicationRegistrar

    from embedagent.product_catalog import product_shell_registry

    allowed = tuple(_plan_value(plan, "allowed_agent_application_ids", ()) or ())
    if len(allowed) != 1:
        raise ValueError("application_registration_error:application_id")

    class _ShellOnlyExtensionHost(object):
        def register(self, extension, source_id):
            del extension, source_id
            return lambda: None

        def register_prompt_provider(self, provider, source_id):
            del provider, source_id
            return lambda: None

        def register_context_provider(self, provider, source_id):
            del provider, source_id
            return lambda: None

    registry = product_shell_registry()
    registrar = ApplicationRegistrar(_ShellOnlyExtensionHost(), registry)
    dispose = load_selected_applications(plan, registrar)
    try:
        capabilities = dict(session_capabilities or {})
        active_sources = list(capabilities.get("application_sources", ()) or ())
        entries = _registration_entries(plan)
        if (
            "embedagent_workflow_cpp.application:register_application" in entries
            and "embedagent.workflow.cpp" not in active_sources
        ):
            active_sources.append("embedagent.workflow.cpp")
        capabilities["application_sources"] = active_sources
        return registry.compile(allowed[0], capabilities)
    finally:
        dispose()
