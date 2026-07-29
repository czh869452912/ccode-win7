from __future__ import annotations

from typing import Any, Optional, Set, Tuple

from embedagent_core.extensions import (
    ExtensionContext,
    ExtensionManager,
    SessionView,
    ToolRegistrationEvent,
    ToolResultPatch,
    WorkflowEvent,
    WorkflowPatch,
)
from embedagent_core.interaction import ask_user_schema, propose_mode_switch_schema
from embedagent_core.policies import EmptyModeToolPolicy, ModeToolPolicy
from embedagent_core.session import Action, ContextAssemblyResult, Observation, Session
from embedagent_core.session_view import SessionReadView
from embedagent_core.tool_contracts import ToolRuntimePort


class AgentExtensionHost(object):
    """Agent runtime boundary for extension hook dispatch."""

    def __init__(
        self,
        manager: Optional[ExtensionManager],
        tools: ToolRuntimePort,
        permission_policy: Any,
        mode_tool_policy: Optional[ModeToolPolicy] = None,
    ) -> None:
        self.manager = manager or ExtensionManager()
        self.tools = tools
        self.permission_policy = permission_policy
        self._mode_tool_policy = mode_tool_policy or EmptyModeToolPolicy()

    def context_for(self, session: Any) -> ExtensionContext:
        runtime_snapshot = {}
        runtime_lookup = getattr(self.tools, "runtime_environment_snapshot", None)
        if callable(runtime_lookup):
            runtime_snapshot = runtime_lookup()
        return ExtensionContext(
            workspace=str(getattr(self.tools, "workspace", "") or ""),
            runtime_environment=dict(runtime_snapshot or {}),
            tool_registry=self.tools,
            permission_policy=self.permission_policy,
            session_view=SessionView.from_session(session),
        )

    def workflow_event(
        self, session: Any, current_mode: str, workflow_state_name: str, **metadata: Any
    ) -> WorkflowEvent:
        turn_id = session.turns[-1].turn_id if session.turns else ""
        step = session.current_step()
        step_id = step.step_id if step is not None else ""
        return WorkflowEvent(
            session_id=session.session_id,
            turn_id=turn_id,
            step_id=step_id,
            current_mode=current_mode,
            workflow_state=dict(getattr(session, "workflow_state", {}) or {}),
            workflow_state_name=workflow_state_name,
            metadata=dict(metadata),
        )

    def should_inject_workflow(self, user_text: str, current_mode: str) -> bool:
        return bool(self.manager.should_inject_workflow(user_text, current_mode))

    def describe_prompt(
        self,
        current_mode: str,
        workflow_state: str = "",
        session: Any = None,
    ) -> Any:
        return self.manager.describe_prompt(
            current_mode,
            workflow_state=workflow_state,
            session=session,
        )

    def initialize_workflow_state(
        self,
        session: Session,
        user_text: str,
        current_mode: str,
        workflow_state: str = "",
    ) -> Optional[WorkflowPatch]:
        return self.manager.initialize_workflow_state(
            session,
            user_text=user_text,
            current_mode=current_mode,
            workflow_state=workflow_state,
        )

    def allowed_tool_names(self, mode_name: str, workflow_state: str = "") -> Set[str]:
        return set(
            self.manager.allowed_tool_names(
                mode_name,
                workflow_state=workflow_state,
                base_tool_names=set(
                    self._mode_tool_policy.allowed_tools_for(
                        mode_name,
                        workflow_state=workflow_state,
                    )
                ),
            )
        )

    def register_tools(
        self,
        session: Session,
        current_mode: str,
        workflow_state: str,
        reason: str = "turn",
    ) -> None:
        self.manager.register_tools(
            ToolRegistrationEvent(
                current_mode=current_mode,
                workflow_state_name=workflow_state,
                reason=reason,
                metadata={"session_id": session.session_id},
            ),
            self.context_for(session),
        )

    def schemas_for_active_tools(self, mode_name: str, workflow_state: str) -> list:
        active_tool_names = sorted(
            self.allowed_tool_names(mode_name, workflow_state=workflow_state)
        )
        schemas = list(
            self.tools.schemas_for(
                mode_name,
                workflow_state=workflow_state,
                tool_names=active_tool_names,
            )
        )
        names = set(item.get("function", {}).get("name", "") for item in schemas)
        allowed = self.allowed_tool_names(mode_name, workflow_state=workflow_state)
        if "ask_user" in allowed and "ask_user" not in names:
            schemas.append(ask_user_schema())
            names.add("ask_user")
        if "propose_mode_switch" in allowed and "propose_mode_switch" not in names:
            schemas.append(propose_mode_switch_schema())
        return schemas

    def apply_context_patch(
        self,
        session: SessionReadView,
        mode_name: str,
        workflow_state: str,
        assembly: ContextAssemblyResult,
        force_compact: bool = False,
    ) -> ContextAssemblyResult:
        event = self.workflow_event(
            session,
            mode_name,
            workflow_state,
            force_compact=force_compact,
        )
        event.messages = [dict(message) for message in list(assembly.messages or [])]
        patch = self.manager.context(event, self.context_for(session))
        if patch.messages:
            assembly.messages = [dict(message) for message in patch.messages]
        return assembly

    def prepare_tool_call(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
    ) -> Tuple[Any, Action]:
        event = self.workflow_event(session, current_mode, workflow_state)
        event.tool_name = action.name
        event.tool_arguments = dict(action.arguments)
        decision = self.manager.before_tool_call(event, self.context_for(session))
        if decision.updated_arguments is not None:
            action = Action(
                name=action.name,
                arguments=dict(decision.updated_arguments),
                call_id=action.call_id,
                raw_arguments=action.raw_arguments,
            )
        return decision, action

    def apply_tool_result_patch(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
        observation: Observation,
    ) -> ToolResultPatch:
        event = self.workflow_event(session, current_mode, workflow_state)
        event.tool_name = action.name
        event.tool_arguments = dict(action.arguments)
        event.observation = observation
        patch = self.manager.after_tool_result(event, self.context_for(session))
        return ToolResultPatch(
            observation=patch.observation if patch.observation is not None else observation,
            workflow_patch=patch.workflow_patch,
            metadata=dict(patch.metadata or {}),
        )

    def handle_tool_call(
        self,
        session: Session,
        tool_name: str,
        current_mode: str,
        workflow_state: str,
    ) -> Optional[Observation]:
        return self.manager.handle_tool_call(
            session,
            tool_name=tool_name,
            current_mode=current_mode,
            workflow_state=workflow_state,
        )
