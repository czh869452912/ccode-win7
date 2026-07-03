from __future__ import annotations

from embedagent_core.session import (
    Action,
    InteractionCheckpoint,
    LoopTransition,
    PendingInteraction,
    Session,
)
from embedagent_core.agent_lifecycle import AgentLifecycleJournal


class AgentTurnFrame(object):
    """Lifecycle frame for one user, command, or resume turn."""

    def __init__(
        self,
        lifecycle: AgentLifecycleJournal,
        session: Session,
        turn_id: str,
        current_mode: str,
        workflow_state: str,
    ) -> None:
        self._lifecycle = lifecycle
        self._session = session
        self.turn_id = turn_id
        self.current_mode = current_mode
        self.workflow_state = workflow_state

    def finish(self, transition: LoopTransition) -> None:
        self._lifecycle.emit_turn_finished(
            self._session,
            self.turn_id,
            transition,
            self.current_mode,
            self.workflow_state,
        )

    def interrupt(self, reason: str, error: str = "") -> None:
        self._lifecycle.emit_turn_interrupted(
            self._session,
            self.turn_id,
            reason,
            self.current_mode,
            self.workflow_state,
            error=error,
        )


class AgentKernel(object):
    """Internal lifecycle kernel behind the QueryEngine session facade."""

    def __init__(self, lifecycle: AgentLifecycleJournal) -> None:
        self.lifecycle = lifecycle

    def begin_turn(
        self,
        session: Session,
        turn_id: str,
        current_mode: str,
        workflow_state: str,
        source: str,
    ) -> AgentTurnFrame:
        self.lifecycle.emit_turn_started(
            session,
            turn_id,
            current_mode,
            workflow_state,
            source,
        )
        return AgentTurnFrame(
            lifecycle=self.lifecycle,
            session=session,
            turn_id=turn_id,
            current_mode=current_mode,
            workflow_state=workflow_state,
        )

    def interaction_checkpoint_payload(
        self,
        session: Session,
        action: Action,
        pending: PendingInteraction,
        request_data: dict = None,
    ) -> dict:
        turn_id = session.turns[-1].turn_id if session.turns else ""
        step = session.current_step()
        step_id = step.step_id if step is not None else ""
        return InteractionCheckpoint(
            action={
                "name": action.name,
                "arguments": dict(action.arguments),
                "call_id": action.call_id,
            },
            turn_id=turn_id,
            step_id=step_id,
            interaction_id=pending.interaction_id,
            kind=pending.kind,
            request_data=dict(request_data or {}),
        ).to_dict()

    def record_pending_permission(
        self,
        session: Session,
        action: Action,
        permission_payload: dict,
        current_mode: str,
        interaction_id: str = "",
    ):
        pending_kwargs = {
            "kind": "permission",
            "tool_name": action.name,
        }
        if interaction_id:
            pending_kwargs["interaction_id"] = interaction_id
        pending = PendingInteraction(**pending_kwargs)
        pending.request_payload = self.interaction_checkpoint_payload(
            session,
            action,
            pending,
            request_data={"permission": permission_payload},
        )
        pending.request_payload["permission"] = dict(permission_payload)
        transition = LoopTransition(
            "permission_wait",
            str(permission_payload.get("reason") or ""),
            pending,
            current_mode,
        )
        self.lifecycle.record_transition(session, transition)
        return pending, transition

    def record_pending_user_input(
        self,
        session: Session,
        action: Action,
        tool_name: str,
        request_payload: dict,
        message: str,
        current_mode: str,
        interaction_id: str = "",
    ):
        pending_kwargs = {
            "kind": "user_input",
            "tool_name": tool_name,
        }
        if interaction_id:
            pending_kwargs["interaction_id"] = interaction_id
        pending = PendingInteraction(**pending_kwargs)
        pending.request_payload = self.interaction_checkpoint_payload(
            session,
            action,
            pending,
            request_data={"request": request_payload},
        )
        pending.request_payload["request"] = dict(request_payload)
        transition = LoopTransition(
            "user_input_wait",
            message,
            pending,
            current_mode,
        )
        self.lifecycle.record_transition(session, transition)
        return pending, transition

    def resolve_pending_interaction(
        self,
        session: Session,
        pending: PendingInteraction,
        resolution: dict,
    ) -> None:
        turn_id = session.turns[-1].turn_id if session.turns else ""
        step_id = session.current_step().step_id if session.current_step() is not None else ""
        self.lifecycle.append_transcript_event(
            session,
            "pending_resolution",
            {
                "turn_id": turn_id,
                "step_id": step_id,
                "interaction_id": pending.interaction_id,
                "kind": pending.kind,
                "tool_name": pending.tool_name,
                "resolution_payload": dict(resolution or {}),
            },
        )
        self.lifecycle.emit_pending_finished(
            session,
            pending,
            turn_id,
            step_id,
            "resolved",
        )
        session.resolve_pending_interaction(resolution)
