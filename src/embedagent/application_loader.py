"""Load only the application registrations selected by a compiled plan."""

from __future__ import annotations

import importlib
from typing import Any, Callable, Dict, List, Tuple


def _plan_value(plan: Any, name: str, default: Any = None) -> Any:
    if isinstance(plan, dict):
        return plan.get(name, default)
    return getattr(plan, name, default)


def _registration_entries(plan: Any) -> Tuple[str, ...]:
    entries = _plan_value(plan, "registration_entries", ()) or ()
    return tuple(str(item or "").strip() for item in entries)


def _load_entry(entry: str) -> Callable[[Any], Any]:
    module_name, separator, symbol_name = entry.partition(":")
    if not separator or not module_name or not symbol_name:
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
        if isinstance(exc, ValueError) and str(exc).startswith("application_registration_error:"):
            raise
        raise ValueError("application_registration_error:%s" % entry)

    def dispose() -> None:
        while disposers:
            disposer = disposers.pop()
            disposer()

    return dispose


def bootstrap_generic_shell(plan: Any, registrar: Any):
    """Bootstrap the generic shell from the selected build plan."""
    allowed = tuple(_plan_value(plan, "allowed_agent_application_ids", ()) or ())
    if not allowed:
        raise ValueError("application_registration_error:application_id")
    return load_selected_applications(plan, registrar)


def compile_generic_shell_descriptor(plan: Any, session_capabilities: Dict[str, Any]):
    from embedagent.product_catalog import product_shell_compiler

    allowed = tuple(_plan_value(plan, "allowed_agent_application_ids", ()) or ())
    if len(allowed) != 1:
        raise ValueError("application_registration_error:application_id")
    return product_shell_compiler()(allowed[0], session_capabilities)
