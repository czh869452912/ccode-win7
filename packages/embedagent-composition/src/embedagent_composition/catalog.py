from __future__ import annotations

from pathlib import PurePosixPath
from typing import Dict, Tuple

from .errors import CompositionError
from .model import ComponentManifest


def _validate_asset_path(value: str) -> None:
    path = PurePosixPath(str(value))
    if path.is_absolute() or not str(value).strip() or ".." in path.parts:
        raise CompositionError("unsafe_asset_path", str(value))


class FrozenComponentCatalog(object):
    def __init__(self, manifests: Dict[str, ComponentManifest]):
        self._manifests = dict(manifests)

    def manifest(self, component_id: str) -> ComponentManifest:
        try:
            return self._manifests[str(component_id)]
        except KeyError:
            raise CompositionError("unknown_component", str(component_id))

    def manifests(self) -> Tuple[ComponentManifest, ...]:
        return tuple(self._manifests[key] for key in sorted(self._manifests))


class ComponentCatalog(object):
    def __init__(self):
        self._manifests: Dict[str, ComponentManifest] = {}
        self._frozen = False

    def register(self, manifest: ComponentManifest) -> None:
        if self._frozen:
            raise CompositionError("catalog_frozen", "component catalog is already frozen")
        component_id = str(manifest.component_id or "").strip()
        if not component_id:
            raise CompositionError("invalid_component_id", "component id is required")
        if component_id in self._manifests:
            raise CompositionError("duplicate_component", component_id)
        if not str(manifest.kind or "").strip() or not str(manifest.version or "").strip():
            raise CompositionError("invalid_component", component_id)
        for asset in manifest.runtime_assets:
            _validate_asset_path(asset)
        self._manifests[component_id] = manifest

    def freeze(self) -> FrozenComponentCatalog:
        if self._frozen:
            return FrozenComponentCatalog(self._manifests)
        namespaces = {}
        for manifest in self._manifests.values():
            for required in manifest.requires:
                if required not in self._manifests:
                    raise CompositionError("missing_dependency", "%s -> %s" % (manifest.component_id, required))
            for conflict in manifest.conflicts:
                if conflict not in self._manifests:
                    raise CompositionError("unknown_conflict", "%s -> %s" % (manifest.component_id, conflict))
            for namespace in manifest.namespaces:
                owner = namespaces.get(namespace)
                if owner is not None and owner != manifest.component_id:
                    raise CompositionError("duplicate_namespace", namespace)
                namespaces[namespace] = manifest.component_id
        self._frozen = True
        return FrozenComponentCatalog(self._manifests)
