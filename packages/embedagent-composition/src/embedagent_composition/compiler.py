from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .catalog import FrozenComponentCatalog
from .errors import CompositionError
from .model import AgentProductDefinition, CompiledAgentSpec


def _canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _component_order(
    selected: Set[str],
    catalog: FrozenComponentCatalog,
) -> Tuple[str, ...]:
    result: List[str] = []
    visiting: Set[str] = set()
    visited: Set[str] = set()

    def visit(component_id: str) -> None:
        if component_id in visited:
            return
        if component_id in visiting:
            raise CompositionError("dependency_cycle", component_id)
        visiting.add(component_id)
        manifest = catalog.manifest(component_id)
        for required in sorted(manifest.requires):
            visit(required)
        visiting.remove(component_id)
        visited.add(component_id)
        result.append(component_id)

    for component_id in sorted(selected):
        visit(component_id)
    return tuple(result)


def _selected_components(
    definition: AgentProductDefinition,
    catalog: FrozenComponentCatalog,
) -> Tuple[str, ...]:
    selected: Set[str] = set()
    pending = [ref.component_id for ref in definition.component_refs()]
    while pending:
        component_id = str(pending.pop())
        if component_id in selected:
            continue
        manifest = catalog.manifest(component_id)
        selected.add(component_id)
        pending.extend(manifest.requires)
    for component_id in sorted(selected):
        manifest = catalog.manifest(component_id)
        for conflict in manifest.conflicts:
            if conflict in selected:
                raise CompositionError("component_conflict", "%s conflicts with %s" % (component_id, conflict))
    return _component_order(selected, catalog)


def derive_distribution_closure(
    components: List[Dict[str, object]],
) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """Project selected component manifests into their runtime owners."""
    distributions = []  # type: List[str]
    registration_entries = []  # type: List[str]
    for component in components:
        component_id = str(component.get("component_id") or "").strip()
        distribution_id = str(component.get("distribution_id") or "").strip()
        if not distribution_id:
            raise CompositionError("missing_distribution_owner", component_id)
        if distribution_id not in distributions:
            distributions.append(distribution_id)
        registration_entry = str(component.get("registration_entry") or "").strip()
        if registration_entry and registration_entry not in registration_entries:
            registration_entries.append(registration_entry)
    return tuple(distributions), tuple(registration_entries)


def compile_agent(
    definition: AgentProductDefinition,
    catalog: FrozenComponentCatalog,
    component_files: Optional[Dict[str, Path]] = None,
    asset_root: Optional[Path] = None,
) -> CompiledAgentSpec:
    agent_id = str(definition.agent_id or "").strip()
    if not agent_id:
        raise CompositionError("invalid_agent_id", "agent id is required")
    component_files = dict(component_files or {})
    ordered_ids = _selected_components(definition, catalog)
    components: List[Dict[str, object]] = []
    files: List[Dict[str, object]] = []
    for component_id in ordered_ids:
        manifest = catalog.manifest(component_id)
        manifest_dict = manifest.to_dict()
        components.append(manifest_dict)
        file_path = component_files.get(component_id)
        if file_path is not None:
            path = Path(file_path).resolve()
            if not path.is_file():
                raise CompositionError("missing_component_file", component_id)
            files.append(
                {
                    "component_id": component_id,
                    "source_name": path.name,
                    "target_path": "components/%s" % path.name,
                    "sha256": _sha256(path),
                }
            )
        if asset_root is not None:
            root = Path(asset_root).resolve()
            for asset in manifest.runtime_assets:
                asset_path = (root / asset).resolve()
                try:
                    asset_path.relative_to(root)
                except ValueError:
                    raise CompositionError("unsafe_asset_path", asset)
                if not asset_path.is_file():
                    raise CompositionError("missing_asset", asset)
                files.append(
                    {
                        "component_id": component_id,
                        "source_name": asset,
                        "target_path": "assets/%s" % asset,
                        "sha256": _sha256(asset_path),
                    }
                )
    lock_components = []
    for manifest in components:
        lock_components.append(
            {
                "component_id": manifest["component_id"],
                "version": manifest["version"],
                "api_version": manifest["api_version"],
                "manifest_sha256": hashlib.sha256(_canonical(manifest).encode("ascii")).hexdigest(),
            }
        )
    project_distribution_ids, registration_entries = derive_distribution_closure(components)
    manifest_payload = {
        "schema_version": 1,
        "agent_id": agent_id,
        "components": components,
    }
    lock_payload = {
        "schema_version": 1,
        "agent_id": agent_id,
        "components": lock_components,
        "files": sorted(files, key=lambda item: (item["target_path"], item["component_id"])),
        "project_distribution_ids": list(project_distribution_ids),
        "registration_entries": list(registration_entries),
    }
    return CompiledAgentSpec(
        agent_id=agent_id,
        manifest=manifest_payload,
        lock=lock_payload,
        files=tuple(lock_payload["files"]),
    )
