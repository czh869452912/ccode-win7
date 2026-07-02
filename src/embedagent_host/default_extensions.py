from __future__ import annotations

from dataclasses import dataclass

from embedagent.workflow_packages.c_cpp.extension import CHarnessWorkflowExtension
from embedagent_core.extensions import ExtensionManager


@dataclass
class DefaultExtensionSet:
    manager: ExtensionManager
    harness_workflow: CHarnessWorkflowExtension


def build_default_extension_set(tools) -> DefaultExtensionSet:
    harness_workflow = CHarnessWorkflowExtension(tools=tools)
    return DefaultExtensionSet(
        manager=ExtensionManager([harness_workflow]),
        harness_workflow=harness_workflow,
    )
