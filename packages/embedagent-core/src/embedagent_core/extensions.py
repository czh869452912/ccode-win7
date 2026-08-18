from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from embedagent_core.agent_event_bus import AgentEvent, AgentEventBus, AgentEventDispatchError
from embedagent_core.registration_scope import RegistrationScope

_HOOK_EVENT_TYPES = {
    "context": "extension.context",
    "resources_discover": "extension.resources_discover",
    "register_tools": "extension.register_tools",
    "tool_call": "extension.tool_call",
    "tool_result": "extension.tool_result",
    "before_agent_start": "extension.before_agent_start",
    "should_inject_workflow": "extension.should_inject_workflow",
    "describe_prompt": "extension.describe_prompt",
    "initialize_workflow_state": "extension.initialize_workflow_state",
    "allowed_tool_names": "extension.allowed_tool_names",
    "load_session_tasks": "extension.load_session_tasks",
    "handle_tool_call": "extension.handle_tool_call",
    "package_manifest": "extension.package_manifest",
    "register_context_reducers": "extension.register_context_reducers",
    "workspace_recipes": "extension.workspace_recipes",
}


@dataclass
class SessionView:
    session_id: str = ""
    workflow_state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_session(cls, session: Any) -> "SessionView":
        return cls(
            session_id=str(getattr(session, "session_id", "") or ""),
            workflow_state=dict(getattr(session, "workflow_state", {}) or {}),
        )


@dataclass
class WorkflowEvent:
    session_id: str = ""
    turn_id: str = ""
    step_id: str = ""
    current_mode: str = ""
    workflow_state: Dict[str, Any] = field(default_factory=dict)
    workflow_state_name: str = ""
    user_text: str = ""
    tool_name: str = ""
    tool_arguments: Dict[str, Any] = field(default_factory=dict)
    observation: Any = None
    messages: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtensionContext:
    workspace: str = ""
    runtime_environment: Dict[str, Any] = field(default_factory=dict)
    tool_registry: Any = None
    permission_policy: Any = None
    session_view: Optional[SessionView] = None


@dataclass
class ExtensionCapability:
    """Explicit internal capability registration for in-process extensions."""

    hook_name: str
    handler: Any
    event_type: str = ""
    kind: str = "reducer"
    fail_closed: Optional[bool] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        hook_name = str(self.hook_name or "").strip()
        event_type = str(self.event_type or "").strip()
        if not event_type and hook_name in _HOOK_EVENT_TYPES:
            event_type = _HOOK_EVENT_TYPES[hook_name]
        if not hook_name and event_type.startswith("extension."):
            hook_name = event_type.split(".", 1)[1]
        self.hook_name = hook_name
        self.event_type = event_type
        self.kind = str(self.kind or "reducer")
        self.metadata = dict(self.metadata or {})


@dataclass
class PromptPatch:
    prompt_units: List[str] = field(default_factory=list)
    system_prompt_append: str = ""
    active_tool_names: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowPrompt:
    mode_name: str = ""
    discipline_label: str = ""
    pack_name: str = ""
    prompt_units: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextPatch:
    messages: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallDecision:
    block: bool = False
    reason: str = ""
    updated_arguments: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResultPatch:
    observation: Any = None
    workflow_patch: Optional["WorkflowPatch"] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowPatch:
    workflow: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtensionDiagnostic:
    extension_id: str = ""
    event: str = ""
    error: str = ""
    severity: str = "error"
    source: str = "extension"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "extension_id": self.extension_id,
            "event": self.event,
            "error": self.error,
            "severity": self.severity,
            "source": self.source,
            "metadata": dict(self.metadata),
        }


@dataclass
class ResourcesDiscoverEvent:
    cwd: str = ""
    reason: str = "startup"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourcesDiscoverResult:
    skill_paths: List[str] = field(default_factory=list)
    prompt_paths: List[str] = field(default_factory=list)
    recipe_paths: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolRegistrationEvent:
    current_mode: str = ""
    workflow_state_name: str = ""
    reason: str = "startup"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolRegistrationResult:
    tools: List[Any] = field(default_factory=list)
    source_id: str = ""
    source_type: str = "extension"
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExtensionManager(object):
    def __init__(self, extensions: Optional[List[Any]] = None) -> None:
        self._extensions = []  # type: List[Any]
        self._diagnostics = []  # type: List[ExtensionDiagnostic]
        self._event_bus = AgentEventBus()
        self._scope = RegistrationScope("extensions")
        self._package_manifest_capabilities = []  # type: List[Dict[str, Any]]
        self._context_reducer_capabilities = []  # type: List[Dict[str, Any]]
        self._context_reducer_registration_lock = threading.RLock()
        self._context_reducer_registrations = []  # type: List[Any]
        self._workspace_recipe_capabilities = []  # type: List[Dict[str, Any]]
        for extension in list(extensions or []):
            self.register(extension)

    def register(self, extension: Any) -> Callable[[], None]:
        source_id = self._extension_id(extension)
        extension_scope = self._scope.create_child("extension:%s:%s" % (source_id, id(extension)))
        self._extensions.append(extension)
        try:
            self._register_capabilities(extension, extension_scope)
        except BaseException:
            try:
                extension_scope.dispose()
            finally:
                self._remove_extension(extension)
            raise

        def remove_extension() -> None:
            try:
                extension_scope.dispose()
            finally:
                self._remove_extension(extension)

        return self._scope.register(remove_extension)

    def dispose(self) -> None:
        self._scope.dispose()

    def diagnostics(self) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in self._diagnostics]

    def clear_diagnostics(self) -> None:
        self._diagnostics = []

    def record_diagnostic(
        self,
        extension_id: str,
        event: str,
        error: str,
        severity: str = "error",
        source: str = "project",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._diagnostics.append(
            ExtensionDiagnostic(
                extension_id=str(extension_id or ""),
                event=str(event or ""),
                error=str(error or ""),
                severity=str(severity or "error"),
                source=str(source or "project"),
                metadata=dict(metadata or {}),
            )
        )

    def package_manifests(self) -> List[Dict[str, Any]]:
        manifests = []
        for entry in list(self._package_manifest_capabilities):
            handler = entry["handler"]
            extension_id = str(entry["source_id"] or "")
            source = str(entry["source_type"] or "project")
            try:
                payload = handler()
            except (RuntimeError, ValueError, TypeError, OSError) as exc:
                self.record_diagnostic(
                    extension_id,
                    "package_manifest",
                    str(exc),
                    severity="error",
                    source=source,
                )
                if bool(entry.get("fail_closed")):
                    raise
                continue
            if isinstance(payload, dict):
                manifests.append(dict(payload))
        return manifests

    def workspace_recipes(self) -> Dict[str, Any]:
        merged = {"workspace": "", "items": [], "resources": {}}  # type: Dict[str, Any]
        seen = set()
        for entry in list(self._workspace_recipe_capabilities):
            handler = entry["handler"]
            extension_id = str(entry["source_id"] or "")
            source = str(entry["source_type"] or "project")
            try:
                payload = handler()
            except (RuntimeError, ValueError, TypeError, OSError) as exc:
                self.record_diagnostic(
                    extension_id,
                    "workspace_recipes",
                    str(exc),
                    severity="error",
                    source=source,
                )
                if bool(entry.get("fail_closed")):
                    raise
                continue
            if not isinstance(payload, dict):
                continue
            if not merged["workspace"]:
                merged["workspace"] = str(payload.get("workspace") or "")
            if not merged["resources"] and isinstance(payload.get("resources"), dict):
                merged["resources"] = dict(payload.get("resources") or {})
            for item in list(payload.get("items") or []):
                if not isinstance(item, dict):
                    continue
                key = str(item.get("id") or "") or repr(sorted(item.items()))
                if key in seen:
                    continue
                seen.add(key)
                merged["items"].append(dict(item))
        return merged

    def _extension_id(self, extension: Any) -> str:
        explicit = str(getattr(extension, "extension_id", "") or "").strip()
        if explicit:
            return explicit
        name = getattr(extension.__class__, "__name__", "")
        return str(name or "extension")

    def _is_builtin_extension(self, extension: Any) -> bool:
        return bool(getattr(extension, "builtin_extension", True))

    def _register_capabilities(
        self,
        extension: Any,
        scope: RegistrationScope,
    ) -> None:
        source_id = self._extension_id(extension)
        source_type = "builtin" if self._is_builtin_extension(extension) else "project"
        fail_closed = self._is_builtin_extension(extension)
        provider = getattr(extension, "extension_capabilities", None)
        if not callable(provider):
            return
        try:
            capabilities = list(provider() or [])
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            self.record_diagnostic(
                source_id,
                "extension_capabilities",
                str(exc),
                severity="error",
                source=source_type,
            )
            if fail_closed:
                raise
            return
        for raw_capability in capabilities:
            capability = self._normalize_capability(
                raw_capability,
                source_id,
                source_type,
                fail_closed,
            )
            if capability is None:
                continue
            disposer = self._register_capability(
                capability,
                source_id,
                source_type,
                fail_closed,
            )
            if callable(disposer):
                scope.register(disposer)

    def _normalize_capability(
        self,
        value: Any,
        source_id: str,
        source_type: str,
        fail_closed: bool,
    ) -> Optional[ExtensionCapability]:
        if isinstance(value, ExtensionCapability):
            return value
        if isinstance(value, dict):
            try:
                return ExtensionCapability(**dict(value))
            except TypeError as exc:
                self.record_diagnostic(
                    source_id,
                    "extension_capabilities",
                    "invalid capability record: %s" % exc,
                    severity="error",
                    source=source_type,
                )
                if fail_closed:
                    raise
                return None
        self.record_diagnostic(
            source_id,
            "extension_capabilities",
            "invalid capability record: %s" % value.__class__.__name__,
            severity="error",
            source=source_type,
        )
        if fail_closed:
            raise TypeError("invalid capability record: %s" % value.__class__.__name__)
        return None

    def _register_capability(
        self,
        capability: ExtensionCapability,
        source_id: str,
        source_type: str,
        default_fail_closed: bool,
    ) -> Optional[Callable[[], None]]:
        if not callable(capability.handler):
            self.record_diagnostic(
                source_id,
                "extension_capabilities",
                "capability handler is not callable: %s" % capability.hook_name,
                severity="error",
                source=source_type,
            )
            if default_fail_closed:
                raise TypeError("capability handler is not callable: %s" % capability.hook_name)
            return
        fail_closed = (
            bool(capability.fail_closed)
            if capability.fail_closed is not None
            else bool(default_fail_closed)
        )
        entry = {
            "source_id": source_id,
            "source_type": source_type,
            "handler": capability.handler,
            "hook_name": capability.hook_name,
            "event_type": capability.event_type,
            "fail_closed": fail_closed,
            "metadata": dict(capability.metadata or {}),
        }
        if capability.hook_name == "package_manifest":
            self._package_manifest_capabilities.append(entry)
            return lambda: self._remove_entry(self._package_manifest_capabilities, entry)
        if capability.hook_name == "register_context_reducers":
            self._context_reducer_capabilities.append(entry)
            return lambda: self._remove_entry(self._context_reducer_capabilities, entry)
        if capability.hook_name == "workspace_recipes":
            self._workspace_recipe_capabilities.append(entry)
            return lambda: self._remove_entry(self._workspace_recipe_capabilities, entry)
        event_type = str(capability.event_type or "")
        if not event_type:
            self.record_diagnostic(
                source_id,
                "extension_capabilities",
                "capability event_type is empty: %s" % capability.hook_name,
                severity="error",
                source=source_type,
            )
            if fail_closed:
                raise ValueError("capability event_type is empty: %s" % capability.hook_name)
            return
        metadata = {"hook_name": capability.hook_name}
        metadata.update(dict(capability.metadata or {}))
        handler = self._event_handler_for_capability(capability)
        if capability.kind == "observer":
            return self._event_bus.register_observer(
                event_type,
                source_id,
                source_type,
                handler,
                fail_closed=fail_closed,
                metadata=metadata,
            )
        else:
            return self._event_bus.register_reducer(
                event_type,
                source_id,
                source_type,
                handler,
                fail_closed=fail_closed,
                metadata=metadata,
            )

    def _remove_extension(self, extension: Any) -> None:
        for index, current in enumerate(self._extensions):
            if current is extension:
                self._extensions.pop(index)
                return

    def _remove_entry(self, entries: List[Dict[str, Any]], target: Dict[str, Any]) -> None:
        for index, entry in enumerate(entries):
            if entry is target:
                entries.pop(index)
                return

    def _record_bus_diagnostics(self, dispatch_result: Any, event_name: str) -> None:
        for diagnostic in list(getattr(dispatch_result, "diagnostics", []) or []):
            metadata = dict(diagnostic.get("metadata") or {})
            metadata["agent_event_type"] = str(diagnostic.get("event_type") or "")
            metadata["handler_kind"] = str(diagnostic.get("kind") or "")
            self._diagnostics.append(
                ExtensionDiagnostic(
                    extension_id=str(diagnostic.get("source_id") or ""),
                    event=event_name,
                    error=str(diagnostic.get("error") or ""),
                    severity="error",
                    source=str(diagnostic.get("source_type") or "project"),
                    metadata=metadata,
                )
            )

    def _event_handler_for_capability(self, capability: ExtensionCapability) -> Any:
        hook_name = capability.hook_name
        handler = capability.handler
        if hook_name == "context":
            return lambda event, context: handler(event.payload["workflow_event"], context)
        if hook_name == "resources_discover":
            return lambda event, context: handler(event.payload["resources_event"], context)
        if hook_name == "register_tools":
            return lambda event, context: handler(event.payload["tool_registration_event"], context)
        if hook_name == "tool_call":
            return lambda event, context: self._call_tool_call_handler(
                handler, event.payload["workflow_event"], context
            )
        if hook_name == "tool_result":
            return lambda event, context: handler(event.payload["workflow_event"], context)
        if hook_name == "before_agent_start":
            return lambda event, context: handler(event.payload["workflow_event"], context)
        if hook_name == "should_inject_workflow":
            return lambda event, context: handler(
                event.payload["user_text"],
                event.payload["current_mode"],
            )
        if hook_name == "describe_prompt":
            return lambda event, context: handler(
                event.payload["current_mode"],
                workflow_state=event.payload["workflow_state"],
                session=event.payload.get("session"),
            )
        if hook_name == "initialize_workflow_state":
            return lambda event, context: handler(
                event.payload["session"],
                user_text=event.payload["user_text"],
                current_mode=event.payload["current_mode"],
                workflow_state=event.payload["workflow_state"],
            )
        if hook_name == "allowed_tool_names":
            return lambda event, context: handler(
                event.payload["mode_name"],
                workflow_state=event.payload["workflow_state"],
            )
        if hook_name == "load_session_tasks":
            return lambda event, context: handler(
                workspace=event.payload["workspace"],
                session_id=event.payload["session_id"],
            )
        if hook_name == "handle_tool_call":
            return lambda event, context: handler(
                event.payload["session"],
                tool_name=event.payload["tool_name"],
                current_mode=event.payload["current_mode"],
                workflow_state=event.payload["workflow_state"],
            )
        return lambda event, context: handler(event, context)

    def _call_tool_call_handler(
        self,
        handler: Any,
        workflow_event: WorkflowEvent,
        context: ExtensionContext,
    ) -> Any:
        decision = handler(workflow_event, context)
        updated = getattr(decision, "updated_arguments", None)
        if updated is not None:
            workflow_event.tool_arguments = dict(updated)
        return decision

    def _dispatch_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        context: Any = None,
        event_name: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        reducer_stop: Any = None,
    ) -> Any:
        hook_event_name = str(event_name or event_type.rsplit(".", 1)[-1])
        try:
            dispatch = self._event_bus.dispatch(
                AgentEvent(
                    event_type=event_type,
                    payload=dict(payload or {}),
                    metadata=dict(metadata or {}),
                ),
                context,
                reducer_stop=reducer_stop,
            )
        except AgentEventDispatchError as exc:
            self._record_bus_diagnostics(exc, hook_event_name)
            raise exc.original
        self._record_bus_diagnostics(dispatch, hook_event_name)
        return dispatch

    def context(
        self,
        event: WorkflowEvent,
        context: ExtensionContext,
    ) -> ContextPatch:
        merged = ContextPatch()
        dispatch = self._dispatch_event(
            "extension.context",
            {"workflow_event": event},
            context,
            event_name="context",
            metadata={"current_mode": event.current_mode},
        )
        for item in dispatch.reducer_results:
            patch = item.get("value")
            messages = list(getattr(patch, "messages", []) or [])
            if messages:
                merged.messages = messages
            merged.metadata.update(dict(getattr(patch, "metadata", {}) or {}))
        return merged

    def _append_unique(self, target: List[str], values: List[str]) -> None:
        seen = set(target)
        for value in values:
            text = str(value or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            target.append(text)

    def discover_resources(self, cwd: str, reason: str = "startup") -> ResourcesDiscoverResult:
        event = ResourcesDiscoverEvent(
            cwd=str(cwd or ""),
            reason=str(reason or "startup"),
        )
        context = ExtensionContext(workspace=str(cwd or ""))
        merged = ResourcesDiscoverResult()
        dispatch = self._dispatch_event(
            "extension.resources_discover",
            {"resources_event": event},
            context,
            event_name="resources_discover",
            metadata={"reason": event.reason},
        )
        for item in dispatch.reducer_results:
            result = item.get("value")
            self._append_unique(merged.skill_paths, list(getattr(result, "skill_paths", []) or []))
            self._append_unique(
                merged.prompt_paths, list(getattr(result, "prompt_paths", []) or [])
            )
            self._append_unique(
                merged.recipe_paths, list(getattr(result, "recipe_paths", []) or [])
            )
            merged.metadata.update(dict(getattr(result, "metadata", {}) or {}))
        return merged

    def register_tools(
        self,
        event: ToolRegistrationEvent,
        context: ExtensionContext,
    ) -> None:
        registry = getattr(context, "tool_registry", None)
        register_tool = getattr(registry, "register_tool", None)
        if not callable(register_tool):
            return
        dispatch = self._dispatch_event(
            "extension.register_tools",
            {"tool_registration_event": event},
            context,
            event_name="register_tools",
            metadata={
                "current_mode": event.current_mode,
                "workflow_state_name": event.workflow_state_name,
                "reason": event.reason,
            },
        )
        for item in dispatch.reducer_results:
            result = item.get("value")
            tools = list(getattr(result, "tools", []) or [])
            source_id = str(getattr(result, "source_id", "") or item.get("source_id") or "")
            source_type = str(getattr(result, "source_type", "") or "extension")
            for tool in tools:
                tool_name = str(getattr(tool, "name", "") or "")
                try:
                    register_tool(
                        tool,
                        source_id=source_id,
                        source_type=source_type,
                    )
                except (RuntimeError, ValueError, TypeError, OSError) as exc:
                    self.record_diagnostic(
                        str(item.get("source_id") or ""),
                        "register_tools",
                        str(exc),
                        severity="error",
                        source=str(item.get("source_type") or "project"),
                        metadata={
                            "tool_name": tool_name,
                            "source_id": source_id,
                            "source_type": source_type,
                            "reason": str(event.reason or ""),
                        },
                    )
                    if str(item.get("source_type") or "") == "builtin":
                        raise

    def register_context_reducers(self, reducer_registry: Any) -> None:
        with self._context_reducer_registration_lock:
            for entry in list(self._context_reducer_capabilities):
                if any(
                    registered_registry is reducer_registry and registered_entry is entry
                    for registered_registry, registered_entry in self._context_reducer_registrations
                ):
                    continue
                handler = entry["handler"]
                extension_id = str(entry["source_id"] or "")
                source = str(entry["source_type"] or "project")
                try:
                    handler(reducer_registry)
                except (RuntimeError, ValueError, TypeError, OSError) as exc:
                    self.record_diagnostic(
                        extension_id,
                        "register_context_reducers",
                        str(exc),
                        severity="error",
                        source=source,
                    )
                    if bool(entry.get("fail_closed")):
                        raise
                    continue
                self._context_reducer_registrations.append((reducer_registry, entry))

    def before_tool_call(
        self,
        event: WorkflowEvent,
        context: ExtensionContext,
    ) -> ToolCallDecision:
        merged = ToolCallDecision()
        dispatch = self._dispatch_event(
            "extension.tool_call",
            {"workflow_event": event},
            context,
            event_name="tool_call",
            metadata={"tool_name": event.tool_name},
            reducer_stop=lambda value: bool(getattr(value, "block", False)),
        )
        for item in dispatch.reducer_results:
            decision = item.get("value")
            if bool(getattr(decision, "block", False)):
                merged.block = True
                merged.reason = str(getattr(decision, "reason", "") or "")
                if getattr(decision, "updated_arguments", None) is not None:
                    merged.updated_arguments = dict(getattr(decision, "updated_arguments"))
                merged.metadata.update(dict(getattr(decision, "metadata", {}) or {}))
                return merged
            updated = getattr(decision, "updated_arguments", None)
            if updated is not None:
                merged.updated_arguments = dict(updated)
            merged.metadata.update(dict(getattr(decision, "metadata", {}) or {}))
        return merged

    def after_tool_result(
        self,
        event: WorkflowEvent,
        context: ExtensionContext,
    ) -> ToolResultPatch:
        merged = ToolResultPatch()
        dispatch = self._dispatch_event(
            "extension.tool_result",
            {"workflow_event": event},
            context,
            event_name="tool_result",
            metadata={"tool_name": event.tool_name},
        )
        for item in dispatch.reducer_results:
            patch = item.get("value")
            observation = getattr(patch, "observation", None)
            if observation is not None:
                merged.observation = observation
                event.observation = observation
            workflow_patch = getattr(patch, "workflow_patch", None)
            if workflow_patch is not None:
                merged.workflow_patch = workflow_patch
            merged.metadata.update(dict(getattr(patch, "metadata", {}) or {}))
        return merged

    def before_agent_start(
        self,
        event: WorkflowEvent,
        context: ExtensionContext,
    ) -> PromptPatch:
        merged = PromptPatch()
        dispatch = self._dispatch_event(
            "extension.before_agent_start",
            {"workflow_event": event},
            context,
            event_name="before_agent_start",
            metadata={"current_mode": event.current_mode},
        )
        for item in dispatch.reducer_results:
            patch = item.get("value")
            merged.prompt_units.extend(list(getattr(patch, "prompt_units", []) or []))
            append = str(getattr(patch, "system_prompt_append", "") or "")
            if append:
                if merged.system_prompt_append:
                    merged.system_prompt_append += "\n"
                merged.system_prompt_append += append
            merged.active_tool_names.extend(list(getattr(patch, "active_tool_names", []) or []))
            merged.metadata.update(dict(getattr(patch, "metadata", {}) or {}))
        return merged

    def should_inject_workflow(self, user_text: str, current_mode: str) -> bool:
        dispatch = self._dispatch_event(
            "extension.should_inject_workflow",
            {"user_text": user_text, "current_mode": current_mode},
            None,
            event_name="should_inject_workflow",
            metadata={"current_mode": current_mode},
            reducer_stop=lambda value: bool(value),
        )
        for item in dispatch.reducer_results:
            if bool(item.get("value")):
                return True
        return False

    def describe_prompt(
        self,
        current_mode: str,
        workflow_state: str = "",
        session: Any = None,
    ) -> Optional[WorkflowPrompt]:
        dispatch = self._dispatch_event(
            "extension.describe_prompt",
            {
                "current_mode": current_mode,
                "workflow_state": workflow_state,
                "session": session,
            },
            None,
            event_name="describe_prompt",
            metadata={"current_mode": current_mode, "workflow_state": workflow_state},
            reducer_stop=lambda value: value is not None,
        )
        for item in dispatch.reducer_results:
            prompt = item.get("value")
            if prompt is not None:
                return prompt
        return None

    def initialize_workflow_state(
        self,
        session: Any,
        user_text: str,
        current_mode: str,
        workflow_state: str = "",
    ) -> Optional[WorkflowPatch]:
        dispatch = self._dispatch_event(
            "extension.initialize_workflow_state",
            {
                "session": session,
                "user_text": user_text,
                "current_mode": current_mode,
                "workflow_state": workflow_state,
            },
            None,
            event_name="initialize_workflow_state",
            metadata={"current_mode": current_mode, "workflow_state": workflow_state},
        )
        merged = WorkflowPatch()
        found = False
        for item in dispatch.reducer_results:
            patch = item.get("value")
            workflow = getattr(patch, "workflow", None)
            metadata = getattr(patch, "metadata", None)
            if isinstance(workflow, dict) and workflow:
                merged.workflow = dict(workflow)
                found = True
            if isinstance(metadata, dict) and metadata:
                merged.metadata.update(dict(metadata))
                found = True
        return merged if found else None

    def allowed_tool_names(
        self,
        mode_name: str,
        workflow_state: str = "",
        base_tool_names: Optional[Set[str]] = None,
    ) -> Set[str]:
        names = set(base_tool_names or set())
        dispatch = self._dispatch_event(
            "extension.allowed_tool_names",
            {"mode_name": mode_name, "workflow_state": workflow_state},
            None,
            event_name="allowed_tool_names",
            metadata={"mode_name": mode_name, "workflow_state": workflow_state},
        )
        for item in dispatch.reducer_results:
            names.update(set(item.get("value") or set()))
        return names

    def load_session_tasks(self, workspace: str, session_id: str) -> Dict[str, Any]:
        dispatch = self._dispatch_event(
            "extension.load_session_tasks",
            {"workspace": workspace, "session_id": session_id},
            None,
            event_name="load_session_tasks",
            metadata={"session_id": session_id},
            reducer_stop=lambda value: isinstance(value, dict),
        )
        for item in dispatch.reducer_results:
            payload = item.get("value")
            if isinstance(payload, dict):
                return dict(payload)
        return {"count": 0, "tasks": [], "path": "", "session_id": str(session_id or "")}

    def handle_tool_call(
        self,
        session: Any,
        tool_name: str,
        current_mode: str,
        workflow_state: str = "",
        source_type: str = "",
        source_id: str = "",
    ) -> Optional[Any]:
        dispatch = self._dispatch_event(
            "extension.handle_tool_call",
            {
                "session": session,
                "tool_name": tool_name,
                "current_mode": current_mode,
                "workflow_state": workflow_state,
            },
            None,
            event_name="handle_tool_call",
            metadata={
                "tool_name": tool_name,
                "current_mode": current_mode,
                "source_type": source_type,
                "source_id": source_id,
            },
            reducer_stop=(None if source_id else lambda value: value is not None),
        )
        for item in dispatch.reducer_results:
            observation = item.get("value")
            if source_id and str(item.get("source_id") or "") != source_id:
                continue
            if observation is not None:
                return observation
        return None
