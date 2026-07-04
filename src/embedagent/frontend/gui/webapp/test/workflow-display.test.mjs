import assert from "node:assert/strict";

import {
  buildWorkflowRuntimeRows,
  workflowTaskSummary,
} from "../src/session-runtime/workflow-display.js";

export function runWorkflowDisplayTests() {
  assert.deepEqual(buildWorkflowRuntimeRows({ status: "idle" }), []);
  assert.equal(workflowTaskSummary({ status: "idle" }), "");

  const legacySnapshotRows = buildWorkflowRuntimeRows({
    current_phase: "repair",
    discipline_profile: "lite-spec-tdd",
    current_activity: "Fix parser failure",
  });
  assert.deepEqual(legacySnapshotRows, []);

  const cWorkflowRows = buildWorkflowRuntimeRows({
    workflow: {
      metadata: {
        display_rows: [
          { key: "current_phase", label_key: "inspector.currentPhase", value: "repair" },
          {
            key: "discipline_profile",
            label_key: "inspector.disciplineProfile",
            value: "lite-spec-tdd",
          },
          {
            key: "current_activity",
            label_key: "inspector.currentActivity",
            value: "Fix parser failure",
          },
        ],
      },
    },
  });
  assert.deepEqual(
    cWorkflowRows.map((row) => row.key),
    ["current_phase", "discipline_profile", "current_activity"],
  );
  assert.equal(workflowTaskSummary({ task_summary: "3 tasks, 1 blocked" }), "3 tasks, 1 blocked");

  const customRows = buildWorkflowRuntimeRows({
    workflow: {
      metadata: {
        display_rows: [
          { label: "Framework", value: "React" },
          { label_key: "inspector.currentPhase", value: "" },
          { label: "Package", value: "webapp" },
        ],
      },
      summary: "Frontend smoke ready",
    },
  });

  assert.deepEqual(
    customRows.map((row) => [row.label, row.value]),
    [
      ["Framework", "React"],
      ["Package", "webapp"],
    ],
  );
  assert.equal(workflowTaskSummary({ workflow: { summary: "Frontend smoke ready" } }), "Frontend smoke ready");
}
