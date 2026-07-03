import assert from "node:assert/strict";

import { normalizeProtocolCapabilities } from "../src/session-runtime/protocol-normalizer.js";
import { resolveToolPresentation } from "../src/session-runtime/tool-presentation.js";

export function runProtocolNormalizerTests() {
  const capabilities = normalizeProtocolCapabilities({
    modes: [
      {
        id: "python-build",
        label: "Python Build",
        description: "Implement Python changes",
        iconKey: "hammer",
        colorToken: "success",
        commandId: "mode.python-build",
      },
      {
        id: "html-preview",
        label: "HTML Preview",
        description: "Preview static HTML",
        icon_key: "browser",
        color_token: "info",
      },
    ],
    commands: [
      {
        id: "workflow.test",
        label: "Run tests",
        group: "workflow",
        dispatch: { kind: "slash", command: "/test" },
      },
    ],
    tools: [
      {
        name: "pytest",
        label: "Pytest",
        iconKey: "test-tube",
        rendererKey: "command",
        permissionCategory: "command",
        metadata: { previewArg: "command" },
      },
    ],
    workflowPackages: [{ id: "workflow-python", label: "Python", active: true }],
    agentApplication: {
      applicationId: "tests.python",
      label: "Python Agent",
      profileId: "tests.python.profile",
      workflowPackageIds: ["workflow-python"],
      active: true,
    },
    agentApplications: [
      {
        id: "tests.python",
        label: "Python Agent",
        profile_id: "tests.python.profile",
        workflow_package_ids: ["workflow-python"],
        active: true,
      },
    ],
    emptyState: {
      scenario_label: "Python workspace",
      primary: "Choose a local Python workspace",
      secondary: "Python workflow metadata drives this shell.",
      pathPlaceholder: "D:\\work\\python-app",
    },
  });

  assert.deepEqual(
    capabilities.modes.map((item) => item.id),
    ["python-build", "html-preview"],
  );
  assert.equal(capabilities.modeCatalog["python-build"].label, "Python Build");
  assert.equal(capabilities.modeCatalog["html-preview"].colorToken, "info");
  assert.equal(capabilities.commands[0].dispatch.command, "/test");
  assert.equal(capabilities.toolCatalog.pytest.label, "Pytest");
  assert.equal(capabilities.workflowPackages[0].id, "workflow-python");
  assert.equal(capabilities.agentApplication.applicationId, "tests.python");
  assert.equal(capabilities.agentApplications[0].profileId, "tests.python.profile");
  assert.equal(capabilities.emptyState.scenarioLabel, "Python workspace");
  assert.equal(capabilities.emptyState.pathPlaceholder, "D:\\work\\python-app");

  const pytestPresentation = resolveToolPresentation("pytest", capabilities.toolCatalog);
  assert.equal(pytestPresentation.label, "Pytest");
  assert.equal(pytestPresentation.iconKey, "test-tube");
  assert.equal(pytestPresentation.rendererKey, "command");
  assert.equal(pytestPresentation.previewArg, "command");

  const fallbackPresentation = resolveToolPresentation("html_lint", capabilities.toolCatalog);
  assert.equal(fallbackPresentation.label, "html_lint");
  assert.equal(fallbackPresentation.iconKey, "wrench");
  assert.equal(fallbackPresentation.rendererKey, "generic");

  const emptyCapabilities = normalizeProtocolCapabilities({});
  assert.deepEqual(emptyCapabilities.emptyState, {
    scenarioLabel: "",
    primary: "",
    secondary: "",
    pathPlaceholder: "",
  });
  assert.deepEqual(emptyCapabilities.agentApplication, null);
  assert.deepEqual(emptyCapabilities.agentApplications, []);
}
