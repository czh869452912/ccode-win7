import assert from "node:assert/strict";

import { createComposerState } from "../src/composer/composer-state.js";
import { selectAgentShellView } from "../src/client-runtime/shell-selectors.js";

export function runShellSelectorTests() {
  const composer = createComposerState();
  composer.activeDraftKey = "session:s-1";
  composer.draftsByKey["session:s-1"] = { draft: "hello" };
  const state = {
      thread: { sessions: [{ session_id: "s-1" }], currentSessionId: "s-1" },
      snapshot: { session_id: "s-1", current_mode: "build", status: "idle" },
      composer,
      app: { capabilities: { shell: { surfaces: [] } }, hasActiveWorkspace: true },
      sessionCapabilities: { modeCatalog: { build: { id: "build", label: "Build" } } },
    };
  const view = selectAgentShellView(
    state,
    { activityRuntime: { timelineRows: [{ id: "a-1", kind: "assistant" }] } },
  );

  assert.deepEqual(Object.keys(view).sort(), [
    "composer",
    "connection",
    "interaction",
    "modes",
    "sessions",
    "shell",
    "status",
    "timeline",
    "workflow",
  ]);
  assert.equal(view.timeline.items.length, 1);
  assert.equal(view.composer.draft, "hello");
  assert.equal(view.composer.canSubmit, true);
  assert.equal("terminal" in view, false);
  assert.equal("sourceControl" in view, false);
  assert.equal(Object.isFrozen(view), true);
  assert.equal(Object.isFrozen(view.timeline.items), true);
  assert.equal("protocol" in view, false);
  assert.equal("dispatch" in view, false);
  assert.equal(Object.isFrozen(state), false);
  assert.equal(Object.isFrozen(state.sessionCapabilities.modeCatalog), false);
  assert.equal(Object.isFrozen(state.sessionCapabilities.modeCatalog.build), false);
}
