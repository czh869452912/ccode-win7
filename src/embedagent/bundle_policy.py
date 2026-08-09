from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple

from embedagent.runtime_discovery import discover_bundle_root


@dataclass(frozen=True)
class BundleRuntimePolicy:
    bundled: bool
    flavor_id: str = ""
    bundle_plan_sha256: str = ""
    allowed_agent_application_ids: Tuple[str, ...] = field(default_factory=tuple)
    shell_ids: Tuple[str, ...] = field(default_factory=tuple)

    def require_application(self, requested_id: str) -> str:
        if (
            self.bundled
            and self.allowed_agent_application_ids
            and not str(requested_id or "").strip()
        ):
            return self.allowed_agent_application_ids[0]
        return self._require(requested_id, self.allowed_agent_application_ids)

    def require_shell(self, requested_id: str) -> str:
        return self._require(requested_id, self.shell_ids)

    def _require(self, requested_id: str, allowed_ids: Tuple[str, ...]) -> str:
        requested = str(requested_id or "").strip()
        if not self.bundled or requested in allowed_ids:
            return requested
        raise ValueError("%s is not included in bundle flavor %s" % (requested, self.flavor_id))


def _load_json_object(path: Path, label: str):
    if not path.is_file():
        raise ValueError("bundle %s is missing" % label)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError("bundle %s is invalid" % label)
    if not isinstance(payload, dict):
        raise ValueError("bundle %s must be an object" % label)
    return payload


def _required_ids(plan, field_name: str) -> Tuple[str, ...]:
    values = plan.get(field_name)
    if not isinstance(values, list):
        raise ValueError("bundle plan %s must be an array" % field_name)
    normalized = tuple(str(item).strip() for item in values)
    if (
        not normalized
        or any(not item for item in normalized)
        or len(normalized) != len(set(normalized))
    ):
        raise ValueError("bundle plan %s must contain unique nonempty ids" % field_name)
    return normalized


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_bundle_policy(bundle_root: Optional[str]) -> BundleRuntimePolicy:
    if not bundle_root:
        return BundleRuntimePolicy(bundled=False)

    root = Path(os.path.realpath(str(bundle_root)))
    if not root.is_dir():
        raise ValueError("bundle root does not exist")
    manifests = root / "manifests"
    plan_path = manifests / "bundle-plan.json"
    manifest_path = manifests / "bundle-manifest.json"
    plan = _load_json_object(plan_path, "plan")
    manifest = _load_json_object(manifest_path, "manifest")
    if plan.get("schema_version") != 1:
        raise ValueError("bundle plan schema version must be 1")
    if manifest.get("schema_version") != 2:
        raise ValueError("bundle manifest schema version must be 2")

    flavor_id = str(plan.get("flavor_id") or "").strip()
    if not flavor_id:
        raise ValueError("bundle plan flavor_id is required")
    if str(manifest.get("flavor_id") or "").strip() != flavor_id:
        raise ValueError("bundle manifest flavor does not match bundle plan")
    plan_sha256 = _sha256_file(plan_path)
    if str(manifest.get("bundle_plan_sha256") or "").lower() != plan_sha256:
        raise ValueError("bundle manifest plan hash does not match bundle plan")

    return BundleRuntimePolicy(
        bundled=True,
        flavor_id=flavor_id,
        bundle_plan_sha256=plan_sha256,
        allowed_agent_application_ids=_required_ids(plan, "allowed_agent_application_ids"),
        shell_ids=_required_ids(plan, "shell_ids"),
    )


def load_current_bundle_policy(anchor_path: str) -> BundleRuntimePolicy:
    bundle_root = discover_bundle_root(
        env_root=os.environ.get("EMBEDAGENT_BUNDLE_ROOT", "").strip(),
        anchor_path=anchor_path,
        anchor_levels=tuple(range(7)),
    )
    return load_bundle_policy(bundle_root)
