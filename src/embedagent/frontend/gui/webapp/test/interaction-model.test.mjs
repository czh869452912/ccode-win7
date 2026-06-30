import assert from "node:assert/strict";

import {
  buildPermissionResponse,
  buildUserInputResponse,
  interactionNoticeView,
  normalizeComposerInteraction,
} from "../src/session-runtime/interaction-model.js";

export function runInteractionModelTests() {
  const permission = normalizeComposerInteraction({
    interaction_id: "perm-1",
    kind: "permission",
    tool_name: "edit_file",
    category: "workspace_write",
    reason: "Edit src/demo.c",
    details: { path: "src/demo.c" },
  });

  assert.equal(permission.kind, "permission");
  assert.equal(permission.interactionId, "perm-1");
  assert.equal(permission.requestKind, "file-change");
  assert.equal(permission.summary, "File-change approval requested");
  assert.equal(permission.primaryLabel, "Approve");
  assert.equal(permission.secondaryLabel, "Deny");
  assert.equal(permission.toolName, "edit_file");
  assert.equal(permission.reason, "Edit src/demo.c");
  assert.equal(permission.detailRows[0].label, "path");
  assert.equal(permission.detailRows[0].value, "src/demo.c");

  assert.deepEqual(buildPermissionResponse(permission, "acceptForSession"), {
    decision: "acceptForSession",
  });
  assert.deepEqual(buildPermissionResponse(permission, "decline"), {
    decision: "decline",
  });

  const ask = normalizeComposerInteraction({
    interaction_id: "ask-1",
    kind: "user_input",
    tool_name: "ask_user",
    questions: [
      {
        id: "answer",
        question: "Continue?",
        options: [
          { index: 1, label: "Continue" },
          { index: 2, label: "Switch to debug", mode: "debug" },
        ],
        multi_select: false,
      },
    ],
  });

  assert.equal(ask.kind, "user_input");
  assert.equal(ask.summary, "Input requested");
  assert.equal(ask.questions[0].id, "answer");
  assert.equal(ask.options[0].shortcut, "1");
  assert.equal(ask.options[1].label, "Switch to debug");
  assert.equal(ask.options[1].mode, "debug");
  assert.deepEqual(buildUserInputResponse(ask, { option: ask.options[1] }), {
    answers: { answer: "Switch to debug" },
  });
  assert.deepEqual(buildUserInputResponse(ask, { answer: "custom path" }), {
    answers: { answer: "custom path" },
  });

  const expired = interactionNoticeView({ kind: "expired", detail: "gone" });
  assert.equal(expired.kind, "notice");
  assert.equal(expired.tone, "expired");
  assert.equal(expired.title, "Interaction expired");
  assert.equal(expired.detail, "gone");

  const conflict = normalizeComposerInteraction(null, { kind: "conflict" });
  assert.equal(conflict.kind, "notice");
  assert.equal(conflict.title, "Interaction already handled");
}
