from __future__ import annotations

from typing import Any, Callable, Dict, List

from embedagent_core.capabilities import CapabilityRegistry


class RuntimeCapabilityService(object):
    def __init__(
        self,
        descriptor_loader: Callable[[], List[Any]],
        model_descriptor_loader: Callable[[], Any],
        mode_descriptor_loader: Callable[[], List[Any]],
        workflow_manifest_loader: Callable[[], List[Any]],
    ) -> None:
        self._descriptor_loader = descriptor_loader
        self._model_descriptor_loader = model_descriptor_loader
        self._mode_descriptor_loader = mode_descriptor_loader
        self._workflow_manifest_loader = workflow_manifest_loader

    def snapshot(self) -> Dict[str, Any]:
        registry = CapabilityRegistry()
        model_descriptor = self._model_descriptor_loader()
        if model_descriptor is not None:
            registry.register(model_descriptor)
        for descriptor in self._mode_descriptor_loader() or []:
            registry.register(descriptor)
        for descriptor in self._descriptor_loader() or []:
            registry.register(descriptor)
        for manifest in self._workflow_manifest_loader() or []:
            registry.register(manifest)
        return registry.snapshot().to_dict()

    def registered_tool_names(self, snapshot: Dict[str, Any]) -> List[str]:
        names = []
        for item in list(snapshot.get("descriptors") or []):
            if not isinstance(item, dict):
                continue
            if item.get("kind") == "tool" and item.get("name"):
                names.append(str(item.get("name")))
        return sorted(set(names))
