import assert from "node:assert/strict";

import {
  VISUAL_SCENARIOS,
  buildInteractionFixtureAction,
  buildVisualAppBootstrap,
  installVisualDebugFixtures,
  loadVisualScenario,
} from "../src/app-runtime/visual-debug-fixtures.js";

export function runVisualDebugFixturesTests() {
  assert.deepEqual(VISUAL_SCENARIOS, [
    "empty", "session", "streaming", "tool", "interaction", "commands",
    "recovery", "narrow", "optional-terminal", "optional-diff",
  ]);

  const core = buildVisualAppBootstrap();
  assert.equal(core.bootstrapLoaded, true);
  assert.equal(core.shell.surfaces.some((item) => item.placement === "secondary"), false);
  const terminal = buildVisualAppBootstrap("terminal");
  assert.deepEqual(
    terminal.shell.surfaces.filter((item) => item.placement === "secondary").map((item) => item.id),
    ["terminal"],
  );
  const diff = buildVisualAppBootstrap("diff");
  assert.deepEqual(
    diff.shell.surfaces.filter((item) => item.placement === "secondary").map((item) => item.id),
    ["diff"],
  );

  const permission = buildInteractionFixtureAction();
  assert.equal(permission.interaction.kind, "permission");
  const input = buildInteractionFixtureAction("user_input");
  assert.equal(input.interaction.options.length, 2);

  for (const scenario of VISUAL_SCENARIOS) {
    const actions = [];
    assert.equal(loadVisualScenario((action) => actions.push(action), scenario, "build"), true);
    assert.equal(actions[0].type, "app_shell_bootstrap_loaded");
    const optional = actions.filter((action) => action.type === "contribution_opened");
    if (scenario === "optional-terminal") assert.equal(optional[0].kind, "terminal");
    else assert.equal(optional.length, 0);
    if (scenario === "optional-diff") {
      assert.equal(actions.some((action) => action.type === "diff_surface_opened"), true);
    }
  }
  assert.equal(loadVisualScenario(() => {}, "retired-panel-fixture"), false);

  const disabledWindow = {};
  assert.equal(installVisualDebugFixtures({
    windowObject: disabledWindow,
    locationSearch: "?visual_debug=0",
    dispatch: () => {},
  }), undefined);

  const actions = [];
  const windowObject = {};
  const cleanup = installVisualDebugFixtures({
    windowObject,
    locationSearch: "?visual_debug=1&visual_fixture=session",
    dispatch: (action) => actions.push(action),
    currentMode: "verify",
  });
  assert.equal(typeof cleanup, "function");
  assert.equal(typeof windowObject.__EMBEDAGENT_VISUAL_DEBUG__.loadScenario, "function");
  assert.equal(actions.some((action) => action.type === "session_activated"), true);
  assert.equal(
    actions.find((action) => action.type === "session_activated").snapshot.current_mode,
    "verify",
  );
  cleanup();
  assert.equal(windowObject.__EMBEDAGENT_VISUAL_DEBUG__, undefined);
}
