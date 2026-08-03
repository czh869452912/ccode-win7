import assert from "node:assert/strict";

import { normalizeAppBootstrap } from "../src/app-shell/model.js";
import { buildAppCapabilityModel } from "../src/app-runtime/app-capability-model.js";
import { normalizeProtocolCapabilities } from "../src/session-runtime/protocol-normalizer.js";
import { buildSessionCapabilityModel } from "../src/session-runtime/session-capability-model.js";
import { buildWorkbenchCommands } from "../src/workbench/commands.js";
import { rightPanelLauncherSurfaceDefinitions } from "../src/workbench/surfaces.js";
import {
  agentApplicationDescriptor,
  capabilitySnapshot,
  commandDescriptor,
  modeDescriptor,
  toolDescriptor,
} from "./protocol-fixtures.mjs";

const BASE_APP_FIXTURE = Object.freeze({
  app: { shell_version: 1, protocol: "gui_app_shell_v1" },
  capabilities: {
    empty_state: {
      primary: "Open a workspace",
      secondary: "",
      path_placeholder: "D:\\work\\project",
    },
  },
});

const SPECIALIZED_APP_FIXTURE = Object.freeze({
  app: {
    shell_version: 1,
    product_name: "Project Inspector",
    protocol: "gui_app_shell_v1",
  },
  capabilities: {
    workbench_commands: [
      {
        id: "project.check",
        label: "Check project",
        group: "project",
        dispatch: { kind: "slash", command: "/check-project" },
      },
    ],
    surfaces: {
      right_panel: [
        {
          id: "project_report",
          kind: "project_report",
          title: "Project report",
          body_kind: "surface_panel",
          panel_kind: "descriptor",
          launcher: true,
          command: true,
        },
      ],
    },
    empty_state: {
      scenario_label: "Inspection workspace",
      primary: "Choose a project to inspect",
      secondary: "Project capabilities configure this shell.",
      path_placeholder: "D:\\work\\inspection-target",
    },
  },
});

const SPECIALIZED_SESSION_FIXTURE = capabilitySnapshot({
  modes: [
    modeDescriptor("inspect", "Inspect", {
      description: "Inspect the active project",
      icon_key: "search",
    }),
  ],
  commands: [
    commandDescriptor("project.check", "Check project", {
      group: "project",
      dispatch: { kind: "slash", command: "/check-project" },
    }),
  ],
  tools: [
    toolDescriptor("project_check", "Project check", {
      icon_key: "search-check",
      permission_category: "toolchain_exec",
      metadata: { preview_arg: "target" },
    }),
  ],
  agent_application: agentApplicationDescriptor(
    "tests.project-inspector",
    "Project Inspector",
    {
      profile_id: "tests.project-inspector.profile",
      active: true,
    },
  ),
  empty_state: SPECIALIZED_APP_FIXTURE.capabilities.empty_state,
});

export function runDynamicAgentCapabilityTests() {
  const baseApp = normalizeAppBootstrap(BASE_APP_FIXTURE);
  const baseAppModel = buildAppCapabilityModel(baseApp.capabilities);
  const baseSession = normalizeProtocolCapabilities(capabilitySnapshot());
  const baseSessionModel = buildSessionCapabilityModel(baseSession);

  assert.equal(baseApp.app.productName, "");
  assert.equal(baseAppModel.emptyState.primary, "Open a workspace");
  assert.deepEqual(baseSession.modes, []);
  assert.deepEqual(baseSession.tools, []);
  assert.deepEqual(baseSessionModel.modeCatalog, {});
  assert.deepEqual(baseSessionModel.toolCatalog, {});

  const specializedApp = normalizeAppBootstrap(SPECIALIZED_APP_FIXTURE);
  const specializedAppModel = buildAppCapabilityModel(specializedApp.capabilities);
  const specializedSession = normalizeProtocolCapabilities(SPECIALIZED_SESSION_FIXTURE);
  const specializedSessionModel = buildSessionCapabilityModel(specializedSession);
  const commands = buildWorkbenchCommands(
    specializedSession,
    specializedAppModel.appCapabilities,
  );
  const surfaces = rightPanelLauncherSurfaceDefinitions(
    specializedAppModel.appCapabilities,
  );

  assert.equal(specializedApp.app.productName, "Project Inspector");
  assert.equal(specializedAppModel.emptyState.scenarioLabel, "Inspection workspace");
  assert.equal(specializedSession.modes[0].id, "inspect");
  assert.equal(specializedSessionModel.modeCatalog.inspect.label, "Inspect");
  assert.equal(specializedSessionModel.toolCatalog.project_check.label, "Project check");
  assert.equal(specializedSessionModel.toolCatalog.project_check.metadata.preview_arg, "target");
  assert.equal(specializedSession.agentApplication.applicationId, "tests.project-inspector");
  assert.equal(commands.some((item) => item.id === "project.check"), true);
  assert.deepEqual(surfaces.map((item) => item.kind), ["project_report"]);
  assert.equal(surfaces[0].bodyKind, "surface_panel");
}
