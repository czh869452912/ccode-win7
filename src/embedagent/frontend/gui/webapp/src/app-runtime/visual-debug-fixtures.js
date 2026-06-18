export function buildTimelineFixtureAction({ currentMode = "explore" } = {}) {
  return {
    type: "visual_timeline_fixture_loaded",
    sessionId: "visual-debug-timeline",
    inspectorTab: "tasks",
    timeline: [
      {
        id: "visual-user-1",
        kind: "user",
        content: "Review parser recovery and show the work.",
        turnId: "visual-turn-1",
      },
      {
        id: "visual-compact-1",
        kind: "compact",
        content: "Earlier setup turns were compacted.",
        summarizedTurns: 5,
        recentTurns: 2,
        approxTokensAfter: 3600,
        turnId: "visual-turn-1",
      },
      {
        id: "visual-reasoning-1",
        kind: "reasoning",
        content: "Inspect the parser recovery path, then verify the changed diagnostic flow.",
        streaming: false,
        turnId: "visual-turn-1",
        stepId: "visual-step-1",
        stepIndex: 1,
      },
      {
        id: "visual-read-1",
        kind: "tool",
        toolName: "read_file",
        label: "Read File",
        status: "success",
        arguments: { path: "src/parser.c" },
        data: { summary: "Read parser entry point." },
        turnId: "visual-turn-1",
        stepId: "visual-step-1",
        stepIndex: 1,
      },
      {
        id: "visual-edit-1",
        kind: "tool",
        toolName: "edit_file",
        label: "Edit File",
        status: "success",
        arguments: { path: "src/parser.c" },
        data: {
          path: "src/parser.c",
          diff_preview: "--- a/src/parser.c\n+++ b/src/parser.c\n@@ -1 +1,2 @@\n-int parse(void) { return 0; }\n+int parse(void) { return 1; }\n+int parse_extra(void) { return 2; }\n",
        },
        turnId: "visual-turn-1",
        stepId: "visual-step-1",
        stepIndex: 1,
      },
      {
        id: "visual-review-result",
        kind: "command_result",
        commandName: "review",
        success: false,
        content: "Review found one follow-up item.",
        data: {
          review: {
            findings: [
              {
                id: "visual-finding-1",
                severity: "medium",
                priority: 2,
                title: "Add EOF recovery fixture",
                body: "The parser recovery path is not covered by a fixture yet.",
                file: "tests/parser_recovery_test.c",
                line: 18,
              },
            ],
            residual_risks: ["Visual fixture only checks rendering, not parser behavior."],
          },
        },
        turnId: "visual-turn-1",
      },
      {
        id: "visual-assistant-1",
        kind: "assistant",
        content: "Parser recovery was updated and review found one fixture follow-up.",
        turnId: "visual-turn-1",
        stepId: "visual-step-1",
        stepIndex: 1,
      },
      {
        id: "visual-user-2",
        kind: "user",
        content: "Think through the next verification step.",
        turnId: "visual-turn-2",
      },
    ],
    snapshot: {
      session_id: "visual-debug-timeline",
      status: "running",
      current_mode: currentMode || "explore",
      pending_interaction_valid: false,
    },
    activeTurnId: "visual-turn-2",
    activeStepId: "visual-step-2",
    activeStepIndex: 1,
    thinkingActive: true,
  };
}

export function buildLongTimelineFixtureAction({ currentMode = "explore", turnCount = 36 } = {}) {
  const timeline = [];
  for (let index = 0; index < turnCount; index += 1) {
    const turnId = `visual-long-turn-${index + 1}`;
    const stepId = `visual-long-step-${index + 1}`;
    timeline.push({
      id: `visual-long-user-${index + 1}`,
      kind: "user",
      content: `Inspect long timeline item ${index + 1}.`,
      turnId,
    });
    timeline.push({
      id: `visual-long-tool-${index + 1}`,
      kind: "tool",
      toolName: index % 2 === 0 ? "read_file" : "grep_text",
      label: index % 2 === 0 ? "Read File" : "Search",
      status: "success",
      arguments: index % 2 === 0
        ? { path: `src/file_${index + 1}.c` }
        : { pattern: "parse", path: "src" },
      data: index % 2 === 0
        ? { path: `src/file_${index + 1}.c`, content_preview: "int main(void);" }
        : { pattern: "parse", match_count: 1, matches: [{ path: "src/parser.c", line: index + 1, text: "parse();" }] },
      turnId,
      stepId,
      stepIndex: 1,
    });
    timeline.push({
      id: `visual-long-assistant-${index + 1}`,
      kind: "assistant",
      content: `Long timeline item ${index + 1} completed.`,
      turnId,
      stepId,
      stepIndex: 1,
    });
  }
  return {
    type: "visual_timeline_fixture_loaded",
    sessionId: "visual-debug-long-timeline",
    inspectorTab: "tasks",
    timeline,
    snapshot: {
      session_id: "visual-debug-long-timeline",
      status: "idle",
      current_mode: currentMode || "explore",
      pending_interaction_valid: false,
    },
    activeTurnId: "",
    activeStepId: "",
    activeStepIndex: 0,
    thinkingActive: false,
  };
}

export function buildInteractionFixtureAction(kind = "permission") {
  const permission =
    kind === "permission"
      ? {
          interaction_id: "visual-permission-1",
          kind: "permission",
          tool_name: "edit_file",
          category: "workspace_write",
          reason: "Allow editing src/parser.c",
          details: { path: "src/parser.c" },
          turn_id: "visual-turn-1",
          step_id: "visual-step-2",
          step_index: 2,
        }
      : null;
  const userInput =
    kind === "user_input"
      ? {
          interaction_id: "visual-input-1",
          request_id: "visual-input-1",
          kind: "user_input",
          tool_name: "ask_user",
          question: "Which parser behavior should be preserved?",
          options: [
            { index: 1, text: "Keep strict parsing" },
            { index: 2, text: "Accept empty input" },
          ],
          turn_id: "visual-turn-1",
          step_id: "visual-step-2",
          step_index: 2,
        }
      : null;
  return {
    type: "visual_interaction_fixture_loaded",
    sessionId: "visual-debug-interaction",
    permission,
    userInput,
  };
}

export function buildThreadLifecycleFixtureAction() {
  return {
    type: "visual_thread_lifecycle_fixture_loaded",
    sessionId: "visual-thread-active",
    sessions: [
      {
        session_id: "visual-thread-active",
        user_goal: "Fix parser recovery",
        current_mode: "build",
        updated_at: "2026-06-16T09:30:00Z",
      },
      {
        session_id: "visual-thread-spec",
        summary_text: "Plan tokenizer cleanup",
        current_mode: "spec",
        updated_at: "2026-06-15T17:10:00Z",
      },
      {
        session_id: "visual-thread-verify",
        user_goal: "Verify offline bundle smoke",
        current_mode: "verify",
        updated_at: "2026-06-14T08:00:00Z",
      },
    ],
  };
}

export function installVisualDebugFixtures({
  windowObject,
  locationSearch = "",
  dispatch,
  openDiffFixture,
  currentMode = "explore",
} = {}) {
  if (!windowObject || typeof dispatch !== "function") return undefined;
  const params = new URLSearchParams(locationSearch || "");
  if (params.get("visual_debug") !== "1") return undefined;
  windowObject.__EMBEDAGENT_VISUAL_DEBUG__ = {
    openDiffFixture({ title = "Visual Debug Diff", diff = "", filePath = "" } = {}) {
      if (typeof openDiffFixture === "function") {
        openDiffFixture({ title, diff, filePath });
      }
    },
    loadTimelineFixture() {
      dispatch(buildTimelineFixtureAction({ currentMode }));
    },
    loadLongTimelineFixture() {
      dispatch(buildLongTimelineFixtureAction({ currentMode }));
    },
    loadInteractionFixture(kind = "permission") {
      dispatch(buildInteractionFixtureAction(kind));
    },
    loadThreadLifecycleFixture() {
      dispatch(buildThreadLifecycleFixtureAction());
    },
  };
  return () => {
    if (windowObject.__EMBEDAGENT_VISUAL_DEBUG__) {
      delete windowObject.__EMBEDAGENT_VISUAL_DEBUG__;
    }
  };
}
