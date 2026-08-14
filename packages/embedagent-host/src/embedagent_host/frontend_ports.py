from __future__ import annotations

import difflib
from dataclasses import asdict, is_dataclass
from typing import Any, Callable, Dict, List, Optional

from embedagent_protocol import (
    AgentApplicationDescriptor,
    CapabilitySnapshot,
    CommandDescriptor,
    FrontendSessionPort,
    FrontendWorkspacePort,
    ModeDescriptor,
    SessionBootstrap,
    ThreadShell,
    ToolPresentation,
    WorkflowPackageDescriptor,
)

from embedagent_host.frontend_errors import FrontendPortError, failure_for_exception


def _frontend_call(source: str, operation: Callable[[], Any]) -> Any:
    try:
        return operation()
    except FrontendPortError:
        raise
    except Exception as exc:
        raise FrontendPortError(failure_for_exception(exc, source=source)) from exc


def _mapping(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("frontend projection must be a mapping")
    return dict(value)


def _dto_mapping(value: Any, field_name: str) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        if isinstance(payload, dict):
            return dict(payload)
    if is_dataclass(value):
        payload = asdict(value)
        if isinstance(payload, dict):
            return payload
    raise ValueError("%s must be a mapping or protocol DTO" % field_name)


def _records(value: Any, field_name: str) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("%s must be a list" % field_name)
    records = []
    for item in value:
        records.append(_mapping(item))
    return records


def _application(value: Any) -> Optional[AgentApplicationDescriptor]:
    data = _mapping(value) if value else {}
    if not data:
        return None
    return AgentApplicationDescriptor(
        id=str(data.get("applicationId") or data.get("id") or ""),
        label=str(data.get("label") or ""),
        profile_id=str(data.get("profileId") or data.get("profile_id") or ""),
        workflow_package_ids=[
            str(item)
            for item in list(
                data.get("workflowPackageIds") or data.get("workflow_package_ids") or []
            )
        ],
        active=bool(data.get("active")),
        source_type=str(data.get("sourceType") or data.get("source_type") or ""),
        source_id=str(data.get("sourceId") or data.get("source_id") or ""),
        default=bool(data.get("default")),
        metadata=dict(data.get("metadata") or {}),
    )


def capability_snapshot(value: Any) -> CapabilitySnapshot:
    data = _mapping(value)
    modes = []
    for item in _records(data.get("modes", []), "capabilities.modes"):
        modes.append(
            ModeDescriptor(
                id=str(item.get("id") or item.get("slug") or ""),
                label=str(item.get("label") or item.get("name") or ""),
                description=str(item.get("description") or ""),
                icon_key=str(item.get("icon_key") or ""),
                color_token=str(item.get("color_token") or ""),
                command_id=str(item.get("command_id") or ""),
            )
        )
    commands = []
    for item in _records(data.get("commands", []), "capabilities.commands"):
        if item.get("active") is False:
            continue
        commands.append(
            CommandDescriptor(
                id=str(item.get("id") or item.get("name") or ""),
                label=str(item.get("label") or item.get("usage") or ""),
                group=str(item.get("group") or item.get("source_type") or "builtin"),
                dispatch=dict(item.get("dispatch") or {}),
                shortcut=str(item.get("shortcut") or ""),
                availability=dict(item.get("availability") or {}),
                summary=str(item.get("summary") or ""),
                source_type=str(item.get("source_type") or ""),
                source_id=str(item.get("source_id") or ""),
            )
        )
    tools = []
    for item in _records(data.get("tools", []), "capabilities.tools"):
        if item.get("active") is False:
            continue
        tools.append(
            ToolPresentation(
                name=str(item.get("name") or ""),
                label=str(item.get("label") or item.get("name") or ""),
                icon_key=str(item.get("icon_key") or ""),
                renderer_key=str(item.get("renderer_key") or "generic"),
                permission_category=str(item.get("permission_category") or "other"),
                metadata=dict(item.get("metadata") or {}),
            )
        )
    workflow_packages = []
    for item in _records(
        data.get("workflowPackages", data.get("workflow_packages", [])),
        "capabilities.workflow_packages",
    ):
        workflow_packages.append(
            WorkflowPackageDescriptor(
                id=str(item.get("id") or ""),
                label=str(item.get("label") or ""),
                active=bool(item.get("active")),
                state=dict(item.get("state") or {}),
                metadata=dict(item.get("metadata") or {}),
            )
        )
    application = _application(data.get("agentApplication", data.get("agent_application")))
    applications = []
    for item in _records(
        data.get("agentApplications", data.get("agent_applications", [])),
        "capabilities.agent_applications",
    ):
        descriptor = _application(item)
        if descriptor is not None:
            applications.append(descriptor)
    return CapabilitySnapshot(
        schema_version=1,
        modes=modes,
        commands=commands,
        tools=tools,
        workflow_packages=workflow_packages,
        agent_application=application,
        agent_applications=applications,
        resources=_records(data.get("resources", []), "capabilities.resources"),
        model_profiles=_records(
            data.get("modelProfiles", data.get("model_profiles", [])),
            "capabilities.model_profiles",
        ),
        empty_state=dict(data.get("emptyState", data.get("empty_state", {})) or {}),
    )


def thread_shell(value: Any) -> ThreadShell:
    data = _mapping(value)
    thread = data.get("thread") if isinstance(data.get("thread"), dict) else {}
    session_id = str(data.get("session_id") or data.get("id") or "")
    return ThreadShell(
        id=session_id,
        title=str(data.get("title") or thread.get("title") or ""),
        archived=bool(data.get("archived", thread.get("archived", False))),
        current_mode=str(data.get("current_mode") or ""),
        status=str(data.get("status") or "idle"),
        updated_at=str(data.get("updated_at") or ""),
        pending_interaction=bool(
            data.get("pending_interaction_valid") or data.get("pending_interaction")
        ),
    )


def session_bootstrap(value: Any) -> SessionBootstrap:
    data = _mapping(value)
    snapshot = _mapping(data.get("snapshot"))
    history = _mapping(data.get("history") or {})
    return SessionBootstrap(
        schema_version=1,
        event_cursor=data.get("event_cursor", 0),
        thread=thread_shell(
            {
                **snapshot,
                "thread": data.get("thread") or {},
            }
        ),
        snapshot=snapshot,
        activities=list(history.get("activities") or []),
        capabilities=capability_snapshot(data.get("capabilities") or {}),
        integrity=dict(history.get("integrity") or {}),
        plan=(_dto_mapping(data.get("plan"), "plan") if data.get("plan") is not None else None),
        permission_context=_dto_mapping(
            data.get("permission_context") or {},
            "permission_context",
        ),
    )


class InProcessFrontendSessionPort(FrontendSessionPort):
    def __init__(self, adapter: Any) -> None:
        self._adapter = adapter

    def list_sessions(self, limit: int = 10) -> List[ThreadShell]:
        return _frontend_call(
            "session",
            lambda: [thread_shell(item) for item in self._adapter.list_sessions(limit=limit)],
        )

    def load_session_summary(self, reference: str) -> Dict[str, Any]:
        return _frontend_call(
            "session",
            lambda: dict(self._adapter.summary_store.load_summary(reference)),
        )

    def get_session_bootstrap(self, reference: str, mode: str = "") -> SessionBootstrap:
        return _frontend_call(
            "session",
            lambda: session_bootstrap(self._adapter.get_session_bootstrap(reference, mode)),
        )

    def get_session_capabilities(self, session_id: str = "") -> CapabilitySnapshot:
        return _frontend_call(
            "session",
            lambda: capability_snapshot(self._adapter.get_session_capabilities(session_id)),
        )

    def create_session(self, mode: str) -> SessionBootstrap:
        def create() -> SessionBootstrap:
            snapshot = self._adapter.create_session(mode)
            return self.get_session_bootstrap(str(snapshot.get("session_id") or ""))

        return _frontend_call("session", create)

    def resume_session(self, reference: str, mode: str) -> SessionBootstrap:
        def resume() -> SessionBootstrap:
            snapshot = self._adapter.resume_session(reference, mode)
            return self.get_session_bootstrap(str(snapshot.get("session_id") or ""))

        return _frontend_call("session", resume)

    def submit_user_message(self, session_id: str, text: str, stream: bool) -> None:
        _frontend_call(
            "session",
            lambda: self._adapter.submit_user_message(
                session_id=session_id,
                text=text,
                stream=stream,
                wait=False,
            ),
        )

    def cancel_session(self, session_id: str) -> SessionBootstrap:
        return _frontend_call(
            "session",
            lambda: self._cancel_and_bootstrap(session_id),
        )

    def set_session_mode(self, session_id: str, mode: str) -> SessionBootstrap:
        return _frontend_call(
            "session",
            lambda: self._set_mode_and_bootstrap(session_id, mode),
        )

    def respond_to_interaction(
        self,
        session_id: str,
        interaction_id: str,
        payload: Dict[str, Any],
    ) -> SessionBootstrap:
        return _frontend_call(
            "session",
            lambda: self._respond_and_bootstrap(session_id, interaction_id, payload),
        )

    def rename_session(self, session_id: str, title: str) -> ThreadShell:
        return _frontend_call(
            "session",
            lambda: thread_shell(self._adapter.rename_session(session_id, title)),
        )

    def archive_session(self, session_id: str) -> ThreadShell:
        return _frontend_call(
            "session",
            lambda: thread_shell(self._adapter.archive_session(session_id)),
        )

    def fork_session(self, session_id: str, title: str = "") -> ThreadShell:
        return _frontend_call(
            "session",
            lambda: thread_shell(self._adapter.fork_session(session_id, title)),
        )

    def close(self) -> None:
        shutdown = getattr(self._adapter, "shutdown", None)
        if callable(shutdown):
            _frontend_call("session", shutdown)

    def _cancel_and_bootstrap(self, session_id: str) -> SessionBootstrap:
        self._adapter.cancel_session(session_id)
        return self.get_session_bootstrap(session_id)

    def _set_mode_and_bootstrap(self, session_id: str, mode: str) -> SessionBootstrap:
        self._adapter.set_session_mode(session_id, mode)
        return self.get_session_bootstrap(session_id)

    def _respond_and_bootstrap(
        self,
        session_id: str,
        interaction_id: str,
        payload: Dict[str, Any],
    ) -> SessionBootstrap:
        self._adapter.respond_to_interaction(session_id, interaction_id, payload)
        return self.get_session_bootstrap(session_id)


class InProcessFrontendWorkspacePort(FrontendWorkspacePort):
    def __init__(self, adapter: Any) -> None:
        self._adapter = adapter

    def get_workspace_snapshot(self) -> Dict[str, Any]:
        return _frontend_call(
            "workspace",
            lambda: dict(self._adapter.get_workspace_snapshot()),
        )

    def list_workspace_tree(
        self,
        path: str = ".",
        max_depth: int = 3,
        limit: int = 200,
    ) -> Dict[str, Any]:
        return _frontend_call(
            "workspace",
            lambda: dict(
                self._adapter.list_workspace_tree(
                    path=path,
                    max_depth=max_depth,
                    limit=limit,
                )
            ),
        )

    def list_file_children(self, path: str = ".", limit: int = 200) -> List[Dict[str, Any]]:
        return _frontend_call(
            "workspace",
            lambda: list(self._adapter.list_workspace_children(path, limit).get("items") or []),
        )

    def read_file(self, path: str) -> Dict[str, Any]:
        return _frontend_call(
            "workspace",
            lambda: dict(self._adapter.read_workspace_file(path)),
        )

    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        return _frontend_call(
            "workspace",
            lambda: dict(self._adapter.write_workspace_file(path, content)),
        )

    def get_diff_preview(self, path: str, new_content: str) -> Dict[str, Any]:
        try:
            old_content = str(self.read_file(path).get("content") or "")
        except (FrontendPortError, OSError, TypeError, ValueError):
            old_content = ""
        unified_diff = "".join(
            difflib.unified_diff(
                old_content.splitlines(True),
                new_content.splitlines(True),
                fromfile=path,
                tofile=path,
                lineterm="",
            )
        )
        return {
            "path": path,
            "old_content": old_content,
            "new_content": new_content,
            "unified_diff": unified_diff,
        }

    def reload_resources(self, session_id: str = "", reason: str = "api") -> Dict[str, Any]:
        return _frontend_call(
            "workspace",
            lambda: dict(self._adapter.reload_resources(session_id=session_id, reason=reason)),
        )
