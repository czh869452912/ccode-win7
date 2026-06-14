from __future__ import annotations

from embedagent.agent_lifecycle import AgentLifecycleJournal
from embedagent.session import LoopTransition, Session


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
