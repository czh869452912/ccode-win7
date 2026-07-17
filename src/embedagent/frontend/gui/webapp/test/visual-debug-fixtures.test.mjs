import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  buildComposerFileTreeFixtureAction,
  buildFilePreviewRevealFixtureAction,
  buildInteractionFixtureAction,
  buildSourceControlFixtureAction,
  buildThreadLifecycleFixtureAction,
  buildTimelineFixtureAction,
  installVisualDebugFixtures,
} from "../src/app-runtime/visual-debug-fixtures.js";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const FIXTURES_PATH = path.join(WEBAPP_ROOT, "src", "app-runtime", "visual-debug-fixtures.js");

export function runVisualDebugFixturesTests() {
  const source = fs.readFileSync(FIXTURES_PATH, "utf8");
  assert.equal(source.includes("loadSurfaceSwitchingFixture"), true);
  assert.equal(source.includes("loadPanelOverflowFixture"), true);
  assert.equal(source.includes("loadTerminalSplitFixture"), true);
  assert.equal(source.includes("loadTimelineContextFixture"), true);
  assert.equal(source.includes("visual_timeline_fixture_loaded"), false);
  assert.equal(source.includes("visual_interaction_fixture_loaded"), false);
  assert.equal(source.includes("visual_thread_lifecycle_fixture_loaded"), false);

  const timelineAction = buildTimelineFixtureAction({ currentMode: "build" });
  assert.equal(timelineAction.type, "dev_fixture_timeline");
  assert.equal(timelineAction.sessionId, "visual-debug-timeline");
  assert.equal(timelineAction.snapshot.current_mode, "build");
  assert.equal(timelineAction.thinkingActive, true);
  assert.equal(timelineAction.previews["src/parser.c"].content.includes("line 4 reveal target"), true);
  assert.equal(
    timelineAction.timeline.some((item) => item.data?.matches?.some((match) => match.path === "src/parser.c" && match.line === 4)),
    true,
  );
  assert.equal(
    timelineAction.timeline.some((item) => String(item.content || "").includes("[src/parser.c:4](src/parser.c#L4)")),
    true,
  );
  assert.equal(timelineAction.timeline.some((item) => item.kind === "reasoning"), true);
  assert.equal(timelineAction.timeline.some((item) => item.kind === "compact"), true);
  assert.equal(
    timelineAction.timeline.some((item) => item.kind === "command_result" && item.commandName === "review"),
    true,
  );

  const permissionAction = buildInteractionFixtureAction("permission");
  assert.equal(permissionAction.type, "dev_fixture_interaction");
  assert.equal(permissionAction.permission.kind, "permission");
  assert.equal(permissionAction.userInput, null);

  const userInputAction = buildInteractionFixtureAction("user_input");
  assert.equal(userInputAction.permission, null);
  assert.equal(userInputAction.userInput.kind, "user_input");
  assert.equal(userInputAction.userInput.options.length, 2);

  const threadAction = buildThreadLifecycleFixtureAction();
  assert.equal(threadAction.type, "dev_fixture_threads");
  assert.equal(threadAction.sessionId, "visual-thread-active");
  assert.equal(threadAction.sessions.length, 3);

  const sourceControlAction = buildSourceControlFixtureAction();
  assert.equal(sourceControlAction.type, "dev_fixture_source_control");
  assert.equal(sourceControlAction.status.branch, "feature/t3-toolbar");
  assert.equal(sourceControlAction.status.counts.total, 4);
  assert.equal(sourceControlAction.status.files.length, 4);

  const composerAction = buildComposerFileTreeFixtureAction();
  assert.equal(composerAction.type, "dev_fixture_file_tree");
  assert.equal(composerAction.nodes[0].path, "src");
  assert.equal(composerAction.nodes[0].children.some((node) => node.path === "src/parser.c"), true);

  const revealAction = buildFilePreviewRevealFixtureAction();
  assert.equal(revealAction.type, "dev_fixture_file_preview");
  assert.equal(revealAction.path, "README.md");
  assert.equal(revealAction.revealLine, 4);
  assert.equal(revealAction.preview.content.includes("line 4 reveal target"), true);

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

  const automaticDispatched = [];
  const automaticWindow = {};
  const automaticCleanup = installVisualDebugFixtures({
    windowObject: automaticWindow,
    locationSearch: "?visual_debug=1&visual_fixture=permission",
    dispatch: (action) => automaticDispatched.push(action),
    currentMode: "debug",
  });
  const automaticActivation = automaticDispatched.find(
    (action) => action.type === "session_activated",
  );
  assert.ok(automaticActivation, "permission fixture should activate a session");
  assert.equal(automaticActivation.snapshot.status, "waiting_permission");
  assert.equal(automaticActivation.snapshot.pending_interaction.kind, "permission");
  const automaticDispatchCount = automaticDispatched.length;
  automaticCleanup();
  const repeatedCleanup = installVisualDebugFixtures({
    windowObject: automaticWindow,
    locationSearch: "?visual_debug=1&visual_fixture=permission",
    dispatch: (action) => automaticDispatched.push(action),
    currentMode: "debug",
  });
  assert.equal(automaticDispatched.length, automaticDispatchCount);
  repeatedCleanup();
  assert.equal(
    automaticWindow.__EMBEDAGENT_VISUAL_DEBUG_INITIAL_FIXTURE__,
    "permission",
  );

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
  windowObject.__EMBEDAGENT_VISUAL_DEBUG__.loadSurfaceSwitchingFixture();
  windowObject.__EMBEDAGENT_VISUAL_DEBUG__.loadComposerFileTreeFixture();
  windowObject.__EMBEDAGENT_VISUAL_DEBUG__.loadFilePreviewRevealFixture();
  windowObject.__EMBEDAGENT_VISUAL_DEBUG__.openDiffFixture({
    title: "Debug Diff",
    diff: "--- a/a.c\n+++ b/a.c\n",
    filePath: "a.c",
  });
  assert.deepEqual(
    dispatched.map((action) => action.type),
    [
      "app_shell_bootstrap_loaded",
      "session_activated",
      "file_preview_loaded",
      "step_started",
      "thinking_state",
      "app_shell_bootstrap_loaded",
      "source_control_status_loaded",
      "app_shell_bootstrap_loaded",
      "session_activated",
      "app_shell_bootstrap_loaded",
      "sessions_loaded",
      "session_activated",
      "app_shell_bootstrap_loaded",
      "sessions_loaded",
      "session_activated",
      "app_shell_bootstrap_loaded",
      "file_preview_loaded",
      "workbench_surface_opened",
      "app_shell_bootstrap_loaded",
      "source_control_status_loaded",
      "terminal_snapshot_loaded",
      "workbench_surface_opened",
      "workbench_surface_opened",
      "workbench_surface_opened",
      "workbench_surface_opened",
      "workbench_surface_opened",
      "workbench_surface_opened",
      "workbench_surface_opened",
      "workbench_surface_opened",
      "diff_surface_opened",
      "workbench_surface_activated",
      "app_shell_bootstrap_loaded",
      "file_tree_loaded",
      "app_shell_bootstrap_loaded",
      "file_preview_loaded",
      "workbench_surface_opened",
    ],
  );
  assert.equal(dispatched.some((action) => String(action.type || "").startsWith("visual_")), false);
  const firstActivation = dispatched.find((action) => action.type === "session_activated");
  assert.equal(firstActivation.snapshot.current_mode, "verify");
  assert.equal(opened[0].title, "Debug Diff");
  cleanup();
  assert.equal(windowObject.__EMBEDAGENT_VISUAL_DEBUG__, undefined);
}
