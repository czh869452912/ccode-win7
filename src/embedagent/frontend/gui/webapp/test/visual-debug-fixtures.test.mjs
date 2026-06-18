import assert from "node:assert/strict";

import {
  buildInteractionFixtureAction,
  buildSourceControlFixtureAction,
  buildThreadLifecycleFixtureAction,
  buildTimelineFixtureAction,
  installVisualDebugFixtures,
} from "../src/app-runtime/visual-debug-fixtures.js";

export function runVisualDebugFixturesTests() {
  const timelineAction = buildTimelineFixtureAction({ currentMode: "build" });
  assert.equal(timelineAction.type, "visual_timeline_fixture_loaded");
  assert.equal(timelineAction.sessionId, "visual-debug-timeline");
  assert.equal(timelineAction.snapshot.current_mode, "build");
  assert.equal(timelineAction.thinkingActive, true);
  assert.equal(timelineAction.timeline.some((item) => item.kind === "reasoning"), true);
  assert.equal(timelineAction.timeline.some((item) => item.kind === "compact"), true);
  assert.equal(
    timelineAction.timeline.some((item) => item.kind === "command_result" && item.commandName === "review"),
    true,
  );

  const permissionAction = buildInteractionFixtureAction("permission");
  assert.equal(permissionAction.type, "visual_interaction_fixture_loaded");
  assert.equal(permissionAction.permission.kind, "permission");
  assert.equal(permissionAction.userInput, null);

  const userInputAction = buildInteractionFixtureAction("user_input");
  assert.equal(userInputAction.permission, null);
  assert.equal(userInputAction.userInput.kind, "user_input");
  assert.equal(userInputAction.userInput.options.length, 2);

  const threadAction = buildThreadLifecycleFixtureAction();
  assert.equal(threadAction.type, "visual_thread_lifecycle_fixture_loaded");
  assert.equal(threadAction.sessionId, "visual-thread-active");
  assert.equal(threadAction.sessions.length, 3);

  const sourceControlAction = buildSourceControlFixtureAction();
  assert.equal(sourceControlAction.type, "visual_source_control_fixture_loaded");
  assert.equal(sourceControlAction.status.branch, "feature/t3-toolbar");
  assert.equal(sourceControlAction.status.counts.total, 4);
  assert.equal(sourceControlAction.status.files.length, 4);

  const skippedWindow = {};
  const skippedCleanup = installVisualDebugFixtures({
    windowObject: skippedWindow,
    locationSearch: "?visual_debug=0",
    dispatch: () => {
      throw new Error("dispatch should not run while disabled");
    },
    openDiffFixture: () => {},
    currentMode: "build",
  });
  assert.equal(skippedCleanup, undefined);
  assert.equal(skippedWindow.__EMBEDAGENT_VISUAL_DEBUG__, undefined);

  const dispatched = [];
  const opened = [];
  const windowObject = {};
  const cleanup = installVisualDebugFixtures({
    windowObject,
    locationSearch: "?visual_debug=1",
    dispatch: (action) => dispatched.push(action),
    openDiffFixture: (payload) => opened.push(payload),
    currentMode: "verify",
  });
  assert.equal(typeof cleanup, "function");
  assert.equal(typeof windowObject.__EMBEDAGENT_VISUAL_DEBUG__.loadTimelineFixture, "function");
  windowObject.__EMBEDAGENT_VISUAL_DEBUG__.loadTimelineFixture();
  windowObject.__EMBEDAGENT_VISUAL_DEBUG__.loadSourceControlFixture();
  windowObject.__EMBEDAGENT_VISUAL_DEBUG__.loadInteractionFixture("user_input");
  windowObject.__EMBEDAGENT_VISUAL_DEBUG__.loadThreadLifecycleFixture();
  windowObject.__EMBEDAGENT_VISUAL_DEBUG__.openDiffFixture({
    title: "Debug Diff",
    diff: "--- a/a.c\n+++ b/a.c\n",
    filePath: "a.c",
  });
  assert.deepEqual(
    dispatched.map((action) => action.type),
    [
      "visual_timeline_fixture_loaded",
      "visual_source_control_fixture_loaded",
      "visual_interaction_fixture_loaded",
      "visual_thread_lifecycle_fixture_loaded",
    ],
  );
  assert.equal(dispatched[0].snapshot.current_mode, "verify");
  assert.equal(opened[0].title, "Debug Diff");
  cleanup();
  assert.equal(windowObject.__EMBEDAGENT_VISUAL_DEBUG__, undefined);
}
