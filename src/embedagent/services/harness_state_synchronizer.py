from __future__ import annotations

import logging
from typing import Any, List, Optional

from embedagent.harness import task_store
from embedagent.harness.runner import HarnessRunner
from embedagent.session_runtime import ManagedSession

logger = logging.getLogger(__name__)


class HarnessStateSynchronizer(object):
    """Task graph refresh and harness state updates."""

    def __init__(
        self,
        harness_runner: HarnessRunner,
        workspace: str,
    ) -> None:
        self.harness_runner = harness_runner
        self.workspace = workspace

    def refresh_task_graph(
        self,
        session: ManagedSession,
        observations: Optional[List[Any]] = None,
    ) -> None:
        discipline_override = (
            "full_spec_tdd"
            if session.current_mode == "build" and session.workflow_state == "plan"
            else None
        )
        graph = self.harness_runner.update_task_graph(
            session.session,
            session.current_mode,
            observations=observations or [],
            discipline_override=discipline_override,
        )
        context = self.harness_runner.describe_mode(
            session.current_mode,
            discipline_override=discipline_override,
            current_phase=str(getattr(graph, "current_phase", "") or ""),
            observations=[],
        )
        if context is None:
            task_store.save_task_snapshot(
                self.workspace,
                session.session.session_id,
                session.current_mode,
                session.workflow_state,
                "",
                "",
                "",
                [],
            )
            return
        current_phase = str(getattr(graph, "current_phase", "") or context.current_phase or "")
        discipline_profile = str(getattr(graph, "discipline", "") or context.discipline_label or "")
        task_summary = str(
            graph.render_summary() if graph is not None else (context.task_summary or "")
        )
        task_items = list(
            graph.to_items() if graph is not None else (getattr(context, "task_items", []) or [])
        )
        task_store.save_task_snapshot(
            self.workspace,
            session.session.session_id,
            session.current_mode,
            session.workflow_state,
            discipline_profile,
            current_phase,
            task_summary,
            task_items,
        )

    def sync_mode(self, session: ManagedSession, mode: str) -> None:
        session.current_mode = mode

    def build_mode_context(self, session: ManagedSession) -> Optional[Any]:
        graph = getattr(session.session, "task_graph", None)
        return self.harness_runner.describe_mode(
            session.current_mode,
            discipline_override=(
                str(getattr(graph, "discipline", "") or "") if graph is not None else None
            ),
            current_phase=(
                str(getattr(graph, "current_phase", "") or "") if graph is not None else ""
            ),
            observations=[],
        )
