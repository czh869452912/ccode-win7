from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from embedagent.session import (
    Action,
    ContextAssemblyResult,
    LoopTransition,
    PendingInteraction,
    Session,
)

_LOG = logging.getLogger(__name__)


class AgentLifecycleJournal(object):
    """Durable lifecycle journal for agent operations and save points."""

    def __init__(
        self,
        append_event: Callable[[Session, str, Dict[str, Any], int], None],
        session_guard: Callable[[], Any],
    ) -> None:
        self._append_event = append_event
        self._session_guard = session_guard

    def append_transcript_event(
        self,
        session: Session,
        event_type: str,
        payload: Dict[str, Any],
        schema_version: int = 1,
    ) -> None:
        self._append_event(session, event_type, payload, schema_version)

    def emit_lifecycle_event(
        self, session: Session, event_type: str, payload: Dict[str, Any]
    ) -> None:
        try:
            self.append_transcript_event(session, event_type, payload, schema_version=2)
        except (OSError, ValueError, TypeError) as exc:  # pragma: no cover
            _LOG.warning("lifecycle event emission failed (%s): %s", event_type, exc)

    def emit_operation_started(
        self,
        session: Session,
        operation_id: str,
        kind: str,
        turn_id: str = "",
        step_id: str = "",
        tool_call_id: str = "",
        parent_operation_id: str = "",
        retryable: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.emit_lifecycle_event(
            session,
            "operation_started",
            {
                "operation_id": operation_id,
                "kind": kind,
                "turn_id": turn_id,
                "step_id": step_id,
                "tool_call_id": tool_call_id,
                "parent_operation_id": parent_operation_id,
                "retryable": bool(retryable),
                "metadata": dict(metadata or {}),
            },
        )

    def emit_operation_finished(
        self,
        session: Session,
        operation_id: str,
        kind: str = "",
        turn_id: str = "",
        step_id: str = "",
        tool_call_id: str = "",
        finished_at: str = "",
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.emit_lifecycle_event(
            session,
            "operation_finished",
            {
                "operation_id": operation_id,
                "kind": kind,
                "turn_id": turn_id,
                "step_id": step_id,
                "tool_call_id": tool_call_id,
                "finished_at": finished_at,
                "result": dict(result or {}),
            },
        )

    def emit_operation_interrupted(
        self,
        session: Session,
        operation_id: str,
        kind: str = "",
        turn_id: str = "",
        step_id: str = "",
        tool_call_id: str = "",
        reason: str = "",
        finished_at: str = "",
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.emit_lifecycle_event(
            session,
            "operation_interrupted",
            {
                "operation_id": operation_id,
                "kind": kind,
                "turn_id": turn_id,
                "step_id": step_id,
                "tool_call_id": tool_call_id,
                "reason": reason or "operation_interrupted",
                "finished_at": finished_at,
                "retryable": False,
                "result": dict(result or {}),
            },
        )

    def turn_id(self, session: Session) -> str:
        return session.turns[-1].turn_id if session.turns else ""

    def context_operation_metadata(
        self, mode_name: str, workflow_state: str, force_compact: bool
    ) -> Dict[str, Any]:
        return {
            "mode_name": mode_name,
            "workflow_state": workflow_state,
            "force_compact": bool(force_compact),
        }

    def context_operation_result(self, assembly: ContextAssemblyResult) -> Dict[str, Any]:
        return {
            "approx_tokens": assembly.approx_tokens,
            "used_chars": assembly.used_chars,
            "compacted": assembly.compacted,
            "summarized_turns": assembly.summarized_turns,
            "recent_turns": assembly.recent_turns,
            "pipeline_steps": list(assembly.pipeline_steps),
            "replacements": len(assembly.replacements),
            "context_plan": self._context_plan_payload(assembly),
        }

    def context_snapshot_payload(
        self, current_mode: str, assembly: ContextAssemblyResult
    ) -> Dict[str, Any]:
        return {
            "mode_name": current_mode,
            "pipeline_steps": list(assembly.pipeline_steps),
            "analysis": dict(assembly.analysis),
            "approx_tokens": assembly.approx_tokens,
            "summary_message": assembly.summary_message,
            "context_plan": self._context_plan_payload(assembly),
        }

    def _context_plan_payload(self, assembly: ContextAssemblyResult) -> Dict[str, Any]:
        plan = getattr(assembly, "plan", None)
        if plan is None:
            return {}
        to_metadata = getattr(plan, "to_boundary_metadata", None)
        if callable(to_metadata):
            return dict(to_metadata())
        return {}

    def workflow_patch_snapshot(self, session: Session) -> Dict[str, Dict[str, Any]]:
        workflow_root = getattr(session, "workflow_state", {}) or {}
        workflow = {}
        metadata = {}
        if isinstance(workflow_root, dict):
            workflow = dict(workflow_root.get("workflow") or {})
            extensions = workflow_root.get("extensions") or {}
            if isinstance(extensions, dict):
                metadata = dict(extensions.get("last_workflow_patch") or {})
        return {"workflow": workflow, "metadata": metadata}

    def workflow_patch_payload(
        self,
        session: Session,
        current_mode: str,
        workflow_state: str,
        action: Action,
    ) -> Dict[str, Any]:
        snapshot = self.workflow_patch_snapshot(session)
        turn_id = session.turns[-1].turn_id if session.turns else ""
        step_id = session.current_step().step_id if session.current_step() is not None else ""
        return {
            "turn_id": turn_id,
            "step_id": step_id,
            "tool_call_id": action.call_id,
            "mode_name": current_mode,
            "workflow_state_name": workflow_state,
            "workflow": dict(snapshot.get("workflow") or {}),
            "metadata": dict(snapshot.get("metadata") or {}),
        }

    def workflow_patch_changed(
        self,
        before: Dict[str, Dict[str, Any]],
        payload: Dict[str, Any],
    ) -> bool:
        before_workflow = dict((before or {}).get("workflow") or {})
        before_metadata = dict((before or {}).get("metadata") or {})
        workflow = dict(payload.get("workflow") or {})
        metadata = dict(payload.get("metadata") or {})
        return bool(workflow or metadata) and (
            workflow != before_workflow or metadata != before_metadata
        )

    def persist_workflow_patch(self, session: Session, payload: Dict[str, Any]) -> None:
        turn_id = str(payload.get("turn_id") or "")
        step_id = str(payload.get("step_id") or "")
        tool_call_id = str(payload.get("tool_call_id") or "")
        operation_id = "workflow_patch:%s:%s" % (step_id or "session", tool_call_id or "patch")
        self.emit_operation_started(
            session,
            operation_id,
            "workflow_patch",
            turn_id=turn_id,
            step_id=step_id,
            tool_call_id=tool_call_id,
            parent_operation_id="tool:%s" % tool_call_id if tool_call_id else "",
            metadata={
                "mode_name": str(payload.get("mode_name") or ""),
                "workflow_state_name": str(payload.get("workflow_state_name") or ""),
            },
        )
        self.append_transcript_event(session, "workflow_patch", dict(payload), schema_version=2)
        self.emit_operation_finished(
            session,
            operation_id,
            kind="workflow_patch",
            turn_id=turn_id,
            step_id=step_id,
            tool_call_id=tool_call_id,
            result={
                "workflow": dict(payload.get("workflow") or {}),
                "metadata": dict(payload.get("metadata") or {}),
            },
        )

    def capture_workflow_patch_if_changed(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
        before: Dict[str, Dict[str, Any]],
    ) -> None:
        payload = self.workflow_patch_payload(session, current_mode, workflow_state, action)
        if self.workflow_patch_changed(before, payload):
            self.persist_workflow_patch(session, payload)

    def emit_turn_started(
        self,
        session: Session,
        turn_id: str,
        current_mode: str,
        workflow_state: str,
        source: str,
    ) -> None:
        self.emit_operation_started(
            session,
            "turn:%s" % turn_id,
            "turn",
            turn_id=turn_id,
            metadata={
                "mode_name": current_mode,
                "workflow_state": workflow_state,
                "source": source,
            },
        )

    def emit_turn_finished(
        self,
        session: Session,
        turn_id: str,
        transition: LoopTransition,
        current_mode: str,
        workflow_state: str,
    ) -> None:
        self.emit_operation_finished(
            session,
            "turn:%s" % turn_id,
            kind="turn",
            turn_id=turn_id,
            result={
                "transition_reason": transition.reason,
                "message": transition.message,
                "next_mode": transition.next_mode or current_mode,
                "workflow_state": workflow_state,
                "turns_used": transition.turns_used,
            },
        )

    def emit_turn_interrupted(
        self,
        session: Session,
        turn_id: str,
        reason: str,
        current_mode: str,
        workflow_state: str,
        error: str = "",
    ) -> None:
        self.emit_operation_interrupted(
            session,
            "turn:%s" % turn_id,
            kind="turn",
            turn_id=turn_id,
            reason=reason,
            result={
                "mode_name": current_mode,
                "workflow_state": workflow_state,
                "error": error,
            },
        )

    def pending_operation_metadata(self, pending: PendingInteraction) -> Dict[str, Any]:
        metadata = {
            "kind": pending.kind,
            "tool_name": pending.tool_name,
            "interaction_id": pending.interaction_id,
        }
        request_payload = dict(pending.request_payload or {})
        if "permission" in request_payload and isinstance(request_payload.get("permission"), dict):
            permission_payload = dict(request_payload.get("permission") or {})
            metadata["category"] = str(permission_payload.get("category") or "")
            metadata["reason"] = str(permission_payload.get("reason") or "")
        if "request" in request_payload and isinstance(request_payload.get("request"), dict):
            request = dict(request_payload.get("request") or {})
            metadata["question"] = str(request.get("question") or "")
        return metadata

    def emit_pending_started(
        self,
        session: Session,
        pending: PendingInteraction,
        turn_id: str,
        step_id: str,
    ) -> None:
        if not pending.interaction_id:
            return
        self.emit_operation_started(
            session,
            "pending:%s" % pending.interaction_id,
            "pending_interaction",
            turn_id=turn_id,
            step_id=step_id,
            parent_operation_id="step:%s" % step_id if step_id else "",
            metadata=self.pending_operation_metadata(pending),
        )

    def emit_pending_finished(
        self,
        session: Session,
        pending: PendingInteraction,
        turn_id: str,
        step_id: str,
        resolution_status: str,
    ) -> None:
        if not pending.interaction_id:
            return
        self.emit_operation_finished(
            session,
            "pending:%s" % pending.interaction_id,
            kind="pending_interaction",
            turn_id=turn_id,
            step_id=step_id,
            result={
                "resolution_status": resolution_status,
                "kind": pending.kind,
                "tool_name": pending.tool_name,
            },
        )

    def emit_step_finished(
        self,
        session: Session,
        turn_id: str,
        step_id: str,
        reason: str,
        message: str = "",
        turns_used: int = 0,
    ) -> None:
        if not step_id:
            return
        self.emit_operation_finished(
            session,
            "step:%s" % step_id,
            kind="agent_step",
            turn_id=turn_id,
            step_id=step_id,
            result={
                "reason": reason,
                "message": message,
                "turns_used": turns_used,
            },
        )

    def emit_step_interrupted(
        self,
        session: Session,
        turn_id: str,
        step_id: str,
        reason: str,
        message: str = "",
        turns_used: int = 0,
    ) -> None:
        if not step_id:
            return
        self.emit_operation_interrupted(
            session,
            "step:%s" % step_id,
            kind="agent_step",
            turn_id=turn_id,
            step_id=step_id,
            reason=reason,
            result={
                "reason": reason,
                "message": message,
                "turns_used": turns_used,
            },
        )

    def record_transition(self, session: Session, transition: LoopTransition) -> None:
        with self._session_guard():
            step_id = session.current_step().step_id if session.current_step() is not None else ""
            turn_id = self.turn_id(session)
            savepoint_index = len(session.turns[-1].transitions) + 1 if session.turns else 1
            savepoint_id = "savepoint:%s:%s:%s" % (
                turn_id or "session",
                step_id or "turn",
                savepoint_index,
            )
            savepoint_result = {
                "reason": transition.reason,
                "message": transition.message,
                "next_mode": transition.next_mode,
                "turns_used": transition.turns_used,
                "metadata": dict(transition.metadata),
            }
            if transition.pending_interaction is not None:
                self.append_transcript_event(
                    session,
                    "pending_interaction",
                    {
                        "turn_id": turn_id,
                        "step_id": step_id,
                        "kind": transition.pending_interaction.kind,
                        "tool_name": transition.pending_interaction.tool_name,
                        "interaction_id": transition.pending_interaction.interaction_id,
                        "request_payload": dict(transition.pending_interaction.request_payload),
                    },
                )
                self.emit_pending_started(
                    session,
                    transition.pending_interaction,
                    turn_id,
                    step_id,
                )
            self.emit_operation_started(
                session,
                savepoint_id,
                "save_point",
                turn_id=turn_id,
                step_id=step_id,
                parent_operation_id="step:%s" % step_id if step_id else "",
                metadata={"transition_reason": transition.reason},
            )
            self.append_transcript_event(
                session,
                "loop_transition",
                {
                    "turn_id": turn_id,
                    "step_id": step_id,
                    "reason": transition.reason,
                    "message": transition.message,
                    "next_mode": transition.next_mode,
                    "turns_used": transition.turns_used,
                    "metadata": dict(transition.metadata),
                },
            )
            self.emit_operation_finished(
                session,
                savepoint_id,
                kind="save_point",
                turn_id=turn_id,
                step_id=step_id,
                result=savepoint_result,
            )
            finished_step_reasons = (
                "completed",
                "mode_changed",
                "permission_wait",
                "user_input_wait",
            )
            interrupted_step_reasons = ("aborted", "guard_stop", "max_turns")
            if step_id and transition.reason in (finished_step_reasons + interrupted_step_reasons):
                if transition.reason in finished_step_reasons:
                    self.emit_step_finished(
                        session,
                        turn_id,
                        step_id,
                        transition.reason,
                        message=transition.message,
                        turns_used=transition.turns_used,
                    )
                else:
                    self.emit_step_interrupted(
                        session,
                        turn_id,
                        step_id,
                        transition.reason,
                        message=transition.message,
                        turns_used=transition.turns_used,
                    )
            session.record_transition(transition)
