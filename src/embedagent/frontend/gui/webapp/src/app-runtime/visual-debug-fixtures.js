import { normalizeAppBootstrap } from "../app-shell/model.js";
import { createDiffSurfaceState } from "../session-runtime/diff-model.js";

export const VISUAL_SCENARIOS = Object.freeze([
  "empty",
  "session",
  "streaming",
  "tool",
  "interaction",
  "commands",
  "recovery",
  "narrow",
  "optional-terminal",
  "optional-diff",
]);

const WORKSPACE = Object.freeze({
  id: "visual-workspace",
  path: "D:/visual-debug",
  label: "EmbedAgent",
  exists: true,
  created_at: "",
  last_opened_at: "",
});

function command(id, label, group, dispatch, visibleWhen = "always") {
  return {
    id,
    label,
    group,
    dispatch,
    shortcut: "",
    availability: { visible_when: visibleWhen },
    summary: "",
    source_type: "product",
    source_id: "visual_debug",
  };
}

function surface(id, label, placement, rendererKey) {
  return {
    id,
    label,
    placement,
    renderer_key: rendererKey,
    availability: {},
    metadata: {},
  };
}

function shellDescriptor(optional = "") {
  const commands = [
    command("session.new", "New Session", "session", { kind: "session.create" }),
    command("session.select", "Select Session", "session", { kind: "session.select" }),
    command("session.cancel", "Cancel Turn", "session", { kind: "session.cancel" }, "running"),
    command("shell.commands", "Open Commands", "shell", {
      kind: "shell.surface",
      surface_id: "session.command_palette",
    }),
  ];
  const surfaces = [
    surface("session.command_palette", "Commands", "overlay", "command_palette"),
    surface("session.interaction", "Interaction", "overlay", "interaction"),
    surface("session.composer", "Composer", "overlay", "composer"),
  ];
  if (optional === "terminal") {
    commands.push(command("shell.terminal", "Open Terminal", "shell", {
      kind: "shell.surface",
      surface_id: "terminal",
    }, "has_workspace"));
    surfaces.push(surface("terminal", "Terminal", "secondary", "terminal"));
  }
  if (optional === "diff") {
    surfaces.push(surface("diff", "Diff", "secondary", "inline_diff"));
  }
  return {
    schema_version: 1,
    commands,
    surfaces,
    keybindings: [
      { command_id: "shell.commands", keys: "ctrl+p", when: {} },
      { command_id: "session.new", keys: "ctrl+n", when: {} },
      { command_id: "session.cancel", keys: "ctrl+c", when: {} },
    ],
    tool_presentations: [],
    timeline_items: [
      { event_kind: "message", renderer_key: "generic_timeline", priority: 10 },
      { event_kind: "reasoning", renderer_key: "generic_timeline", priority: 20 },
      { event_kind: "tool", renderer_key: "tool", priority: 30 },
      { event_kind: "error", renderer_key: "generic_timeline", priority: 40 },
      { event_kind: "file_reference", renderer_key: "file_reference", priority: 50 },
      { event_kind: "inline_diff", renderer_key: "inline_diff", priority: 60 },
    ],
    interactions: [
      { kind: "permission", renderer_key: "interaction" },
      { kind: "user_input", renderer_key: "interaction" },
    ],
  };
}

export function buildVisualAppBootstrap(optional = "") {
  return normalizeAppBootstrap({
    schema_version: 1,
    app: {
      shell_version: 1,
      product_name: "EmbedAgent",
      protocol: "gui_app_shell_v1",
    },
    workspaces: [WORKSPACE],
    active_workspace: WORKSPACE,
    has_active_workspace: true,
    shell: shellDescriptor(optional),
    settings: { confirm_workspace_switch: true, show_diagnostics_badge: true },
    diagnostics: {},
    last_error: "",
  });
}

function sessionSnapshot(sessionId, mode, patch = {}) {
  return {
    session_id: sessionId,
    status: "idle",
    current_mode: mode || "explore",
    pending_interaction_valid: false,
    workflow_state: {},
    context_usage: { used_tokens: 3200, max_tokens: 16000 },
    ...patch,
  };
}

function sessionRows() {
  return [
    {
      id: "visual-user",
      kind: "user",
      content: "Review parser recovery and verify the focused change.",
      turnId: "visual-turn",
    },
    {
      id: "visual-reasoning",
      kind: "reasoning",
      content: "Inspect the recovery branch, then run the focused checks.",
      turnId: "visual-turn",
      stepId: "visual-step",
      stepIndex: 1,
    },
    {
      id: "visual-assistant",
      kind: "assistant",
      content: "The recovery branch is isolated and the focused checks pass.",
      turnId: "visual-turn",
      stepId: "visual-step",
      stepIndex: 1,
    },
  ];
}

function toolRows(status = "success") {
  return [
    sessionRows()[0],
    {
      id: "visual-tool",
      kind: "tool",
      toolName: "edit_file",
      label: status === "running" ? "Editing parser.c" : "Edited parser.c",
      toolTitle: "Changed files",
      itemType: "file_change",
      requestKind: "file-change",
      toolLifecycleStatus: status === "running" ? "in_progress" : "completed",
      status,
      arguments: { path: "src/parser.c" },
      data: {
        path: "src/parser.c",
        diff_preview: "--- a/src/parser.c\n+++ b/src/parser.c\n@@ -1 +1 @@\n-return 0;\n+return 1;\n",
      },
      turnId: "visual-turn",
      stepId: "visual-step",
      stepIndex: 1,
    },
  ];
}

function activate(dispatch, { id, mode, activities = [], snapshot = {}, historyIntegrity = null }) {
  dispatch({
    type: "sessions_loaded",
    sessions: [
      { session_id: id, user_goal: "Review parser recovery", current_mode: mode },
      { session_id: "visual-follow-up", user_goal: "Verify offline bundle", current_mode: "verify" },
    ],
  });
  dispatch({
    type: "session_activated",
    sessionId: id,
    snapshot: sessionSnapshot(id, mode, snapshot),
    activities,
    historyIntegrity,
  });
}

export function buildInteractionFixtureAction(kind = "permission") {
  const interaction = kind === "user_input"
    ? {
        interaction_id: "visual-input",
        request_id: "visual-input",
        kind: "user_input",
        tool_name: "ask_user",
        question: "Which recovery behavior should be preserved?",
        options: [{ index: 1, text: "Strict" }, { index: 2, text: "Permissive" }],
      }
    : {
        interaction_id: "visual-permission",
        kind: "permission",
        tool_name: "edit_file",
        category: "workspace_write",
        reason: "Allow editing src/parser.c",
        details: { path: "src/parser.c" },
      };
  return { type: "visual_interaction", interaction };
}

function optionalKind(scenarioId) {
  if (scenarioId === "optional-terminal") return "terminal";
  if (scenarioId === "optional-diff") return "diff";
  return "";
}

export function loadVisualScenario(dispatch, scenarioId, currentMode = "explore") {
  if (typeof dispatch !== "function") return false;
  const id = String(scenarioId || "").trim();
  if (!VISUAL_SCENARIOS.includes(id)) return false;
  dispatch({ type: "app_shell_bootstrap_loaded", bootstrap: buildVisualAppBootstrap(optionalKind(id)) });
  if (id === "empty") return true;

  const sessionId = `visual-${id}`;
  let activities = sessionRows();
  let snapshot = {};
  let historyIntegrity = null;
  if (id === "streaming") {
    activities = toolRows("running");
    snapshot = { status: "running" };
  } else if (id === "tool") {
    activities = toolRows();
  } else if (id === "interaction") {
    const { interaction } = buildInteractionFixtureAction("permission");
    activities = [sessionRows()[0]];
    snapshot = {
      status: "waiting_permission",
      pending_interaction_valid: true,
      pending_interaction: interaction,
    };
  } else if (id === "recovery") {
    historyIntegrity = {
      status: "partial",
      restore_stop_reason: "truncated_tail",
      last_recovered_sequence: 12,
    };
  }
  activate(dispatch, {
    id: sessionId,
    mode: currentMode,
    activities,
    snapshot,
    historyIntegrity,
  });

  if (id === "streaming") {
    dispatch({ type: "step_started", turnId: "visual-turn", stepId: "visual-step", stepIndex: 1 });
    dispatch({ type: "thinking_state", active: true });
  } else if (id === "commands") {
    dispatch({ type: "command_palette_opened" });
  } else if (id === "optional-terminal") {
    dispatch({
      type: "terminal_snapshot_loaded",
      snapshot: {
        session_id: sessionId,
        terminal_id: "visual-terminal",
        status: "running",
        history: "D:/visual-debug> uv run pytest tests/\n12 passed\n",
        cols: 100,
        rows: 30,
      },
    });
    dispatch({
      type: "contribution_opened",
      kind: "terminal",
      label: "Terminal",
      rendererKey: "terminal",
      resourceId: "visual-terminal",
      terminalId: "visual-terminal",
      terminalIds: ["visual-terminal"],
      activeTerminalId: "visual-terminal",
    });
  } else if (id === "optional-diff") {
    dispatch({
      type: "diff_surface_opened",
      diffSurface: createDiffSurfaceState({
        title: "src/parser.c",
        diff: "--- a/src/parser.c\n+++ b/src/parser.c\n@@ -1 +1 @@\n-return 0;\n+return 1;\n",
        source: "visual-debug",
        filePath: "src/parser.c",
      }),
    });
  }
  return true;
}

export function installVisualDebugFixtures({
  windowObject,
  locationSearch = "",
  dispatch,
  currentMode = "explore",
} = {}) {
  if (!windowObject || typeof dispatch !== "function") return undefined;
  const params = new URLSearchParams(locationSearch || "");
  if (params.get("visual_debug") !== "1") return undefined;
  const fixtures = Object.freeze({
    scenarioIds: VISUAL_SCENARIOS,
    loadScenario: (scenarioId) => loadVisualScenario(dispatch, scenarioId, currentMode),
  });
  windowObject.__EMBEDAGENT_VISUAL_DEBUG__ = fixtures;
  const initialFixture = params.get("visual_fixture");
  if (initialFixture && !windowObject.__EMBEDAGENT_VISUAL_DEBUG_INITIAL_FIXTURE__) {
    if (fixtures.loadScenario(initialFixture)) {
      windowObject.__EMBEDAGENT_VISUAL_DEBUG_INITIAL_FIXTURE__ = initialFixture;
    }
  }
  return () => {
    if (windowObject.__EMBEDAGENT_VISUAL_DEBUG__ === fixtures) {
      delete windowObject.__EMBEDAGENT_VISUAL_DEBUG__;
    }
  };
}
