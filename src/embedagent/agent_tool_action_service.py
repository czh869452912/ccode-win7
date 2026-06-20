from __future__ import annotations

import os
import threading
from typing import Any, Callable, Optional, Tuple

from embedagent.agent_extension_host import AgentExtensionHost
from embedagent.interaction import UserInputRequest, UserInputResponse
from embedagent.modes import is_path_writable
from embedagent.permissions import PermissionPolicy, PermissionRequest
from embedagent.session import Action, Observation, QueryTurnResult, Session
from embedagent.tools import ToolRuntime
from embedagent.tools._base import ToolError


class AgentToolActionService(object):
    """Non-LLM tool action execution boundary for QueryEngine."""

    def __init__(
        self,
        tools: ToolRuntime,
        permission_policy: PermissionPolicy,
        extension_host: AgentExtensionHost,
        app_config_provider: Callable[[], Any],
        failure_observation_factory: Callable[..., Observation],
        permission_pending_handler: Optional[
            Callable[[Session, Action, PermissionRequest, str], QueryTurnResult]
        ] = None,
        permission_rejected_handler: Optional[Callable[[Session, Action], None]] = None,
    ) -> None:
        self.tools = tools
        self.permission_policy = permission_policy
        self.extension_host = extension_host
        self._app_config_provider = app_config_provider
        self._failure_observation = failure_observation_factory
        self._permission_pending_handler = permission_pending_handler
        self._permission_rejected_handler = permission_rejected_handler

    def is_extension_blocked_observation(self, observation: Optional[Observation]) -> bool:
        if observation is None or not isinstance(observation.data, dict):
            return False
        return observation.data.get("error_kind") == "extension_blocked"

    def is_interactive_precomputed_skip(self, observation: Optional[Observation]) -> bool:
        if observation is None or not isinstance(observation.data, dict):
            return False
        return observation.data.get("error_kind") == "interactive_precomputed_skip"

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
                "interactive tool requires query-engine handling",
                {"error_kind": "interactive_precomputed_skip", "retryable": False},
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
        return self.extension_host.apply_tool_result_patch(
            session,
            action,
            current_mode,
            workflow_state,
            observation,
        )

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
        del user_input_handler
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
        if precomputed_observation is not None and not self.is_interactive_precomputed_skip(
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
        observation = self.extension_host.handle_tool_call(
            session,
            tool_name=action.name,
            current_mode=current_mode,
            workflow_state=workflow_state,
        )
        if observation is not None:
            return observation, current_mode, None
        decision = self.permission_policy.evaluate(runtime_action)
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
        if not is_path_writable(current_mode, normalized, self._app_config_provider()):
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
            resolved_path = self.tools._ctx.resolve_path(normalized, allow_missing=True)
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
