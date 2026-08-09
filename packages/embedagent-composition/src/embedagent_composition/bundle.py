from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Set, Tuple

from .catalog import FrozenComponentCatalog
from .compiler import compile_agent
from .errors import CompositionError
from .recipes import OfficialBundleRecipe

PORTABLE_PROJECT_DISTRIBUTIONS = (
    "embedagent-core",
    "embedagent-protocol",
    "embedagent-host",
    "embedagent-composition",
    "embedagent-workflow-cpp",
    "embedagent",
)

_RUNTIME_CAPABILITY_RE = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$")
_ASSURANCE_LEVELS = ("dev", "release")


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _value_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("ascii")).hexdigest()


@dataclass(frozen=True)
class CompiledBundlePlan:
    schema_version: int
    flavor_id: str
    target_id: str
    assurance: str
    artifact_name: str
    agent_id: str
    config_template_id: str
    allowed_agent_application_ids: Tuple[str, ...]
    component_ids: Tuple[str, ...]
    shell_ids: Tuple[str, ...]
    plan_fact_ids: Tuple[str, ...]
    runtime_capability_ids: Tuple[str, ...]
    runtime_component_ids: Tuple[str, ...]
    asset_ids: Tuple[str, ...]
    python_feature_ids: Tuple[str, ...]
    launcher_ids: Tuple[str, ...]
    gate_ids: Tuple[str, ...]
    project_distribution_ids: Tuple[str, ...]
    agent_lock_sha256: str
    component_catalog_sha256: str
    runtime_contract_sha256: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "flavor_id": self.flavor_id,
            "target_id": self.target_id,
            "assurance": self.assurance,
            "artifact_name": self.artifact_name,
            "agent_id": self.agent_id,
            "config_template_id": self.config_template_id,
            "allowed_agent_application_ids": list(self.allowed_agent_application_ids),
            "component_ids": list(self.component_ids),
            "shell_ids": list(self.shell_ids),
            "plan_fact_ids": list(self.plan_fact_ids),
            "runtime_capability_ids": list(self.runtime_capability_ids),
            "runtime_component_ids": list(self.runtime_component_ids),
            "asset_ids": list(self.asset_ids),
            "python_feature_ids": list(self.python_feature_ids),
            "launcher_ids": list(self.launcher_ids),
            "gate_ids": list(self.gate_ids),
            "project_distribution_ids": list(self.project_distribution_ids),
            "agent_lock_sha256": self.agent_lock_sha256,
            "component_catalog_sha256": self.component_catalog_sha256,
            "runtime_contract_sha256": self.runtime_contract_sha256,
        }

    @property
    def sha256(self) -> str:
        return _value_sha256(self.to_dict())


def _records(value: object, error_code: str) -> List[Dict[str, object]]:
    if not isinstance(value, list):
        raise CompositionError(error_code, "expected a list")
    records = []  # type: List[Dict[str, object]]
    for item in value:
        if not isinstance(item, dict):
            raise CompositionError(error_code, "expected an object")
        records.append(item)
    return records


def _string_list(value: object, error_code: str, owner: str) -> Tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise CompositionError(error_code, owner)
    result = tuple(str(item or "").strip() for item in value)
    if any(not item for item in result) or len(set(result)) != len(result):
        raise CompositionError(error_code, owner)
    return result


def _capability_list(value: object, error_code: str, owner: str) -> Tuple[str, ...]:
    result = _string_list(value, error_code, owner)
    for capability_id in result:
        if not _RUNTIME_CAPABILITY_RE.match(capability_id):
            raise CompositionError(error_code, capability_id)
    return result


def _component_fact(component: Dict[str, object]) -> str:
    kind = str(component.get("kind") or "").strip()
    component_id = str(component.get("component_id") or "").strip()
    slug = component_id.replace("_", "-").replace(".", "-")
    return "component.%s.%s" % (kind, slug)


def _index_runtime_components(runtime_contract: Dict[str, object]):
    components = {}  # type: Dict[str, Dict[str, object]]
    providers = {}  # type: Dict[str, str]
    raw_components = _records(
        runtime_contract.get("runtime_components"),
        "invalid_runtime_components",
    )
    for component in raw_components:
        component_id = str(component.get("id") or "").strip()
        if not component_id:
            raise CompositionError("invalid_runtime_component_id", component_id)
        if component_id in components:
            raise CompositionError("duplicate_runtime_component", component_id)
        provides = _capability_list(
            component.get("provides"),
            "invalid_runtime_capability",
            component_id,
        )
        if not provides:
            raise CompositionError("invalid_runtime_capability", component_id)
        requires = _capability_list(
            component.get("requires", []),
            "invalid_runtime_requirement",
            component_id,
        )
        normalized = dict(component)
        normalized["id"] = component_id
        normalized["provides"] = provides
        normalized["requires"] = requires
        components[component_id] = normalized
        for capability_id in provides:
            owner = providers.get(capability_id)
            if owner is not None:
                raise CompositionError("ambiguous_runtime_provider", capability_id)
            providers[capability_id] = component_id
    return components, providers


def _runtime_closure(
    requirements: Set[str],
    components: Dict[str, Dict[str, object]],
    providers: Dict[str, str],
) -> Tuple[Set[str], Set[str]]:
    selected = set()  # type: Set[str]
    visiting = set()  # type: Set[str]
    resolved = set()  # type: Set[str]

    def resolve_capability(capability_id: str) -> None:
        if capability_id in resolved:
            return
        provider_id = providers.get(capability_id)
        if provider_id is None:
            raise CompositionError("unknown_runtime_requirement", capability_id)
        resolve_component(provider_id)
        resolved.add(capability_id)

    def resolve_component(component_id: str) -> None:
        if component_id in selected:
            return
        if component_id in visiting:
            raise CompositionError("runtime_component_cycle", component_id)
        visiting.add(component_id)
        component = components[component_id]
        for capability_id in component["requires"]:
            requirements.add(capability_id)
            resolve_capability(capability_id)
        visiting.remove(component_id)
        selected.add(component_id)

    for capability_id in sorted(requirements):
        resolve_capability(capability_id)
    return requirements, selected


def _index_named_records(
    records: Iterable[Dict[str, object]],
    invalid_code: str,
    duplicate_code: str,
) -> Dict[str, Dict[str, object]]:
    result = {}  # type: Dict[str, Dict[str, object]]
    for record in records:
        record_id = str(record.get("id") or "").strip()
        if not record_id:
            raise CompositionError(invalid_code, record_id)
        if record_id in result:
            raise CompositionError(duplicate_code, record_id)
        result[record_id] = record
    return result


def _condition_value(condition: object, known_facts: Set[str], facts: Set[str]) -> bool:
    if not isinstance(condition, dict) or len(condition) != 1:
        raise CompositionError("invalid_bundle_condition", str(condition))
    operator = next(iter(condition))
    value = condition[operator]
    if operator in ("all_of", "any_of"):
        fact_ids = _string_list(value, "invalid_bundle_condition", operator)
        for fact_id in fact_ids:
            if fact_id not in known_facts:
                raise CompositionError("unknown_bundle_fact", fact_id)
        matches = [fact_id in facts for fact_id in fact_ids]
        return all(matches) if operator == "all_of" else any(matches)
    if operator == "not":
        fact_id = str(value or "").strip()
        if not fact_id:
            raise CompositionError("invalid_bundle_condition", operator)
        if fact_id not in known_facts:
            raise CompositionError("unknown_bundle_fact", fact_id)
        return fact_id not in facts
    raise CompositionError("unknown_bundle_condition_operator", str(operator))


def _artifact_name(flavor_id: str, assurance: str) -> str:
    names = {
        "minimal-cli": "embedagent-minimal-cli-win7-x64",
        "cpp-desktop": "embedagent-win7-x64",
    }
    try:
        base_name = names[flavor_id]
    except KeyError:
        raise CompositionError("unknown_bundle_artifact", flavor_id)
    return base_name if assurance == "release" else "%s-dev" % base_name


def _known_facts(
    catalog: FrozenComponentCatalog,
    runtime_contract: Dict[str, object],
    providers: Dict[str, str],
) -> Set[str]:
    facts = set()  # type: Set[str]
    for manifest in catalog.manifests():
        manifest_dict = manifest.to_dict()
        facts.add(_component_fact(manifest_dict))
        if manifest.kind == "shell" and manifest.component_id.startswith("shell."):
            facts.add("shell.%s" % manifest.component_id[len("shell.") :])
    facts.update("runtime.%s" % item for item in providers)
    facts.update("assurance.%s" % item for item in _ASSURANCE_LEVELS)
    targets = runtime_contract.get("targets") or {}
    if not isinstance(targets, dict):
        raise CompositionError("invalid_bundle_targets", "expected an object")
    facts.update("target.%s" % item for item in targets)
    return facts


def _validate_shells(
    recipe: OfficialBundleRecipe,
    components: List[Dict[str, object]],
) -> None:
    compiled_shells = []  # type: List[str]
    for component in components:
        if component.get("kind") != "shell":
            continue
        component_id = str(component.get("component_id") or "")
        if not component_id.startswith("shell."):
            raise CompositionError("invalid_shell_component", component_id)
        compiled_shells.append(component_id[len("shell.") :])
    if len(compiled_shells) != len(set(compiled_shells)):
        raise CompositionError("duplicate_shell_component", recipe.recipe_id)
    if set(compiled_shells) != set(recipe.shell_ids):
        raise CompositionError("bundle_recipe_shell_mismatch", recipe.recipe_id)


def _asset_ids(
    asset_manifest: Dict[str, object],
    components: Dict[str, Dict[str, object]],
    selected_component_ids: Set[str],
) -> Set[str]:
    if asset_manifest.get("schema_version") != 1:
        raise CompositionError(
            "unsupported_asset_manifest",
            str(asset_manifest.get("schema_version")),
        )
    asset_records = _records(asset_manifest.get("assets"), "invalid_asset_manifest")
    assets = _index_named_records(
        asset_records,
        "invalid_asset_id",
        "duplicate_asset_id",
    )
    selected = set()  # type: Set[str]
    for component_id in selected_component_ids:
        component = components[component_id]
        selected.update(
            _string_list(component.get("asset_ids", []), "invalid_asset_ids", component_id)
        )
    for asset_id in selected:
        if asset_id not in assets:
            raise CompositionError("unknown_bundle_asset", asset_id)
    return selected


def compile_bundle_plan(
    recipe: OfficialBundleRecipe,
    catalog: FrozenComponentCatalog,
    runtime_contract: Dict[str, object],
    asset_manifest: Dict[str, object],
    target_id: str,
    assurance: str,
) -> CompiledBundlePlan:
    target_id = str(target_id or "").strip()
    assurance = str(assurance or "").strip()
    if assurance not in _ASSURANCE_LEVELS:
        raise CompositionError("invalid_bundle_assurance", assurance)
    if runtime_contract.get("schema_version") != 2:
        raise CompositionError(
            "unsupported_runtime_contract",
            str(runtime_contract.get("schema_version")),
        )
    targets = runtime_contract.get("targets") or {}
    if not isinstance(targets, dict):
        raise CompositionError("invalid_bundle_targets", "expected an object")
    target = targets.get(target_id)
    if not isinstance(target, dict):
        raise CompositionError("unknown_bundle_target", target_id)

    compiled_agent = compile_agent(recipe.definition_factory(), catalog)
    components = compiled_agent.manifest["components"]
    component_ids = tuple(item["component_id"] for item in components)
    _validate_shells(recipe, components)

    requirements = set(
        _capability_list(
            target.get("always_requires", []),
            "invalid_runtime_requirement",
            target_id,
        )
    )
    for component in components:
        requirements.update(component.get("runtime_requirements") or ())
    runtime_components, providers = _index_runtime_components(runtime_contract)
    requirements, selected_runtime = _runtime_closure(
        requirements,
        runtime_components,
        providers,
    )

    facts = set(_component_fact(item) for item in components)
    facts.update("shell.%s" % item for item in recipe.shell_ids)
    facts.update("runtime.%s" % item for item in requirements)
    facts.add("assurance.%s" % assurance)
    facts.add("target.%s" % target_id)
    known_facts = _known_facts(catalog, runtime_contract, providers)

    gate_records = _records(runtime_contract.get("release_gates"), "invalid_release_gates")
    gates = _index_named_records(
        gate_records,
        "invalid_release_gate_id",
        "duplicate_release_gate",
    )
    selected_gates = set(
        _string_list(target.get("always_gates", []), "invalid_release_gates", target_id)
    )
    for gate_id, gate in gates.items():
        if _condition_value(gate.get("applies_when"), known_facts, facts):
            selected_gates.add(gate_id)
    for gate_id in selected_gates:
        if gate_id not in gates:
            raise CompositionError("unknown_release_gate", gate_id)

    launcher_records = _records(runtime_contract.get("launchers"), "invalid_launchers")
    launchers = _index_named_records(
        launcher_records,
        "invalid_launcher_id",
        "duplicate_launcher",
    )
    selected_launchers = set()  # type: Set[str]
    python_features = set()  # type: Set[str]
    for component_id in selected_runtime:
        component = runtime_components[component_id]
        selected_launchers.update(
            _string_list(component.get("launcher_ids", []), "invalid_launcher_ids", component_id)
        )
        python_features.update(
            _string_list(
                component.get("python_feature_ids", []),
                "invalid_python_feature_ids",
                component_id,
            )
        )
    for gate_id in selected_gates:
        selected_launchers.update(
            _string_list(gates[gate_id].get("launcher_ids", []), "invalid_launcher_ids", gate_id)
        )
    for launcher_id in selected_launchers:
        if launcher_id not in launchers:
            raise CompositionError("unknown_bundle_launcher", launcher_id)

    selected_assets = _asset_ids(
        asset_manifest,
        runtime_components,
        selected_runtime,
    )
    catalog_payload = [manifest.to_dict() for manifest in catalog.manifests()]
    return CompiledBundlePlan(
        schema_version=1,
        flavor_id=recipe.recipe_id,
        target_id=target_id,
        assurance=assurance,
        artifact_name=_artifact_name(recipe.recipe_id, assurance),
        agent_id=compiled_agent.agent_id,
        config_template_id=recipe.config_template_id,
        allowed_agent_application_ids=(compiled_agent.agent_id,),
        component_ids=component_ids,
        shell_ids=recipe.shell_ids,
        plan_fact_ids=tuple(sorted(facts)),
        runtime_capability_ids=tuple(sorted(requirements)),
        runtime_component_ids=tuple(sorted(selected_runtime)),
        asset_ids=tuple(sorted(selected_assets)),
        python_feature_ids=tuple(sorted(python_features)),
        launcher_ids=tuple(sorted(selected_launchers)),
        gate_ids=tuple(sorted(selected_gates)),
        project_distribution_ids=PORTABLE_PROJECT_DISTRIBUTIONS,
        agent_lock_sha256=_value_sha256(compiled_agent.lock),
        component_catalog_sha256=_value_sha256(catalog_payload),
        runtime_contract_sha256=_value_sha256(runtime_contract),
    )
