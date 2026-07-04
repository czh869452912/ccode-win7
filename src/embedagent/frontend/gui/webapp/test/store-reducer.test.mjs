import assert from "node:assert/strict";

import { initialState, reducer } from "../src/store.js";

export function runStoreReducerTests() {
  const limitedState = {
    ...initialState,
    terminationReason: "max_turns",
    turnsUsed: 8,
    maxTurns: 8,
  };

  const completedState = reducer(limitedState, {
    type: "turn_ended",
    terminationReason: "completed",
    turnsUsed: 9,
    maxTurns: null,
  });

  assert.equal(completedState.terminationReason, "completed");
  assert.equal(completedState.turnsUsed, 9);
  assert.equal(completedState.maxTurns, null);

  const nextUserState = reducer(limitedState, {
    type: "local_user_message",
    text: "continue",
  });

  assert.equal(nextUserState.terminationReason, "");
  assert.equal(nextUserState.maxTurns, null);

  const capabilityState = reducer(initialState, {
    type: "session_capabilities_loaded",
    capabilities: {
      commands: [
        {
          name: "help",
          usage: "/help",
          active: true,
        },
      ],
    },
  });

  assert.equal(capabilityState.sessionCapabilities.commands[0].usage, "/help");

  const restoredWorkbenchState = {
    ...initialState,
    workbench: {
      ...initialState.workbench,
      activeSessionKey: "sess-1",
      rightPanel: {
        ...initialState.workbench.rightPanel,
        surfaces: [
          {
            id: "right:preview:http://127.0.0.1:5173",
            placement: "right",
            kind: "preview",
            title: "Preview",
            resourceId: "http://127.0.0.1:5173",
          },
          {
            id: "right:file:src/main.c",
            placement: "right",
            kind: "file",
            title: "main.c",
            resourceId: "src/main.c",
            filePath: "src/main.c",
          },
          {
            id: "right:source_control",
            placement: "right",
            kind: "source_control",
            title: "Source Control",
          },
        ],
        activeKind: "source_control",
        activeSurfaceId: "right:source_control",
      },
      bottomDrawer: {
        ...initialState.workbench.bottomDrawer,
        open: true,
        activeKind: "terminal",
      },
      surfacesBySession: {
        "sess-1": {
          right: [
            {
              id: "right:preview:http://127.0.0.1:5173",
              placement: "right",
              kind: "preview",
              title: "Preview",
              resourceId: "http://127.0.0.1:5173",
            },
            {
              id: "right:file:src/main.c",
              placement: "right",
              kind: "file",
              title: "main.c",
              resourceId: "src/main.c",
              filePath: "src/main.c",
            },
          ],
          activeRightSurfaceId: "right:preview:http://127.0.0.1:5173",
        },
      },
    },
  };

  const appLimitedState = reducer(restoredWorkbenchState, {
    type: "app_bootstrap_loaded",
    bootstrap: {
      capabilities: {
        surfaces: {
          right_panel: ["files"],
          bottom_drawer: ["logs"],
        },
      },
    },
  });

  const workspacePathEditingState = reducer(restoredWorkbenchState, {
    type: "app_shell_workspace_path_changed",
    value: "D:/work/other",
  });
  assert.deepEqual(
    workspacePathEditingState.workbench.rightPanel.surfaces.map((surface) => surface.kind),
    ["preview", "file", "source_control"],
  );
  assert.equal(workspacePathEditingState.app.workspacePathInput, "D:/work/other");

  assert.deepEqual(
    appLimitedState.workbench.rightPanel.surfaces.map((surface) => surface.kind),
    ["file"],
  );
  assert.equal(appLimitedState.workbench.rightPanel.activeSurfaceId, "right:file:src/main.c");
  assert.deepEqual(
    appLimitedState.workbench.surfacesBySession["sess-1"].right.map((surface) => surface.kind),
    ["file"],
  );
  assert.equal(appLimitedState.workbench.surfacesBySession["sess-1"].activeRightSurfaceId, "right:file:src/main.c");
  assert.equal(appLimitedState.workbench.bottomDrawer.open, true);
  assert.equal(appLimitedState.workbench.bottomDrawer.activeKind, "logs");
}
