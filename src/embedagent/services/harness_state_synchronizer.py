from __future__ import annotations

import logging
from typing import Any, List, Optional

from embedagent.harness import task_store
from embedagent.harness.extension import CHarnessWorkflowExtension
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
        self.harness_workflow = CHarnessWorkflowExtension(harness_runner=harness_runner)
        self.workspace = workspace

    def refresh_task_graph(
        self,
        session: ManagedSession,
        observations: Optional[List[Any]] = None,
    ) -> None:
        self.harness_workflow.refresh_managed_session(
            session,
            self.workspace,
            observations=observations or [],
            task_store_module=task_store,
        )

    def sync_mode(self, session: ManagedSession, mode: str) -> None:
        session.current_mode = mode

    def build_mode_context(
        self,
        session: ManagedSession,
        mode: Optional[str] = None,
    ) -> Optional[Any]:
        current_mode = str(mode or session.current_mode or "")
        return self.harness_workflow.build_mode_context(
            session.session,
            current_mode,
            workflow_state=session.workflow_state,
        )
