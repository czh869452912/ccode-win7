import assert from "node:assert/strict";

import {
  buildAppHomeModel,
  formatSessionUpdatedLabel,
} from "../src/session-runtime/app-home-model.js";

export function runAppHomeModelTests() {
  const model = buildAppHomeModel({
    app: {
      hasActiveWorkspace: true,
      activeWorkspace: {
        id: "ws-active",
        label: "parser",
        path: "D:/work/parser",
        exists: true,
      },
      workspaces: [
        {
          id: "ws-active",
          label: "parser",
          path: "D:/work/parser",
          exists: true,
        },
        {
          id: "ws-missing",
          label: "old-driver",
          path: "D:/archive/old-driver",
          exists: false,
        },
      ],
      activatingWorkspace: false,
    },
    sessions: [
      {
        session_id: "sess-active",
        user_goal: "Fix parser recovery",
        current_mode: "build",
        updated_at: "not-a-date",
      },
      {
        session_id: "sess-followup",
        summary_text: "Inspect tokenizer",
        current_mode: "",
        updated_at: "",
      },
    ],
    currentSessionId: "sess-active",
    defaultMode: "explore",
  });

  assert.equal(model.workspace.hasActiveWorkspace, true);
  assert.equal(model.workspace.activeLabel, "parser");
  assert.equal(model.workspace.rows.length, 2);
  assert.equal(model.workspace.rows[0].isActive, true);
  assert.equal(model.workspace.rows[0].status, "active");
  assert.equal(model.workspace.rows[1].status, "missing");
  assert.equal(model.workspace.rows[1].disabled, true);
  assert.equal(model.threads.canCreateThread, true);
  assert.equal(model.threads.count, 2);
  assert.equal(model.threads.rows[0].title, "Fix parser recovery");
  assert.equal(model.threads.rows[0].isActive, true);
  assert.equal(model.threads.rows[0].mode, "build");
  assert.equal(model.threads.rows[0].updated, "not-a-date");
  assert.equal(model.threads.rows[1].mode, "explore");

  const emptyHome = buildAppHomeModel({
    app: {
      hasActiveWorkspace: false,
      activeWorkspace: null,
      workspaces: [
        {
          id: "ws-recent",
          label: "",
          path: "D:/work/demo",
          exists: true,
        },
      ],
      activatingWorkspace: true,
    },
    sessions: [],
    currentSessionId: "",
  });

  assert.equal(emptyHome.workspace.hasActiveWorkspace, false);
  assert.equal(emptyHome.workspace.activeLabel, "No workspace");
  assert.equal(emptyHome.workspace.rows[0].label, "demo");
  assert.equal(emptyHome.workspace.rows[0].disabled, true);
  assert.equal(emptyHome.threads.canCreateThread, false);
  assert.equal(emptyHome.threads.empty, true);

  assert.equal(formatSessionUpdatedLabel(""), "");
  assert.equal(formatSessionUpdatedLabel("not-a-date"), "not-a-date");
}
