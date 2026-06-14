from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from embedagent.agent_event_bus import AgentEvent, AgentEventBus, AgentEventDispatchError


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
class PromptPatch:
    prompt_units: List[str] = field(default_factory=list)
    system_prompt_append: str = ""
    active_tool_names: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HarnessPrompt:
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
    legacy_projection: Dict[str, Any] = field(default_factory=dict)
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
    workflow_state_name: str = "chat"
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
        for extension in list(extensions or []):
            self.register(extension)

    def register(self, extension: Any) -> None:
        self._extensions.append(extension)
        self._register_bus_reducers(extension)

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
        for extension in self._extensions:
            manifest_method = getattr(extension, "package_manifest", None)
            if not callable(manifest_method):
                continue
            extension_id = self._extension_id(extension)
            source = "builtin" if self._is_builtin_extension(extension) else "project"
            try:
                payload = manifest_method()
            except (RuntimeError, ValueError, TypeError, OSError) as exc:
                self.record_diagnostic(
                    extension_id,
                    "package_manifest",
                    str(exc),
                    severity="error",
                    source=source,
                )
                if source == "builtin":
                    raise
                continue
            if isinstance(payload, dict):
                manifests.append(dict(payload))
        return manifests

    def _extension_id(self, extension: Any) -> str:
        explicit = str(getattr(extension, "extension_id", "") or "").strip()
        if explicit:
            return explicit
        name = getattr(extension.__class__, "__name__", "")
        return str(name or "extension")

    def _is_builtin_extension(self, extension: Any) -> bool:
        return bool(getattr(extension, "builtin_extension", True))

    def _register_bus_reducers(self, extension: Any) -> None:
        source_id = self._extension_id(extension)
        source_type = "builtin" if self._is_builtin_extension(extension) else "project"
        fail_closed = self._is_builtin_extension(extension)
        self._register_extension_reducer(
            extension,
            source_id,
            source_type,
            fail_closed,
            "context",
            "extension.context",
            lambda event, context, ext=extension: ext.context(
                event.payload["workflow_event"], context
            ),
        )
        self._register_extension_reducer(
            extension,
            source_id,
            source_type,
            fail_closed,
            "resources_discover",
            "extension.resources_discover",
            lambda event, context, ext=extension: ext.resources_discover(
                event.payload["resources_event"], context
            ),
        )
        self._register_extension_reducer(
            extension,
            source_id,
            source_type,
            fail_closed,
            "register_tools",
            "extension.register_tools",
            lambda event, context, ext=extension: ext.register_tools(
                event.payload["tool_registration_event"], context
            ),
        )
        self._register_extension_reducer(
            extension,
            source_id,
            source_type,
            fail_closed,
            "tool_call",
            "extension.tool_call",
            lambda event, context, ext=extension: self._call_tool_call_reducer(
                ext, event.payload["workflow_event"], context
            ),
        )
        self._register_extension_reducer(
            extension,
            source_id,
            source_type,
            fail_closed,
            "tool_result",
            "extension.tool_result",
            lambda event, context, ext=extension: ext.tool_result(
                event.payload["workflow_event"], context
            ),
        )
        self._register_extension_reducer(
            extension,
            source_id,
            source_type,
            fail_closed,
            "before_agent_start",
            "extension.before_agent_start",
            lambda event, context, ext=extension: ext.before_agent_start(
                event.payload["workflow_event"], context
            ),
        )
        self._register_extension_reducer(
            extension,
            source_id,
            source_type,
            fail_closed,
            "should_inject_workflow",
            "extension.should_inject_workflow",
            lambda event, context, ext=extension: ext.should_inject_workflow(
                event.payload["user_text"],
                event.payload["current_mode"],
            ),
        )
        self._register_extension_reducer(
            extension,
            source_id,
            source_type,
            fail_closed,
            "describe_prompt",
            "extension.describe_prompt",
            lambda event, context, ext=extension: ext.describe_prompt(
                event.payload["current_mode"],
                workflow_state=event.payload["workflow_state"],
                session=event.payload.get("session"),
            ),
        )
        self._register_extension_reducer(
            extension,
            source_id,
            source_type,
            fail_closed,
            "initialize_workflow_state",
            "extension.initialize_workflow_state",
            lambda event, context, ext=extension: ext.initialize_workflow_state(
                event.payload["session"],
                user_text=event.payload["user_text"],
                current_mode=event.payload["current_mode"],
                workflow_state=event.payload["workflow_state"],
            ),
        )
        self._register_extension_reducer(
            extension,
            source_id,
            source_type,
            fail_closed,
            "allowed_tool_names",
            "extension.allowed_tool_names",
            lambda event, context, ext=extension: ext.allowed_tool_names(
                event.payload["mode_name"],
                workflow_state=event.payload["workflow_state"],
            ),
        )
        self._register_extension_reducer(
            extension,
            source_id,
            source_type,
            fail_closed,
            "load_session_tasks",
            "extension.load_session_tasks",
            lambda event, context, ext=extension: ext.load_session_tasks(
                workspace=event.payload["workspace"],
                session_id=event.payload["session_id"],
            ),
        )
        self._register_extension_reducer(
            extension,
            source_id,
            source_type,
            fail_closed,
            "handle_tool_call",
            "extension.handle_tool_call",
            lambda event, context, ext=extension: ext.handle_tool_call(
                event.payload["session"],
                tool_name=event.payload["tool_name"],
                current_mode=event.payload["current_mode"],
                workflow_state=event.payload["workflow_state"],
            ),
        )

    def _register_extension_reducer(
        self,
        extension: Any,
        source_id: str,
        source_type: str,
        fail_closed: bool,
        hook_name: str,
        event_type: str,
        reducer: Any,
    ) -> None:
        if callable(getattr(extension, hook_name, None)):
            self._event_bus.register_reducer(
                event_type,
                source_id,
                source_type,
                reducer,
                fail_closed=fail_closed,
                metadata={"hook_name": hook_name},
            )

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

    def _call_tool_call_reducer(
        self,
        extension: Any,
        workflow_event: WorkflowEvent,
        context: ExtensionContext,
    ) -> Any:
        decision = extension.tool_call(workflow_event, context)
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
        workflow_state: str = "chat",
        session: Any = None,
    ) -> Optional[HarnessPrompt]:
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
        workflow_state: str = "chat",
    ) -> None:
        self._dispatch_event(
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

    def allowed_tool_names(
        self,
        mode_name: str,
        workflow_state: str = "chat",
        fallback: Optional[Set[str]] = None,
    ) -> Set[str]:
        names = set(fallback or set())
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
        workflow_state: str = "chat",
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
            metadata={"tool_name": tool_name, "current_mode": current_mode},
            reducer_stop=lambda value: value is not None,
        )
        for item in dispatch.reducer_results:
            observation = item.get("value")
            if observation is not None:
                return observation
        return None
