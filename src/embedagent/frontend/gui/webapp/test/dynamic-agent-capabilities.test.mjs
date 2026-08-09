import assert from "node:assert/strict";

import { normalizeAppBootstrap } from "../src/app-shell/model.js";
import { buildAppCapabilityModel } from "../src/app-runtime/app-capability-model.js";
import { normalizeProtocolCapabilities } from "../src/session-runtime/protocol-normalizer.js";
import { buildSessionCapabilityModel } from "../src/session-runtime/session-capability-model.js";
import { buildWorkbenchCommands } from "../src/workbench/commands.js";
import {
  agentApplicationDescriptor,
  capabilitySnapshot,
  commandDescriptor,
  modeDescriptor,
  toolDescriptor,
} from "./protocol-fixtures.mjs";

function appBootstrap(shell, app = {}) {
  return {
    schema_version: 1,
    app: {
      shell_version: 1,
      product_name: "",
      protocol: "gui_app_shell_v1",
      ...app,
    },
    workspaces: [],
    active_workspace: null,
    has_active_workspace: false,
    shell,
    settings: {
      confirm_workspace_switch: true,
      show_diagnostics_badge: true,
    },
    diagnostics: {},
    last_error: "",
  };
}

function shellDescriptor(patch = {}) {
  return {
    schema_version: 1,
    commands: [],
    surfaces: [],
    keybindings: [],
    tool_presentations: [],
    timeline_items: [],
    interactions: [],
    ...patch,
  };
}

function shellCommand(id) {
  return {
    id,
    label: "Check project",
    group: "project",
    dispatch: { kind: "session.command", command: "check-project" },
    shortcut: "",
    availability: {},
    summary: "",
    source_type: "agent_application",
    source_id: "tests.project-inspector",
  };
}

const SPECIALIZED_SESSION_FIXTURE = capabilitySnapshot({
  modes: [
    modeDescriptor("inspect", "Inspect", {
      description: "Inspect the active project",
      icon_key: "search",
    }),
  ],
  commands: [
    commandDescriptor("project.unregistered", "Unregistered command", {
      group: "project",
      dispatch: { kind: "slash", command: "/unregistered" },
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
  empty_state: {
    scenario_label: "Inspection workspace",
    primary: "Choose a project to inspect",
    secondary: "",
    path_placeholder: "D:/work/inspection-target",
  },
});

export function runDynamicAgentCapabilityTests() {
  const baseApp = normalizeAppBootstrap(appBootstrap(shellDescriptor()));
  const baseAppModel = buildAppCapabilityModel(baseApp.capabilities);
  const baseSession = normalizeProtocolCapabilities(capabilitySnapshot());
  const baseSessionModel = buildSessionCapabilityModel(baseSession);

  assert.deepEqual(baseAppModel.appCapabilities.workbenchCommands, []);
  assert.deepEqual(baseSessionModel.modeCatalog, {});
  assert.deepEqual(baseSessionModel.toolCatalog, {});

  const specializedApp = normalizeAppBootstrap(appBootstrap(shellDescriptor({
    commands: [shellCommand("project.check")],
    surfaces: [
      {
        id: "project_report",
        label: "Project report",
        placement: "secondary",
        renderer_key: "workflow_summary",
        availability: {},
        metadata: { body_kind: "surface_panel", panel_kind: "descriptor" },
      },
    ],
  }), { product_name: "Project Inspector" }));
  const specializedAppModel = buildAppCapabilityModel(specializedApp.capabilities);
  const specializedSession = normalizeProtocolCapabilities(SPECIALIZED_SESSION_FIXTURE);
  const specializedSessionModel = buildSessionCapabilityModel(specializedSession);
  const commands = buildWorkbenchCommands(
    specializedSession,
    specializedAppModel.appCapabilities,
  );
  const surfaces = specializedAppModel.contributions;

  assert.equal(specializedApp.app.productName, "Project Inspector");
  assert.equal(specializedSessionModel.emptyState.scenarioLabel, "Inspection workspace");
  assert.equal(specializedSessionModel.modeCatalog.inspect.label, "Inspect");
  assert.equal(specializedSessionModel.toolCatalog.project_check.label, "Project check");
  assert.equal(specializedSession.agentApplication.applicationId, "tests.project-inspector");
  assert.deepEqual(commands.map((item) => item.id), ["project.check"]);
  assert.equal(commands.some((item) => item.id === "project.unregistered"), false);
  assert.deepEqual(surfaces.map((item) => item.kind), ["project_report"]);
  assert.equal(surfaces[0].bodyKind, "surface_panel");
}
