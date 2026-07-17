import json

import pytest
from embedagent_core.workflow_package_manifest import (
    WorkflowPackageManifest,
    WorkflowPackageManifestError,
    WorkflowPackDeclaration,
    WorkflowToolDeclaration,
)


def test_workflow_package_manifest_serializes_stable_safe_payload():
    manifest = WorkflowPackageManifest(
        package_id=" embedagent.c_workflow ",
        label="C/C++ Workflow",
        version="1",
        source_type="builtin",
        source_id="embedagent_workflow_cpp",
        supported_modes=["debug", "build", "build"],
        supported_workflow_states=["chat", "plan"],
        tools=[
            WorkflowToolDeclaration(
                name="run_recipe",
                permission_category="toolchain_exec",
                source_type="workflow_package",
                source_id="embedagent_workflow_cpp",
                metadata={"activity_kind": "diagnostic"},
            )
        ],
        packs=[
            WorkflowPackDeclaration(
                name="build_lite",
                tool_names=["read_file", "run_recipe", "read_file"],
            )
        ],
        resource_scopes=[".embedagent/recipes", ".embedagent/recipes"],
    )

    payload = manifest.to_dict()

    assert payload["package_id"] == "embedagent.c_workflow"
    assert payload["label"] == "C/C++ Workflow"
    assert payload["supported_modes"] == ["build", "debug"]
    assert payload["supported_workflow_states"] == ["chat", "plan"]
    assert payload["tools"][0]["name"] == "run_recipe"
    assert payload["tools"][0]["metadata"]["activity_kind"] == "diagnostic"
    assert payload["packs"][0]["tool_names"] == ["read_file", "run_recipe"]
    assert payload["resource_scopes"] == [".embedagent/recipes"]
    assert payload["diagnostics"] == []
    json.dumps(payload, sort_keys=True)


def test_workflow_package_manifest_is_non_executing_control_plane():
    manifest = WorkflowPackageManifest(
        package_id="local.workflow",
        label="Local Workflow",
        tools=[WorkflowToolDeclaration(name="local_tool")],
        packs=[WorkflowPackDeclaration(name="local_pack", tool_names=["local_tool"])],
        resource_scopes=[".embedagent/recipes"],
    )

    payload = manifest.to_dict()

    assert set(payload.keys()) == {
        "package_id",
        "label",
        "version",
        "source_type",
        "source_id",
        "supported_modes",
        "supported_workflow_states",
        "tools",
        "packs",
        "resource_scopes",
        "diagnostics",
    }
    forbidden = ("entrypoint", "enabled", "autoload", "permissions", "dependencies")
    assert not any(key in payload for key in forbidden)
    assert not any(key in payload["tools"][0] for key in forbidden)


def test_workflow_package_manifest_rejects_missing_identity():
    with pytest.raises(WorkflowPackageManifestError):
        WorkflowPackageManifest(package_id="", label="Missing")


def test_c_workflow_manifest_projects_package_packs_tools_and_resources():
    from embedagent_workflow_cpp.package_manifest import (
        build_c_workflow_package_manifest,
    )

    manifest = build_c_workflow_package_manifest()
    payload = manifest.to_dict()

    assert payload["package_id"] == "embedagent.c_workflow"
    assert payload["source_type"] == "builtin"
    assert payload["source_id"] == "embedagent_workflow_cpp"
    assert payload["supported_modes"] == ["build", "debug", "verify"]
    assert "chat" in payload["supported_workflow_states"]
    assert ".embedagent/recipes" in payload["resource_scopes"]

    pack_names = [item["name"] for item in payload["packs"]]
    assert "build_lite" in pack_names
    assert "debug_lite" in pack_names
    assert "verify" in pack_names

    tools = dict((item["name"], item) for item in payload["tools"])
    assert tools["run_recipe"]["permission_category"] == "toolchain_exec"
    assert tools["task_status"]["permission_category"] == "read"
    assert tools["report_quality_v2"]["metadata"]["mode_visibility"] == ["verify"]


def test_c_harness_extension_exposes_read_only_package_manifest():
    from embedagent_workflow_cpp.extension import CHarnessWorkflowExtension

    manifest = CHarnessWorkflowExtension().package_manifest()

    assert manifest["package_id"] == "embedagent.c_workflow"
    assert any(item["name"] == "verify" for item in manifest["packs"])
    assert any(item["name"] == "run_recipe" for item in manifest["tools"])
