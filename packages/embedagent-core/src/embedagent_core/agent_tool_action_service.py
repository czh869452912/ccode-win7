from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from copy import deepcopy
from dataclasses import replace
from typing import Any, Callable, Dict, List, Optional, Tuple

from embedagent_core.agent_effects import (
    ExecuteToolBatchEffect,
    FrozenToolAction,
    ImmediateToolResult,
    InteractionSuspended,
    PreparedToolInvocation,
    PrepareToolBatchEffect,
    ToolBatchCompleted,
    ToolBatchPrepared,
    _tool_invocation_id,
)
from embedagent_core.agent_extension_host import AgentExtensionHost
from embedagent_core.interaction import (
    UserInputRequest,
    UserInputResponse,
    build_user_input_request,
)
from embedagent_core.permissions import PermissionPolicy, PermissionRequest
from embedagent_core.policies import DenyWritePathPolicy, WritePathPolicy
from embedagent_core.session import Action, Observation, PendingInteraction, Session
from embedagent_core.session_journal import EventIntent
from embedagent_core.tool_contracts import (
    PreparedToolObservation,
    ToolError,
    ToolRuntimePort,
)
from embedagent_core.tool_execution import StreamingToolExecutor, partition_tool_actions

_LOG = logging.getLogger(__name__)


class InteractionFactory(object):
    """Build pending interaction values without committing session state."""

    def permission_request(
        self,
        action: Action,
        request: PermissionRequest,
        mode_name: str,
    ) -> InteractionSuspended:
        del mode_name
        permission_payload = {
            "tool_name": request.tool_name,
            "category": request.category,
            "reason": request.reason,
            "details": self._public_details(request.details),
        }
        pending = self._pending(
            action,
            "permission",
            request.tool_name,
            "permission",
            permission_payload,
            self._interaction_id(request.details),
        )
        pending.request_payload["permission"] = dict(permission_payload)
        return InteractionSuspended("", pending)

    def user_input_request(
        self,
        action: Action,
        request: UserInputRequest,
        mode_name: str,
    ) -> InteractionSuspended:
        del mode_name
        request_payload = {
            "tool_name": request.tool_name,
            "question": request.question,
            "options": [
                {"index": item.index, "text": item.text, "mode": item.mode}
                for item in request.options
            ],
            "details": self._public_details(request.details),
        }
        pending = self._pending(
            action,
            "user_input",
            request.tool_name,
            "request",
            request_payload,
            self._interaction_id(request.details),
        )
        pending.request_payload["request"] = dict(request_payload)
        return InteractionSuspended("", pending)

    def _pending(
        self,
        action: Action,
        kind: str,
        tool_name: str,
        request_key: str,
        request_payload: Dict[str, Any],
        interaction_id: str,
    ) -> PendingInteraction:
        kwargs = {"kind": kind, "tool_name": tool_name}
        if interaction_id:
            kwargs["interaction_id"] = interaction_id
        pending = PendingInteraction(**kwargs)
        pending.request_payload = {
            "action": {
                "name": action.name,
                "arguments": dict(action.arguments),
                "call_id": action.call_id,
            },
            "turn_id": "",
            "step_id": "",
            "interaction_id": pending.interaction_id,
            "kind": kind,
            "request_data": {request_key: dict(request_payload)},
        }
        return pending

    def _interaction_id(self, details: Dict[str, Any]) -> str:
        return str((details or {}).get("_interaction_id") or "").strip()

    def _public_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(details or {})
        payload.pop("_interaction_id", None)
        return payload


class AgentToolActionService(object):
    """Execute tool effects and return journal-ready typed results."""

    def __init__(
        self,
        tools: ToolRuntimePort,
        permission_policy: PermissionPolicy,
        extension_host: AgentExtensionHost,
        app_config_provider: Callable[[], Any],
        interaction_factory: InteractionFactory,
        write_path_policy: Optional[WritePathPolicy] = None,
    ) -> None:
        self.tools = tools
        self.permission_policy = permission_policy
        self.extension_host = extension_host
        self._app_config_provider = app_config_provider
        self._interaction_factory = interaction_factory
        self.write_path_policy = write_path_policy or DenyWritePathPolicy()

    def prepare(
        self,
        effect: PrepareToolBatchEffect,
        session: Session,
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]] = None,
        user_input_handler: Optional[
            Callable[[UserInputRequest], Optional[UserInputResponse]]
        ] = None,
    ):
        if not isinstance(effect, PrepareToolBatchEffect):
            raise TypeError("unsupported tool preparation effect")
        prepared = list(effect.prepared_prefix)
        immediate = list(effect.immediate_prefix)
        events = []  # type: List[EventIntent]
        start_index = max(0, int(effect.start_index or 0))

        for source_index in range(start_index, len(effect.actions)):
            outcome = self._prepare_action(
                effect,
                session,
                source_index,
                permission_handler,
                user_input_handler,
            )
            if isinstance(outcome, InteractionSuspended):
                pending_event = self._pending_interaction_event(session, outcome.pending)
                return replace(
                    outcome,
                    effect_id=effect.effect_id,
                    events=tuple(events) + outcome.events + (pending_event,),
                )
            if isinstance(outcome, PreparedToolInvocation):
                prepared.append(outcome)
                continue
            immediate.append(outcome)
            events.extend(self._inline_immediate_result_events(effect, session, outcome))

        return ToolBatchPrepared(
            effect.effect_id,
            invocations=tuple(prepared),
            immediate_results=tuple(immediate),
            events=tuple(events),
        )

    def _prepare_action(
        self,
        effect: PrepareToolBatchEffect,
        session: Session,
        source_index: int,
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]],
        user_input_handler: Optional[Callable[[UserInputRequest], Optional[UserInputResponse]]],
    ):
        original_frozen = effect.actions[source_index]
        action = original_frozen.to_action()
        if effect.provider_truncated:
            return self._immediate_result(
                source_index,
                original_frozen,
                original_frozen,
                self._failure_observation(
                    action.name,
                    "provider output ended before tool arguments were complete",
                    "truncated_tool_arguments",
                    True,
                    "provider_finish_reason",
                    "Retry the tool call with complete arguments.",
                    {"synthetic": True},
                ),
            )

        if action.name not in self.extension_host.allowed_tool_names(
            effect.mode_name,
            workflow_state=effect.workflow_state,
        ) and action.name not in ("ask_user", "propose_mode_switch"):
            return self._immediate_result(
                source_index,
                original_frozen,
                original_frozen,
                self._failure_observation(
                    action.name,
                    "Current mode %s does not allow tool %s." % (effect.mode_name, action.name),
                    "mode_tool_blocked",
                    False,
                    effect.mode_name,
                    "Use a tool allowed by the current mode.",
                ),
            )

        blocked_observation, runtime_action = self.prepare_extension_tool_call(
            session,
            action,
            effect.mode_name,
            effect.workflow_state,
        )
        if blocked_observation is not None:
            return self._immediate_result(
                source_index,
                original_frozen,
                original_frozen,
                blocked_observation,
            )
        try:
            effective_frozen = FrozenToolAction.from_action(runtime_action)
        except (TypeError, ValueError):
            return self._immediate_result(
                source_index,
                original_frozen,
                original_frozen,
                self._failure_observation(
                    action.name,
                    "before-tool hook returned non-JSON-safe arguments",
                    "invalid_arguments",
                    False,
                    "extension",
                    "Return JSON-safe tool arguments.",
                ),
            )

        decision = self.permission_policy.evaluate(
            runtime_action,
            remembered_categories=self.permission_policy.remembered_categories_for(
                session.session_id
            ),
        )
        if decision.outcome == "deny":
            return self._immediate_result(
                source_index,
                original_frozen,
                effective_frozen,
                self._failure_observation(
                    action.name,
                    decision.error or "Permission policy denied this operation.",
                    "permission_denied",
                    False,
                    "permission_policy",
                    "Update the permission policy or choose a lower-risk action.",
                    {
                        "permission_required": True,
                        "permission_decision": "deny",
                    },
                ),
            )
        if decision.request is not None:
            approved = (
                permission_handler(decision.request) if permission_handler is not None else None
            )
            if approved is None:
                return self._interaction_factory.permission_request(
                    runtime_action,
                    decision.request,
                    effect.mode_name,
                )
            if not approved:
                return self._immediate_result(
                    source_index,
                    original_frozen,
                    effective_frozen,
                    self._failure_observation(
                        action.name,
                        "Operation was not approved.",
                        "permission_denied",
                        False,
                        "user_confirmation",
                        "Wait for approval or choose a lower-risk action.",
                        {
                            "permission_required": True,
                            "permission_decision": "deny",
                        },
                    ),
                )

        invalid_path = self._validate_write_path(runtime_action, effect.mode_name)
        if invalid_path is not None:
            return self._immediate_result(
                source_index,
                original_frozen,
                effective_frozen,
                invalid_path,
            )

        if runtime_action.name in ("ask_user", "propose_mode_switch"):
            interactive = self._execute_interactive_action(
                runtime_action,
                effect.mode_name,
                user_input_handler,
            )
            if isinstance(interactive, InteractionSuspended):
                return interactive
            return self._immediate_result(
                source_index,
                original_frozen,
                effective_frozen,
                interactive,
            )

        catalog = self._catalog_snapshot(runtime_action.name)
        if not catalog:
            return self._immediate_result(
                source_index,
                original_frozen,
                effective_frozen,
                self._failure_observation(
                    action.name,
                    "Tool runtime catalog entry is unavailable.",
                    "tool_unavailable",
                    False,
                    "tool_catalog",
                    "Refresh tool registration before retrying.",
                ),
            )
        presentation = {
            "tool_label": str(catalog.get("user_label") or runtime_action.name),
            "progress_renderer_key": str(catalog.get("progress_renderer_key") or "default"),
            "result_renderer_key": str(catalog.get("result_renderer_key") or "default"),
            "supports_diff_preview": bool(catalog.get("supports_diff_preview")),
        }
        details = dict(getattr(decision, "details", {}) or {})
        return PreparedToolInvocation(
            invocation_id=_tool_invocation_id(effect.assistant_message_id, source_index),
            provider_call_id=action.call_id,
            source_index=source_index,
            original_action=original_frozen,
            effective_action=effective_frozen,
            permission_category=str(
                details.get("category") or catalog.get("permission_category") or "other"
            ),
            read_only=bool(catalog.get("read_only")),
            concurrency_safe=bool(catalog.get("concurrency_safe")),
            presentation_json=json.dumps(
                presentation,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            source_type=str(catalog.get("source_type") or ""),
            source_id=str(catalog.get("source_id") or ""),
            replay_safe=False,
        )

    def _catalog_snapshot(self, tool_name: str) -> Dict[str, Any]:
        lookup = getattr(self.tools, "catalog_entry", None)
        if not callable(lookup):
            lookup = getattr(self.tools, "tool_catalog_entry", None)
        if not callable(lookup):
            return {}
        entry = lookup(tool_name)
        if entry is None:
            return {}
        if isinstance(entry, dict):
            return deepcopy(dict(entry))
        to_dict = getattr(entry, "to_dict", None)
        if callable(to_dict):
            return deepcopy(dict(to_dict() or {}))
        return {}

    def _immediate_result(
        self,
        source_index: int,
        original_action: FrozenToolAction,
        effective_action: FrozenToolAction,
        observation: Observation,
    ) -> ImmediateToolResult:
        return ImmediateToolResult(
            source_index,
            original_action,
            effective_action,
            observation,
        )

    def _inline_immediate_result_events(
        self,
        effect: PrepareToolBatchEffect,
        session: Session,
        result: ImmediateToolResult,
    ) -> Tuple[EventIntent, ...]:
        original_action = result.original_action.to_action()
        turn_id, step_id = self._turn_step(session)
        finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        message_id = "m-tool-%s-%d" % (
            effect.assistant_message_id,
            result.source_index,
        )
        events = []
        data = result.observation.data if isinstance(result.observation.data, dict) else {}
        if data.get("error_kind") == "permission_denied":
            events.append(self._permission_rejection_event(session, original_action))
        events.append(
            EventIntent(
                "tool_result",
                {
                    "turn_id": turn_id,
                    "step_id": step_id,
                    "call_id": original_action.call_id,
                    "tool_name": original_action.name,
                    "arguments": dict(original_action.arguments),
                    "message_id": message_id,
                    "parent_message_id": effect.assistant_message_id,
                    "finished_at": finished_at,
                    "replaced_by_refs": [],
                    "observation": result.observation.to_dict(),
                },
            )
        )
        return tuple(events)

    def execute(
        self,
        effect: ExecuteToolBatchEffect,
        session: Session,
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]] = None,
        user_input_handler: Optional[
            Callable[[UserInputRequest], Optional[UserInputResponse]]
        ] = None,
        precomputed_observations: Optional[Tuple[Optional[Observation], ...]] = None,
        stop_event: Optional[threading.Event] = None,
        on_action_start: Optional[Callable[[Action], None]] = None,
        max_parallel_tools: int = 3,
    ):
        if not isinstance(effect, ExecuteToolBatchEffect):
            raise TypeError("unsupported tool effect")
        observations: List[Observation] = []
        events: List[EventIntent] = []
        commit_tokens: List[Any] = []
        precomputed = tuple(precomputed_observations or ())

        def append_result(action, precomputed_observation=None):
            result = self._execute_action(
                session,
                action,
                effect.mode_name,
                effect.workflow_state,
                permission_handler,
                user_input_handler,
                precomputed_observation=precomputed_observation,
                stop_event=stop_event,
            )
            if isinstance(result, InteractionSuspended):
                pending_event = self._pending_interaction_event(session, result.pending)
                return replace(
                    result,
                    effect_id=effect.effect_id,
                    events=tuple(events) + result.events + (pending_event,),
                    commit_tokens=tuple(commit_tokens),
                )
            observation, action_events, commit_token = result
            observations.append(observation)
            events.extend(action_events)
            if commit_token is not None:
                commit_tokens.append(commit_token)
            return None

        if precomputed:
            for index, action in enumerate(effect.actions):
                if on_action_start is not None:
                    on_action_start(action)
                suspension = append_result(
                    action,
                    precomputed[index] if index < len(precomputed) else None,
                )
                if suspension is not None:
                    return suspension
            return ToolBatchCompleted(
                effect.effect_id,
                observations=tuple(observations),
                events=tuple(events),
                commit_tokens=tuple(commit_tokens),
            )

        capability_lookup = getattr(self.tools, "tool_capabilities", None)
        if not callable(capability_lookup):

            def capability_lookup(tool_name):
                del tool_name
                return {}

        discard_remaining = False
        for batch in partition_tool_actions(list(effect.actions), capability_lookup):
            if discard_remaining:
                for action in batch.actions:
                    suspension = append_result(action, self._discarded_observation(action.name))
                    if suspension is not None:
                        return suspension
                continue
            if batch.parallel and len(batch.actions) > 1:
                executor = StreamingToolExecutor(
                    lambda action: self.execute_parallel_tool_action(
                        session,
                        action,
                        effect.mode_name,
                        effect.workflow_state,
                        stop_event,
                    ),
                    max_parallel_tools,
                    cancel_event=stop_event,
                )
                batch_interrupted = False
                batch_discarded = False
                for update in executor.run_batch(batch):
                    if update.phase == "start":
                        if on_action_start is not None:
                            on_action_start(update.action)
                        if self._stop_is_set(stop_event):
                            batch_interrupted = True
                            executor.discard()
                        continue
                    precomputed_observation = update.observation
                    if batch_interrupted or self._stop_is_set(stop_event):
                        batch_interrupted = True
                        if not self._is_discarded(precomputed_observation):
                            precomputed_observation = self._interrupted_observation(
                                update.action.name
                            )
                    suspension = append_result(update.action, precomputed_observation)
                    if suspension is not None:
                        return suspension
                    if self._is_discarded(observations[-1]):
                        batch_discarded = True
                if batch_discarded:
                    discard_remaining = True
                continue

            for action in batch.actions:
                if self._stop_is_set(stop_event):
                    suspension = append_result(
                        action,
                        self._discarded_observation(action.name),
                    )
                    discard_remaining = True
                else:
                    if on_action_start is not None:
                        on_action_start(action)
                    precomputed_observation = (
                        self._interrupted_observation(action.name)
                        if self._stop_is_set(stop_event)
                        else None
                    )
                    suspension = append_result(action, precomputed_observation)
                if suspension is not None:
                    return suspension
                if self._is_interrupted(observations[-1]):
                    discard_remaining = True
        return ToolBatchCompleted(
            effect.effect_id,
            observations=tuple(observations),
            events=tuple(events),
            commit_tokens=tuple(commit_tokens),
        )

    def finalize(self, commit_tokens: Tuple[Any, ...]) -> None:
        for commit_token in commit_tokens:
            self.tools.finalize_observation(commit_token)

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

    def _execute_action(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]],
        user_input_handler: Optional[Callable[[UserInputRequest], Optional[UserInputResponse]]],
        precomputed_observation: Optional[Observation] = None,
        stop_event: Optional[threading.Event] = None,
    ):
        runtime_action = action
        if action.name not in self.extension_host.allowed_tool_names(
            current_mode,
            workflow_state=workflow_state,
        ) and action.name not in ("ask_user", "propose_mode_switch"):
            return self._complete_action(
                session,
                action,
                self._failure_observation(
                    action.name,
                    "当前模式 %s 不允许调用工具 %s。" % (current_mode, action.name),
                    "mode_tool_blocked",
                    False,
                    current_mode,
                    "请改用当前模式允许的工具。",
                ),
            )
        if precomputed_observation is not None and not self.is_interactive_serial_skip(
            precomputed_observation
        ):
            if self.is_extension_blocked_observation(precomputed_observation):
                return self._complete_action(session, action, precomputed_observation)
            observation, workflow_intent = self._apply_extension_tool_result_patch(
                session,
                action,
                current_mode,
                workflow_state,
                precomputed_observation,
            )
            return self._complete_action(
                session,
                action,
                observation,
                workflow_intent=workflow_intent,
            )
        blocked_observation, runtime_action = self.prepare_extension_tool_call(
            session,
            action,
            current_mode,
            workflow_state,
        )
        if blocked_observation is not None:
            return self._complete_action(session, action, blocked_observation)
        if action.name in ("ask_user", "propose_mode_switch"):
            interactive = self._execute_interactive_action(
                runtime_action,
                current_mode,
                user_input_handler,
            )
            if isinstance(interactive, InteractionSuspended):
                return interactive
            return self._complete_action(session, action, interactive)
        observation = self.extension_host.handle_tool_call(
            session,
            tool_name=action.name,
            current_mode=current_mode,
            workflow_state=workflow_state,
        )
        if observation is not None:
            return self._complete_action(session, action, observation)
        decision = self.permission_policy.evaluate(
            runtime_action,
            remembered_categories=self.permission_policy.remembered_categories_for(
                session.session_id
            ),
        )
        if decision.outcome == "deny":
            rejection_event = self._permission_rejection_event(session, action)
            return self._complete_action(
                session,
                action,
                self._failure_observation(
                    action.name,
                    decision.error or "权限规则拒绝该操作。",
                    "permission_denied",
                    False,
                    "permission_policy",
                    "修改权限规则，或由用户手动放行后重试。",
                    {"permission_required": True, "permission_decision": "deny"},
                ),
                extra_events=(rejection_event,),
            )
        if decision.request is not None:
            approved = (
                permission_handler(decision.request) if permission_handler is not None else None
            )
            if approved is None:
                return self._interaction_factory.permission_request(
                    action,
                    decision.request,
                    current_mode,
                )
            if not approved:
                rejection_event = self._permission_rejection_event(session, action)
                return self._complete_action(
                    session,
                    action,
                    self._failure_observation(
                        action.name,
                        "操作未获批准，已跳过执行。",
                        "permission_denied",
                        False,
                        "user_confirmation",
                        "等待用户批准，或改为不需要该权限的方案。",
                        {"permission_required": True, "permission_decision": "deny"},
                    ),
                    extra_events=(rejection_event,),
                )
        invalid_path = self._validate_write_path(runtime_action, current_mode)
        if invalid_path is not None:
            return self._complete_action(session, action, invalid_path)
        observation = self.tools.execute_with_interrupt(
            runtime_action.name,
            runtime_action.arguments,
            stop_event,
        )
        observation, workflow_intent = self._apply_extension_tool_result_patch(
            session,
            runtime_action,
            current_mode,
            workflow_state,
            observation,
        )
        return self._complete_action(
            session,
            runtime_action,
            observation,
            workflow_intent=workflow_intent,
        )

    def _apply_extension_tool_result_patch(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
        observation: Observation,
    ) -> Tuple[Observation, Optional[EventIntent]]:
        patch = self.extension_host.apply_tool_result_patch(
            session,
            action,
            current_mode,
            workflow_state,
            observation,
        )
        intent = None
        if patch.workflow_patch is not None:
            intent = self._workflow_patch_intent(
                session,
                action,
                current_mode,
                workflow_state,
                patch.workflow_patch,
            )
        return (
            patch.observation if patch.observation is not None else observation,
            intent,
        )

    def _workflow_patch_operation_events(
        self,
        action: Action,
        intent: EventIntent,
    ) -> Tuple[EventIntent, ...]:
        payload = dict(intent.payload)
        turn_id = str(payload.get("turn_id") or "")
        step_id = str(payload.get("step_id") or "")
        operation_id = "workflow_patch:%s:%s" % (
            step_id or "session",
            action.call_id or "patch",
        )
        return (
            EventIntent(
                "operation_started",
                {
                    "operation_id": operation_id,
                    "kind": "workflow_patch",
                    "turn_id": turn_id,
                    "step_id": step_id,
                    "tool_call_id": action.call_id,
                    "parent_operation_id": "tool:%s" % action.call_id,
                    "metadata": {
                        "mode_name": str(payload.get("mode_name") or ""),
                        "workflow_state_name": str(payload.get("workflow_state_name") or ""),
                    },
                },
            ),
            intent,
            EventIntent(
                "operation_finished",
                {
                    "operation_id": operation_id,
                    "kind": "workflow_patch",
                    "turn_id": turn_id,
                    "step_id": step_id,
                    "tool_call_id": action.call_id,
                    "result": {
                        "workflow": dict(payload.get("workflow") or {}),
                        "metadata": dict(payload.get("metadata") or {}),
                    },
                },
            ),
        )

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
        turn_id, step_id = self._turn_step(session)
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

    def _execute_interactive_action(
        self,
        action: Action,
        current_mode: str,
        user_input_handler: Optional[Callable[[UserInputRequest], Optional[UserInputResponse]]],
    ):
        request = self._interactive_request(action)
        response = user_input_handler(request) if user_input_handler is not None else None
        if response is None:
            return self._interaction_factory.user_input_request(
                action,
                request,
                current_mode,
            )
        selected_mode = str(response.selected_mode or "").strip()
        if not selected_mode and action.name == "propose_mode_switch":
            selected_mode = str(request.details.get("target_mode") or "").strip()
        return Observation(
            request.tool_name,
            True,
            None,
            {
                "question": request.question,
                "answer": str(response.answer or "").strip(),
                "selected_index": response.selected_index,
                "selected_option_text": response.selected_option_text,
                "selected_mode": selected_mode,
                "mode_changed": bool(selected_mode and selected_mode != current_mode),
            },
        )

    def _interactive_request(self, action: Action) -> UserInputRequest:
        if action.name == "ask_user":
            return build_user_input_request(action.arguments)
        return UserInputRequest(
            "propose_mode_switch",
            str(action.arguments.get("reason") or ""),
            [],
            {"target_mode": str(action.arguments.get("target_mode") or "")},
        )

    def _complete_action(
        self,
        session: Session,
        action: Action,
        observation: Observation,
        workflow_intent: Optional[EventIntent] = None,
        extra_events: Tuple[EventIntent, ...] = (),
    ) -> Tuple[Observation, Tuple[EventIntent, ...], Any]:
        try:
            prepared = self.tools.materialize_observation(
                session.session_id,
                action,
                observation,
            )
        except (OSError, ValueError, TypeError) as exc:
            _LOG.warning(
                "tool result materialization failed for %s/%s; using inline fallback: %s",
                action.name,
                action.call_id,
                exc,
            )
            prepared = PreparedToolObservation(
                observation=self._fallback_committed_observation(observation, exc),
            )
        committed = prepared.observation
        replacements = [dict(item) for item in prepared.replacements if isinstance(item, dict)]
        replaced_by_refs = [
            str(item.get("stored_path") or "")
            for item in replacements
            if str(item.get("stored_path") or "")
        ]
        turn_id, step_id = self._turn_step(session)
        message_id = "m-" + uuid.uuid4().hex[:12]
        finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        events = list(extra_events)
        events.append(
            EventIntent(
                "tool_result",
                {
                    "turn_id": turn_id,
                    "step_id": step_id,
                    "call_id": action.call_id,
                    "tool_name": action.name,
                    "arguments": dict(action.arguments),
                    "message_id": message_id,
                    "parent_message_id": session.last_message_id(),
                    "finished_at": finished_at,
                    "replaced_by_refs": replaced_by_refs,
                    "observation": committed.to_dict(),
                },
            )
        )
        if replacements:
            events.append(
                EventIntent(
                    "content_replacement",
                    {
                        "message_id": message_id,
                        "tool_call_id": action.call_id,
                        "tool_name": action.name,
                        "replacements": replacements,
                    },
                )
            )
        if workflow_intent is not None:
            events.extend(self._workflow_patch_operation_events(action, workflow_intent))
        events.append(self._tool_operation_event(action, committed, turn_id, step_id, finished_at))
        return committed, tuple(events), prepared.commit_token

    def _tool_operation_event(
        self,
        action: Action,
        observation: Observation,
        turn_id: str,
        step_id: str,
        finished_at: str,
    ) -> EventIntent:
        error_kind = (
            str(observation.data.get("error_kind") or "")
            if isinstance(observation.data, dict)
            else ""
        )
        interrupted = error_kind in ("interrupted", "discarded")
        return EventIntent(
            "operation_interrupted" if interrupted else "operation_finished",
            {
                "operation_id": "tool:%s" % action.call_id,
                "kind": "tool_call",
                "turn_id": turn_id,
                "step_id": step_id,
                "tool_call_id": action.call_id,
                "finished_at": finished_at,
                "reason": error_kind if interrupted else "",
                "result": {
                    "success": observation.success,
                    "error": observation.error,
                    "error_kind": error_kind,
                },
            },
        )

    def _pending_interaction_event(
        self,
        session: Session,
        pending: PendingInteraction,
    ) -> EventIntent:
        turn_id, step_id = self._turn_step(session)
        request_payload = deepcopy(dict(pending.request_payload or {}))
        request_payload["turn_id"] = turn_id
        request_payload["step_id"] = step_id
        return EventIntent(
            "pending_interaction",
            {
                "turn_id": turn_id,
                "step_id": step_id,
                "interaction_id": pending.interaction_id,
                "kind": pending.kind,
                "tool_name": pending.tool_name,
                "request_payload": request_payload,
                "created_at": pending.created_at,
            },
        )

    def _permission_rejection_event(
        self,
        session: Session,
        action: Action,
    ) -> EventIntent:
        turn_id, step_id = self._turn_step(session)
        return EventIntent(
            "interaction",
            {
                "role": "interaction",
                "tool_name": action.name,
                "call_id": action.call_id,
                "message_id": "m-reject-" + uuid.uuid4().hex[:12],
                "parent_message_id": session.last_message_id(),
                "turn_id": turn_id,
                "step_id": step_id,
                "status": "rejected",
                "reason": "permission_denied",
            },
        )

    def _turn_step(self, session: Session) -> Tuple[str, str]:
        turn_id = session.turns[-1].turn_id if session.turns else ""
        step = session.current_step()
        return turn_id, step.step_id if step is not None else ""

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

    def _failure_observation(
        self,
        tool_name: str,
        error: str,
        error_kind: str,
        retryable: bool,
        blocked_by: str,
        suggested_next_step: str,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> Observation:
        data = {
            "error_kind": error_kind,
            "retryable": retryable,
            "blocked_by": blocked_by,
            "suggested_next_step": suggested_next_step,
        }
        if extra_data:
            data.update(extra_data)
        return Observation(tool_name, False, error, data)

    def _fallback_committed_observation(
        self,
        observation: Observation,
        exc: Exception,
    ) -> Observation:
        data = deepcopy(observation.data)
        if isinstance(data, dict):
            warnings = data.get("tool_result_commit_warnings")
            if not isinstance(warnings, list):
                warnings = []
            warnings.append({"error": str(exc)})
            data["tool_result_commit_warnings"] = warnings[:8]
        return Observation(
            observation.tool_name,
            observation.success,
            observation.error,
            data,
        )

    def _stop_is_set(self, stop_event: Optional[threading.Event]) -> bool:
        is_set = getattr(stop_event, "is_set", None)
        return bool(callable(is_set) and is_set())

    def _interrupted_observation(self, tool_name: str) -> Observation:
        return Observation(
            tool_name,
            False,
            "tool execution interrupted",
            {"error_kind": "interrupted", "retryable": False},
        )

    def _discarded_observation(self, tool_name: str) -> Observation:
        return Observation(
            tool_name,
            False,
            "tool execution discarded",
            {"error_kind": "discarded", "retryable": False},
        )

    def _is_interrupted(self, observation: Optional[Observation]) -> bool:
        if observation is None or not isinstance(observation.data, dict):
            return False
        return str(observation.data.get("error_kind") or "") == "interrupted"

    def _is_discarded(self, observation: Optional[Observation]) -> bool:
        if observation is None or not isinstance(observation.data, dict):
            return False
        return str(observation.data.get("error_kind") or "") == "discarded"
