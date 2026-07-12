from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


class SlashCommandService(object):
    def __init__(self, handlers: Dict[str, Callable[..., Any]]) -> None:
        self._handlers = dict(handlers or {})

    def handler_for(self, name: str) -> Optional[Callable[..., Any]]:
        return self._handlers.get(str(name or ""))

    def names(self) -> List[str]:
        return sorted(self._handlers.keys())
