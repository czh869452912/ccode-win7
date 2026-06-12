from __future__ import annotations

from typing import Any, Callable


class AgentLoop(object):
    """Thin turn-loop boundary around the session-scoped runner."""

    def __init__(self, runner: Callable[..., Any]) -> None:
        self._runner = runner

    def run(self, **kwargs: Any) -> Any:
        return self._runner(**kwargs)
