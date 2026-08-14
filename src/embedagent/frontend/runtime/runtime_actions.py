from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, Mapping


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(dict((key, _freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return dict((key, _thaw(item)) for key, item in value.items())
    if isinstance(value, (tuple, list)):
        return [_thaw(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class RuntimeAction(object):
    kind: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        kind = str(self.kind or "").strip()
        if not kind:
            raise ValueError("runtime action kind is required")
        if not isinstance(self.payload, Mapping):
            raise TypeError("runtime action payload must be a mapping")
        if "kind" in self.payload:
            raise ValueError("runtime action payload must not redefine kind")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "payload", _freeze(self.payload))

    def to_dict(self) -> Dict[str, Any]:
        value = {"kind": self.kind}
        value.update(_thaw(self.payload))
        return value
