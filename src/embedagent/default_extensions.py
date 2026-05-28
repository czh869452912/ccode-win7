from __future__ import annotations

from dataclasses import dataclass

from embedagent.extensions import ExtensionManager
from embedagent.harness.extension import CHarnessWorkflowExtension


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
