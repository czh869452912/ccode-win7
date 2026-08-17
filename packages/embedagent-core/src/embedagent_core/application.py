from __future__ import annotations

from typing import Any


class ApplicationRegistrar(object):
    """Focused registration sink for one selected application plugin."""

    def __init__(self, extension_host: Any, shell_registry: Any) -> None:
        self._extension_host = extension_host
        self._shell_registry = shell_registry
        self._disposers = []  # type: List[Any]
        self._source_ids = set()  # type: Set[str]

    def _source(self, source_id: str) -> str:
        normalized = str(source_id or "").strip()
        if not normalized:
            raise ValueError("application source id must be nonempty")
        self._source_ids.add(normalized)
        return normalized

    def _append_disposer(self, disposer: Any, source_id: str) -> None:
        if not callable(disposer):
            raise TypeError("application registration did not return a disposer")
        self._disposers.append((source_id, disposer))

    def add_extension(self, extension: Any, source_id: str) -> None:
        source = self._source(source_id)
        disposer = self._extension_host.register(extension, source)
        self._append_disposer(disposer, source)

    def add_prompt_provider(self, provider: Any, source_id: str) -> None:
        source = self._source(source_id)
        disposer = self._extension_host.register_prompt_provider(provider, source)
        self._append_disposer(disposer, source)

    def add_context_provider(self, provider: Any, source_id: str) -> None:
        source = self._source(source_id)
        disposer = self._extension_host.register_context_provider(provider, source)
        self._append_disposer(disposer, source)

    def add_shell_contribution(self, contribution: Any, source_id: str) -> None:
        source = self._source(source_id)
        disposer = self._shell_registry.register(contribution, source)
        self._append_disposer(disposer, source)

    def dispose(self) -> None:
        while self._disposers:
            source_id, disposer = self._disposers.pop()
            try:
                disposer()
            finally:
                self._source_ids.discard(source_id)
