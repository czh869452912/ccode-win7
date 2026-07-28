from __future__ import annotations

import os
import threading
from copy import deepcopy
from typing import Any, Callable, Optional, Tuple

from embedagent_core.agent_extension_host import AgentExtensionHost
from embedagent_core.agent_lifecycle import AgentLifecycleJournal
from embedagent_core.interaction import (
    UserInputRequest,
    UserInputResponse,
    build_user_input_request,
)
from embedagent_core.permissions import PermissionPolicy, PermissionRequest
from embedagent_core.policies import DenyWritePathPolicy, WritePathPolicy
from embedagent_core.session import Action, Observation, QueryTurnResult, Session
from embedagent_core.session_journal import EventIntent
from embedagent_core.tool_contracts import ToolError, ToolRuntimePort


class AgentToolActionService(object):
    """Non-LLM tool action execution boundary for QueryEngine."""

    def __init__(
        self,
        tools: ToolRuntimePort,
        permission_policy: PermissionPolicy,
        extension_host: AgentExtensionHost,
        app_config_provider: Callable[[], Any],
        failure_observation_factory: Callable[..., Observation],
        write_path_policy: Optional[WritePathPolicy] = None,
        permission_pending_handler: Optional[
            Callable[[Session, Action, PermissionRequest, str], QueryTurnResult]
        ] = None,
        permission_rejected_handler: Optional[Callable[[Session, Action], None]] = None,
        user_input_pending_handler: Optional[
            Callable[[Session, Action, UserInputRequest, str], QueryTurnResult]
        ] = None,
        user_input_response_handler: Optional[
            Callable[
                [Session, str, UserInputRequest, UserInputResponse, str, str],
                Tuple[Observation, str],
            ]
        ] = None,
        lifecycle: Optional[AgentLifecycleJournal] = None,
        event_committer: Optional[Callable[[Session, EventIntent], Any]] = None,
    ) -> None:
        self.tools = tools
        self.permission_policy = permission_policy
        self.extension_host = extension_host
        self._app_config_provider = app_config_provider
        self._failure_observation = failure_observation_factory
        self.write_path_policy = write_path_policy or DenyWritePathPolicy()
        self._permission_pending_handler = permission_pending_handler
        self._permission_rejected_handler = permission_rejected_handler
        self._user_input_pending_handler = user_input_pending_handler
        self._user_input_response_handler = user_input_response_handler
        self.lifecycle = lifecycle
        self._event_committer = event_committer

    def is_extension_blocked_observation(self, observation: Optional[Observation]) -> bool:
        if observation is None or not isinstance(observation.data, dict):
            return False
        return observation.data.get("error_kind") == "extension_blocked"

    def is_interactive_serial_skip(self, observation: Optional[Observation]) -> bool:
        if observation is None or not isinstance(observation.data, dict):
            return False
        return observation.data.get("error_kind") == "interactive_serial_skip"

    def prepare_extension_tool_call(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
    ) -> Tuple[Optional[Observation], Action]:
        decision, runtime_action = self.extension_host.prepare_tool_call(
            session,
            action,
            current_mode,
            workflow_state,
        )
        if decision.block:
            return (
                self._failure_observation(
                    action.name,
                    decision.reason or "Tool call blocked by extension.",
                    "extension_blocked",
                    False,
                    "extension",
                    "Use a different tool or update the extension policy.",
                    {"extension_metadata": dict(decision.metadata)},
                ),
                action,
            )
        return None, runtime_action

    def execute_parallel_tool_action(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
        stop_event: Optional[threading.Event],
    ) -> Observation:
        if action.name in ("ask_user", "propose_mode_switch"):
            return Observation(
                action.name,
                False,
                "interactive tool requires serial action handling",
                {"error_kind": "interactive_serial_skip", "retryable": False},
            )
        blocked_observation, runtime_action = self.prepare_extension_tool_call(
            session,
            action,
            current_mode,
            workflow_state,
        )
        if blocked_observation is not None:
            return blocked_observation
        return self.tools.execute_with_interrupt(
            runtime_action.name,
            runtime_action.arguments,
            stop_event,
        )

    def apply_extension_tool_result_patch(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
        observation: Observation,
    ) -> Observation:
        patch = self.extension_host.apply_tool_result_patch(
            session,
            action,
            current_mode,
            workflow_state,
            observation,
        )
        if patch.workflow_patch is not None:
            intent = self._workflow_patch_intent(
                session, action, current_mode, workflow_state, patch.workflow_patch
            )
            if intent is not None:
                self._commit_workflow_patch_event(session, intent)
        return patch.observation if patch.observation is not None else observation

    def execute_action(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]],
        user_input_handler: Optional[Callable[[UserInputRequest], Optional[UserInputResponse]]],
        precomputed_observation: Optional[Observation] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> Tuple[Observation, str, Optional[QueryTurnResult]]:
        result = self._execute_action_inner(
            session,
            action,
            current_mode,
            workflow_state,
            permission_handler,
            user_input_handler,
            precomputed_observation=precomputed_observation,
            stop_event=stop_event,
        )
        return result

    def _execute_action_inner(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]],
        user_input_handler: Optional[Callable[[UserInputRequest], Optional[UserInputResponse]]],
        precomputed_observation: Optional[Observation] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> Tuple[Observation, str, Optional[QueryTurnResult]]:
        runtime_action = action
        if action.name not in self.extension_host.allowed_tool_names(
            current_mode,
            workflow_state=workflow_state,
        ) and action.name not in ("ask_user", "propose_mode_switch"):
            return (
                self._failure_observation(
                    action.name,
                    "当前模式 %s 不允许调用工具 %s。" % (current_mode, action.name),
                    "mode_tool_blocked",
                    False,
                    current_mode,
                    "请改用当前模式允许的工具。",
                ),
                current_mode,
                None,
            )
        if precomputed_observation is not None and not self.is_interactive_serial_skip(
            precomputed_observation
        ):
            if self.is_extension_blocked_observation(precomputed_observation):
                return precomputed_observation, current_mode, None
            observation = self.apply_extension_tool_result_patch(
                session,
                action,
                current_mode,
                workflow_state,
                precomputed_observation,
            )
            return observation, current_mode, None
        blocked_observation, runtime_action = self.prepare_extension_tool_call(
            session,
            action,
            current_mode,
            workflow_state,
        )
        if blocked_observation is not None:
            return blocked_observation, current_mode, None
        if action.name in ("ask_user", "propose_mode_switch"):
            return self._execute_interactive_action(
                session,
                runtime_action,
                current_mode,
                workflow_state,
                user_input_handler,
            )
        observation = self.extension_host.handle_tool_call(
            session,
            tool_name=action.name,
            current_mode=current_mode,
            workflow_state=workflow_state,
        )
        if observation is not None:
            return observation, current_mode, None
        decision = self.permission_policy.evaluate(
            runtime_action,
            remembered_categories=self.permission_policy.remembered_categories_for(session),
        )
        if decision.outcome == "deny":
            if self._permission_rejected_handler is not None:
                self._permission_rejected_handler(session, action)
            return (
                self._failure_observation(
                    action.name,
                    decision.error or "权限规则拒绝该操作。",
                    "permission_denied",
                    False,
                    "permission_policy",
                    "修改权限规则，或由用户手动放行后重试。",
                    {"permission_required": True, "permission_decision": "deny"},
                ),
                current_mode,
                None,
            )
        if decision.request is not None:
            approved = (
                permission_handler(decision.request) if permission_handler is not None else None
            )
            if approved is None:
                if self._permission_pending_handler is None:
                    return (
                        self._failure_observation(
                            action.name,
                            "waiting permission",
                            "pending_interaction",
                            False,
                            "permission",
                            "等待用户批准。",
                            {"pending": True},
                        ),
                        current_mode,
                        None,
                    )
                suspended = self._permission_pending_handler(
                    session,
                    action,
                    decision.request,
                    current_mode,
                )
                return (
                    self._failure_observation(
                        action.name,
                        "waiting permission",
                        "pending_interaction",
                        False,
                        "permission",
                        "等待用户批准。",
                        {"pending": True},
                    ),
                    current_mode,
                    suspended,
                )
            if not approved:
                if self._permission_rejected_handler is not None:
                    self._permission_rejected_handler(session, action)
                return (
                    self._failure_observation(
                        action.name,
                        "操作未获批准，已跳过执行。",
                        "permission_denied",
                        False,
                        "user_confirmation",
                        "等待用户批准，或改为不需要该权限的方案。",
                        {"permission_required": True, "permission_decision": "deny"},
                    ),
                    current_mode,
                    None,
                )
        invalid_path = self._validate_write_path(runtime_action, current_mode)
        if invalid_path is not None:
            return invalid_path, current_mode, None
        observation = self.tools.execute_with_interrupt(
            runtime_action.name,
            runtime_action.arguments,
            stop_event,
        )
        observation = self.apply_extension_tool_result_patch(
            session,
            runtime_action,
            current_mode,
            workflow_state,
            observation,
        )
        return observation, current_mode, None

    def _workflow_patch_intent(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
        workflow_patch: Any,
    ) -> Optional[EventIntent]:
        workflow = deepcopy(dict(getattr(workflow_patch, "workflow", {}) or {}))
        metadata = deepcopy(dict(getattr(workflow_patch, "metadata", {}) or {}))
        if not workflow and not metadata:
            return None
        turn_id = session.turns[-1].turn_id if session.turns else ""
        step = session.current_step()
        step_id = step.step_id if step is not None else ""
        return EventIntent(
            "workflow_patch",
            {
                "turn_id": turn_id,
                "step_id": step_id,
                "tool_call_id": action.call_id,
                "mode_name": current_mode,
                "workflow_state_name": workflow_state,
                "workflow": workflow,
                "metadata": metadata,
            },
        )

    def _commit_workflow_patch_event(
        self,
        session: Session,
        intent: EventIntent,
    ) -> None:
        if self._event_committer is None:
            raise RuntimeError("workflow patch event committer is not configured")
        if self.lifecycle is None:
            self._event_committer(session, intent)
            return
        self.lifecycle.persist_workflow_patch_intent(
            session,
            intent,
            self._event_committer,
        )

    def _execute_interactive_action(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
        user_input_handler: Optional[Callable[[UserInputRequest], Optional[UserInputResponse]]],
    ) -> Tuple[Observation, str, Optional[QueryTurnResult]]:
        request = self._interactive_request(action)
        response = user_input_handler(request) if user_input_handler is not None else None
        if response is None:
            suspended = None
            if self._user_input_pending_handler is not None:
                suspended = self._user_input_pending_handler(
                    session,
                    action,
                    request,
                    current_mode,
                )
            return (
                self._failure_observation(
                    action.name,
                    "waiting user input",
                    "pending_interaction",
                    False,
                    "user_input",
                    "等待用户回答。",
                    {"pending": True},
                ),
                current_mode,
                suspended,
            )
        if self._user_input_response_handler is None:
            return (
                Observation(
                    request.tool_name,
                    True,
                    None,
                    {
                        "question": request.question,
                        "answer": str(response.answer or "").strip(),
                        "selected_index": response.selected_index,
                        "selected_option_text": response.selected_option_text,
                        "selected_mode": str(response.selected_mode or "").strip(),
                        "mode_changed": False,
                    },
                ),
                current_mode,
                None,
            )
        observation, next_mode = self._user_input_response_handler(
            session,
            current_mode,
            request,
            response,
            workflow_state,
            action.name,
        )
        return observation, next_mode, None

    def _interactive_request(self, action: Action) -> UserInputRequest:
        if action.name == "ask_user":
            return build_user_input_request(action.arguments)
        return UserInputRequest(
            "propose_mode_switch",
            str(action.arguments.get("reason") or ""),
            [],
            {"target_mode": str(action.arguments.get("target_mode") or "")},
        )

    def _validate_write_path(
        self,
        action: Action,
        current_mode: str,
    ) -> Optional[Observation]:
        if action.name not in ("edit_file", "write_file"):
            return None
        path = str(action.arguments.get("path") or "")
        if not path:
            return self._failure_observation(
                action.name,
                "%s 缺少 path 参数。" % action.name,
                "invalid_arguments",
                False,
                "arguments",
                "补充一个相对于工作区的 path 参数。",
            )
        normalized = path.replace("\\", "/")
        if not self.write_path_policy.is_path_writable(
            current_mode,
            normalized,
            self._app_config_provider(),
        ):
            return self._failure_observation(
                action.name,
                "当前模式 %s 不允许修改 %s。" % (current_mode, normalized),
                "mode_path_blocked",
                False,
                current_mode,
                "请改用当前模式允许的文件类型，或切换模式。",
            )
        if action.name != "edit_file":
            return None
        try:
            resolved_path = self.tools.path_resolver().resolve_path(
                normalized,
                allow_missing=True,
            )
        except ToolError as exc:
            return self._failure_observation(
                action.name,
                str(exc),
                "path_invalid",
                False,
                "workspace",
                "改用工作区内的相对路径。",
            )
        if not resolved_path or not os.path.exists(resolved_path):
            return self._failure_observation(
                action.name,
                "目标文件不存在，edit_file 只能修改已存在的文件。",
                "file_missing",
                False,
                "filesystem",
                "若要新建文件，请改用 write_file。",
            )
        return None
