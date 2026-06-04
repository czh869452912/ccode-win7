from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


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


class ExtensionManager(object):
    def __init__(self, extensions: Optional[List[Any]] = None) -> None:
        self._extensions = []  # type: List[Any]
        self._diagnostics = []  # type: List[ExtensionDiagnostic]
        for extension in list(extensions or []):
            self.register(extension)

    def register(self, extension: Any) -> None:
        self._extensions.append(extension)

    def diagnostics(self) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in self._diagnostics]

    def clear_diagnostics(self) -> None:
        self._diagnostics = []

    def _extension_id(self, extension: Any) -> str:
        explicit = str(getattr(extension, "extension_id", "") or "").strip()
        if explicit:
            return explicit
        name = getattr(extension.__class__, "__name__", "")
        return str(name or "extension")

    def _is_builtin_extension(self, extension: Any) -> bool:
        return bool(getattr(extension, "builtin_extension", True))

    def _record_hook_error(self, extension: Any, event_name: str, exc: Exception) -> None:
        self._diagnostics.append(
            ExtensionDiagnostic(
                extension_id=self._extension_id(extension),
                event=event_name,
                error=str(exc),
                severity="error",
                source="builtin" if self._is_builtin_extension(extension) else "project",
            )
        )

    def _call_hook(self, extension: Any, event_name: str, *args: Any, **kwargs: Any) -> Any:
        hook = getattr(extension, event_name, None)
        if not callable(hook):
            return None
        try:
            return hook(*args, **kwargs)
        except Exception as exc:
            self._record_hook_error(extension, event_name, exc)
            if self._is_builtin_extension(extension):
                raise
            return None

    def context(
        self,
        event: WorkflowEvent,
        context: ExtensionContext,
    ) -> ContextPatch:
        merged = ContextPatch()
        for extension in list(self._extensions):
            patch = self._call_hook(extension, "context", event, context)
            if patch is None:
                continue
            messages = list(getattr(patch, "messages", []) or [])
            if messages:
                merged.messages = messages
            merged.metadata.update(dict(getattr(patch, "metadata", {}) or {}))
        return merged

    def before_agent_start(
        self,
        event: WorkflowEvent,
        context: ExtensionContext,
    ) -> PromptPatch:
        merged = PromptPatch()
        for extension in list(self._extensions):
            hook = getattr(extension, "before_agent_start", None)
            if not callable(hook):
                continue
            patch = hook(event, context)
            if patch is None:
                continue
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
        for extension in list(self._extensions):
            hook = getattr(extension, "should_inject_workflow", None)
            if callable(hook) and bool(hook(user_text, current_mode)):
                return True
        return False

    def describe_prompt(
        self,
        current_mode: str,
        workflow_state: str = "chat",
        session: Any = None,
    ) -> Optional[HarnessPrompt]:
        for extension in list(self._extensions):
            hook = getattr(extension, "describe_prompt", None)
            if not callable(hook):
                continue
            prompt = hook(current_mode, workflow_state=workflow_state, session=session)
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
        for extension in list(self._extensions):
            hook = getattr(extension, "initialize_workflow_state", None)
            if callable(hook):
                hook(
                    session,
                    user_text=user_text,
                    current_mode=current_mode,
                    workflow_state=workflow_state,
                )

    def allowed_tool_names(
        self,
        mode_name: str,
        workflow_state: str = "chat",
        fallback: Optional[Set[str]] = None,
    ) -> Set[str]:
        names = set(fallback or set())
        for extension in list(self._extensions):
            hook = getattr(extension, "allowed_tool_names", None)
            if callable(hook):
                names.update(set(hook(mode_name, workflow_state=workflow_state) or set()))
        return names

    def load_session_tasks(self, workspace: str, session_id: str) -> Dict[str, Any]:
        for extension in list(self._extensions):
            hook = getattr(extension, "load_session_tasks", None)
            if not callable(hook):
                continue
            payload = hook(workspace=workspace, session_id=session_id)
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
        for extension in list(self._extensions):
            hook = getattr(extension, "handle_tool_call", None)
            if not callable(hook):
                continue
            observation = hook(
                session,
                tool_name=tool_name,
                current_mode=current_mode,
                workflow_state=workflow_state,
            )
            if observation is not None:
                return observation
        return None
