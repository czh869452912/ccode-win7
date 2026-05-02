from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional


class DIContainer(object):
    """Manual dependency injection container.

    Supports singleton (default) and factory (fresh=True) resolution modes.
    Thread-safe via RLock.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._singletons: Dict[str, Any] = {}

    def register_factory(self, key: str, factory: Callable[[], Any]) -> None:
        with self._lock:
            self._factories[key] = factory
            self._singletons.pop(key, None)

    def resolve(self, key: str, fresh: bool = False) -> Any:
        with self._lock:
            factory = self._factories.get(key)
            if factory is None:
                raise KeyError("No factory registered for key: %s" % key)
            if fresh:
                return factory()
            if key not in self._singletons:
                self._singletons[key] = factory()
            return self._singletons[key]

    def clear(self) -> None:
        with self._lock:
            self._singletons.clear()


# Global container instance for application wiring
_default_container: Optional[DIContainer] = None
_container_lock = threading.Lock()


def get_default_container() -> DIContainer:
    global _default_container
    if _default_container is None:
        with _container_lock:
            if _default_container is None:
                _default_container = DIContainer()
    return _default_container
