from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from embedagent.session import Action, Observation


@dataclass
class ToolBatch:
    parallel: bool
    actions: List[Action] = field(default_factory=list)


@dataclass
class ToolExecutionUpdate:
    action: Action
    observation: Optional[Observation] = None
    phase: str = "result"
    progress: Optional[Dict[str, Any]] = None


class StreamingToolExecutor(object):
    def __init__(
        self,
        execute_action: Callable[[Action], Observation],
        max_parallel: int = 3,
    ) -> None:
        self.execute_action = execute_action
        self.max_parallel = max(1, int(max_parallel or 1))
        self._discarded = False
        self._lock = threading.Lock()

    def discard(self) -> None:
        with self._lock:
            self._discarded = True

    def run_batch(self, batch: ToolBatch) -> List[ToolExecutionUpdate]:
        if not batch.actions:
            return []
        if not batch.parallel or len(batch.actions) == 1:
            return self._run_serial(batch.actions)
        return self._run_parallel(batch.actions)

    def _run_serial(self, actions: List[Action]) -> List[ToolExecutionUpdate]:
        updates = []
        for action in actions:
            if self._discarded:
                updates.append(
                    ToolExecutionUpdate(
                        action=action,
                        observation=Observation(
                            tool_name=action.name,
                            success=False,
                            error="tool execution discarded",
                            data={"error_kind": "discarded", "retryable": False},
                        ),
                    )
                )
                continue
            updates.append(ToolExecutionUpdate(action=action, phase="start"))
            updates.append(
                ToolExecutionUpdate(
                    action=action,
                    observation=self.execute_action(action),
                    phase="result",
                )
            )
        return updates

    def _run_parallel(self, actions: List[Action]) -> List[ToolExecutionUpdate]:
        updates = [ToolExecutionUpdate(action=action, phase="start") for action in actions]
        results = {}  # type: Dict[str, Observation]
        sibling_error = threading.Event()
        semaphore = threading.Semaphore(self.max_parallel)
        threads = []

        def runner(action: Action) -> None:
            with semaphore:
                if self._discarded or sibling_error.is_set():
                    results[action.call_id] = Observation(
                        tool_name=action.name,
                        success=False,
                        error="tool execution discarded",
                        data={"error_kind": "discarded", "retryable": False},
                    )
                    return
                observation = self.execute_action(action)
                results[action.call_id] = observation
                if not observation.success:
                    sibling_error.set()

        for action in actions:
            thread = threading.Thread(target=runner, args=(action,))
            thread.daemon = True
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        for action in actions:
            updates.append(
                ToolExecutionUpdate(
                    action=action,
                    observation=results.get(action.call_id),
                    phase="result",
                )
            )
        return updates


def partition_tool_actions(
    actions: List[Action],
    capability_lookup: Callable[[str], Dict[str, Any]],
) -> List[ToolBatch]:
    batches = []
    current = None  # type: Optional[ToolBatch]
    for action in actions:
        capabilities = capability_lookup(action.name) or {}
        is_parallel = bool(capabilities.get("read_only")) and bool(capabilities.get("concurrency_safe"))
        if current is None or current.parallel != is_parallel:
            current = ToolBatch(parallel=is_parallel, actions=[action])
            batches.append(current)
        else:
            current.actions.append(action)
    return batches
