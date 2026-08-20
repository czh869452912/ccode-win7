import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  emptyProtocolCapabilities,
  normalizeProtocolAppBootstrap,
  normalizeProtocolCapabilities,
  normalizeSessionBootstrap,
} from "../src/session-runtime/protocol-normalizer.js";
import { resolveToolPresentation } from "../src/session-runtime/tool-presentation.js";
import { FRONTEND_PROTOCOL_SCHEMA_VERSION } from "../src/session-runtime/protocol-version.js";

const FIXTURE_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../../../../tests/fixtures/frontend_protocol",
);

function readFixture(name) {
  return JSON.parse(fs.readFileSync(path.join(FIXTURE_ROOT, name), "utf8"));
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

export function runProtocolNormalizerTests() {
  const wireSession = readFixture("session_bootstrap.json");
  const session = normalizeSessionBootstrap(wireSession);
  const capabilities = session.capabilities;

  assert.equal(session.schemaVersion, FRONTEND_PROTOCOL_SCHEMA_VERSION);
  assert.equal(session.eventCursor, 4);
  assert.equal(session.thread.currentMode, "build");
  assert.deepEqual(capabilities.modes.map((item) => item.id), ["build"]);
  assert.equal(capabilities.modeCatalog.build.label, "Build");
  assert.equal(capabilities.commands[0].dispatch.command, "/help");
  assert.equal(capabilities.toolCatalog.read_file.label, "Read File");
  assert.equal(capabilities.agentApplication.applicationId, "embedagent.generic");
  assert.equal(capabilities.agentApplications[0].profileId, "embedagent.generic");
  assert.equal(capabilities.emptyState.scenarioLabel, "Local workspace");

  const readPresentation = resolveToolPresentation("read_file", capabilities.toolCatalog);
  assert.equal(readPresentation.label, "Read File");
  assert.equal(readPresentation.rendererKey, "generic");

  const fallbackPresentation = resolveToolPresentation("html_lint", capabilities.toolCatalog);
  assert.equal(fallbackPresentation.label, "html_lint");
  assert.equal(fallbackPresentation.iconKey, "wrench");
  assert.equal(fallbackPresentation.rendererKey, "generic");

  const emptyCapabilities = emptyProtocolCapabilities();
  assert.deepEqual(emptyCapabilities.emptyState, {
    scenarioLabel: "",
    primary: "",
    secondary: "",
    pathPlaceholder: "",
  });
  assert.deepEqual(emptyCapabilities.agentApplication, null);
  assert.deepEqual(emptyCapabilities.agentApplications, []);

  const app = normalizeProtocolAppBootstrap(readFixture("app_bootstrap.json"));
  assert.equal(app.schemaVersion, FRONTEND_PROTOCOL_SCHEMA_VERSION);
  assert.equal(app.hasActiveWorkspace, true);
  assert.equal(app.shell.surfaces[0].placement, "overlay");
  const failedApp = normalizeProtocolAppBootstrap({
    ...readFixture("app_bootstrap.json"),
    last_failure: {
      code: "configuration_error",
      message: "The application configuration is invalid.",
      retryable: false,
      source: "gui",
      phase: "application_composition",
      kind: "configuration",
      correlation_id: "",
      safe_message: "The application configuration is invalid.",
      exception_type: "",
    },
  });
  assert.equal(failedApp.lastFailure.code, "configuration_error");
  assert.equal(failedApp.lastFailure.safeMessage, "The application configuration is invalid.");

  assert.throws(
    () => normalizeSessionBootstrap({ ...wireSession, eventCursor: 4 }),
    /invalid_session_bootstrap/,
  );
  assert.throws(
    () => normalizeSessionBootstrap({ ...wireSession, schema_version: 1 }),
    /invalid_session_bootstrap:schema_version/,
  );
  const missingCursor = { ...wireSession };
  delete missingCursor.event_cursor;
  assert.throws(
    () => normalizeSessionBootstrap(missingCursor),
    /invalid_session_bootstrap:event_cursor/,
  );

  const camelMode = clone(wireSession.capabilities);
  camelMode.modes[0].commandId = camelMode.modes[0].command_id;
  delete camelMode.modes[0].command_id;
  assert.throws(
    () => normalizeProtocolCapabilities(camelMode),
    /invalid_capability_snapshot/,
  );

  const invalidPlacement = readFixture("app_bootstrap.json");
  invalidPlacement.shell.surfaces[0].placement = "right_panel";
  assert.throws(
    () => normalizeProtocolAppBootstrap(invalidPlacement),
    /invalid_app_bootstrap:shell.surface.placement/,
  );
}
