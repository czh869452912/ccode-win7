from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict, Optional

from .catalog import FrozenComponentCatalog
from .compiler import compile_agent
from .errors import CompositionError
from .model import AgentProductDefinition, CompiledAgentSpec


def _write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source), str(target))


def export_agent(
    definition: AgentProductDefinition,
    catalog: FrozenComponentCatalog,
    output_dir: Path,
    asset_root: Optional[Path] = None,
    component_files: Optional[Dict[str, Path]] = None,
) -> CompiledAgentSpec:
    output_dir = Path(output_dir).resolve()
    if output_dir.parent == output_dir:
        raise CompositionError("unsafe_output_path", str(output_dir))
    temp_dir = output_dir.with_name(output_dir.name + ".tmp")
    if temp_dir.exists():
        shutil.rmtree(str(temp_dir))
    try:
        compiled = compile_agent(
            definition,
            catalog,
            component_files=component_files,
            asset_root=asset_root,
        )
        temp_dir.mkdir(parents=True, exist_ok=False)
        for item in compiled.files:
            source_name = str(item["source_name"])
            source = None
            component_id = str(item["component_id"])
            if str(item["target_path"]).startswith("components/"):
                source = Path((component_files or {})[component_id]).resolve()
            else:
                source = (Path(asset_root).resolve() / source_name).resolve()
            target = temp_dir / str(item["target_path"])
            _copy_file(source, target)
        _write_json(temp_dir / "agent.json", compiled.manifest)
        _write_json(temp_dir / "agent.lock.json", compiled.lock)
        _write_json(
            temp_dir / "export-report.json",
            {
                "schema_version": 1,
                "agent_id": compiled.agent_id,
                "component_ids": [
                    item["component_id"] for item in compiled.manifest["components"]
                ],
                "files": list(compiled.files),
                "status": "complete",
            },
        )
        if output_dir.exists():
            shutil.rmtree(str(output_dir))
        temp_dir.replace(output_dir)
        return compiled
    except Exception:
        if temp_dir.exists():
            shutil.rmtree(str(temp_dir))
        raise
