import assert from "node:assert/strict";

import { initialState, reducer } from "../src/store.js";
import { buildContributionModel } from "../src/components/contributions/contribution-model.js";

function stateWithSession(patch = {}) {
  return {
    ...initialState,
    app: {
      ...initialState.app,
      hasActiveWorkspace: true,
      capabilities: {
        ...initialState.app.capabilities,
        workbenchCommands: [
          {
            id: "shell.files",
            label: "Files",
            visibleWhen: "always",
            dispatch: { kind: "shell.surface", surface_id: "files" },
          },
        ],
      },
    },
    thread: { ...initialState.thread, currentSessionId: "session-a" },
    snapshot: { session_id: "session-a", status: "idle", ...patch },
  };
}

export function runContributionModelTests() {
  let desktop = stateWithSession();
  desktop = reducer(desktop, {
    type: "contribution_opened",
    kind: "files",
    label: "Files",
    rendererKey: "file_reference",
  });
  const desktopModel = buildContributionModel(desktop, { width: 1440 });
  assert.equal(desktopModel.centerColumn.maxWidth, 860);
  assert.deepEqual(desktopModel.contribution, { mode: "overlay", count: 1 });
  assert.equal(desktopModel.composer.mode, "command-ready");
  assert.equal(desktopModel.timeline.density, "compact");
  assert.deepEqual(desktopModel.commandPalette.availableSurfaceCommands, ["shell.files"]);

  const running = buildContributionModel(stateWithSession({ status: "running" }), { width: 900 });
  assert.equal(running.composer.mode, "running");
  assert.deepEqual(running.contribution, { mode: "closed", count: 0 });

  const mobile = buildContributionModel({
    ...desktop,
    snapshot: {
      ...desktop.snapshot,
      status: "waiting_user_input",
      pending_interaction_valid: true,
      pending_interaction: { interaction_id: "input-1", kind: "user_input" },
    },
  }, { width: 390 });
  assert.equal(mobile.centerColumn.maxWidth, 390);
  assert.equal(mobile.contribution.mode, "sheet");
  assert.equal(mobile.composer.mode, "interaction");
}
