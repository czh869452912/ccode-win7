import assert from "node:assert/strict";

import {
  buildThreadLifecycleActions,
  buildAppHomeModel,
  formatSessionUpdatedLabel,
} from "../src/session-runtime/app-home-model.js";

export function runAppHomeModelTests() {
  const model = buildAppHomeModel({
    app: {
      app: {
        productName: "Python Agent Workbench",
      },
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
      capabilities: {
        home: {
          workspace: {
            sectionTitle: "Projects",
            inactiveLabel: "No project",
            inactivePath: "Choose a project",
            pathPlaceholder: "Project path",
            openLabel: "Open Project",
            openAriaLabel: "Open project",
            recentsLabel: "Recent projects",
            missingPathLabel: "Missing project path",
            removeLabel: "Forget",
          },
          threads: {
            sectionTitle: "Runs",
            newLabel: "Start",
            emptyTitle: "No runs",
            emptyBody: "Start a run for this project.",
            activeLabel: "current",
            actionsLabelPrefix: "Run actions for",
          },
        },
        emptyState: {
          scenarioLabel: "Python workspace",
          primary: "Open a Python project",
          secondary: "Choose a Python project folder.",
          pathPlaceholder: "Python project path",
        },
      },
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
      {
        session_id: "sess-renamed",
        title: "Manual title",
        thread: { title: "Thread metadata title" },
        user_goal: "Should not win",
        current_mode: "verify",
        updated_at: "",
      },
    ],
    currentSessionId: "sess-active",
    defaultMode: "explore",
    threadLifecycleCapabilities: {
      actions: [
        {
          id: "rename",
          label: "Retitle",
          capability: "rename",
          order: 10,
          promptTitle: "Retitle prompt",
        },
        { id: "archive", label: "Hide", capability: "archive", order: 20, danger: true },
      ],
    },
  });

  assert.equal(model.workspace.hasActiveWorkspace, true);
  assert.equal(model.productName, "Python Agent Workbench");
  assert.equal(model.workspace.activeLabel, "parser");
  assert.equal(model.workspace.copy.sectionTitle, "Projects");
  assert.equal(model.workspace.copy.pathPlaceholder, "Project path");
  assert.equal(model.workspace.copy.openLabel, "Open Project");
  assert.equal(model.workspace.copy.missingPathLabel, "Missing project path");
  assert.equal(model.workspace.rows.length, 2);
  assert.equal(model.workspace.rows[0].isActive, true);
  assert.equal(model.workspace.rows[0].status, "active");
  assert.equal(model.workspace.rows[1].status, "missing");
  assert.equal(model.workspace.rows[1].pathLabel, "Missing project path");
  assert.equal(model.workspace.rows[1].disabled, true);
  assert.equal(model.threads.canCreateThread, true);
  assert.equal(model.threads.copy.sectionTitle, "Runs");
  assert.equal(model.threads.copy.activeLabel, "current");
  assert.equal(model.threads.count, 3);
  assert.equal(model.threads.rows[0].title, "Fix parser recovery");
  assert.equal(model.threads.rows[0].isActive, true);
  assert.equal(model.threads.rows[0].mode, "build");
  assert.equal(model.threads.rows[0].updated, "not-a-date");
  assert.deepEqual(
    model.threads.rows[0].actions.map((action) => action.id),
    ["rename", "archive"],
  );
  assert.equal(model.threads.rows[0].actions[0].label, "Retitle");
  assert.equal(model.threads.rows[0].actions[0].promptTitle, "Retitle prompt");
  assert.equal(model.threads.rows[0].actions[0].enabled, true);
  assert.equal(model.threads.rows[0].actions[0].reason, "");
  assert.equal(model.threads.rows[1].mode, "explore");
  assert.equal(model.threads.rows[2].title, "Thread metadata title");
  assert.equal(model.threads.rows[2].mode, "verify");

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
      capabilities: {
        home: {
          workspace: {
            inactiveLabel: "No project",
            inactivePath: "Choose a project",
            pathPlaceholder: "Project path",
            openLabel: "Open Project",
            recentsLabel: "Recent projects",
            missingPathLabel: "Missing project path",
          },
          threads: {
            emptyTitle: "No runs",
            emptyBody: "Start a run for this project.",
          },
        },
        emptyState: {
          scenarioLabel: "Python workspace",
          primary: "Open a Python project",
          secondary: "Choose a Python project folder.",
          pathPlaceholder: "Python project path",
        },
      },
    },
    sessions: [],
    currentSessionId: "",
  });

  assert.equal(emptyHome.workspace.hasActiveWorkspace, false);
  assert.equal(emptyHome.workspace.activeLabel, "No project");
  assert.equal(emptyHome.workspace.activePath, "Choose a project");
  assert.equal(emptyHome.workspace.rows[0].label, "demo");
  assert.equal(emptyHome.workspace.rows[0].disabled, true);
  assert.equal(emptyHome.threads.canCreateThread, false);
  assert.equal(emptyHome.threads.empty, true);

  const enabledActions = buildThreadLifecycleActions(
    { session_id: "sess-active" },
    {
      actions: [
        { id: "fork", label: "Clone", capability: "fork", order: 20 },
        { id: "rename", label: "Retitle", capability: "rename", order: 10 },
        { id: "archive", label: "Hide", capability: "archive", order: 30, enabled: false },
      ],
    },
  );
  assert.deepEqual(
    enabledActions.map((action) => action.capability),
    ["rename", "fork", "archive"],
  );
  assert.equal(enabledActions[0].label, "Retitle");
  assert.equal(enabledActions[0].enabled, true);
  assert.equal(enabledActions[1].enabled, true);
  assert.equal(enabledActions[2].enabled, false);
  assert.equal(enabledActions[2].reason, "backend_not_available");

  const missingSessionActions = buildThreadLifecycleActions(null, {
    actions: [{ id: "rename", label: "Retitle", capability: "rename" }],
  });
  assert.equal(missingSessionActions[0].enabled, false);
  assert.equal(missingSessionActions[0].reason, "missing_session");

  assert.equal(formatSessionUpdatedLabel(""), "");
  assert.equal(formatSessionUpdatedLabel("not-a-date"), "not-a-date");
}
