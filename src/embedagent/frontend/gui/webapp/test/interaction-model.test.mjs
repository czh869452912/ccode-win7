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

  assert.deepEqual(
    buildPermissionResponse(permission, { decision: true, remember: true }),
    {
      response_kind: "approve",
      decision: true,
      remember: true,
      category: "workspace_write",
    },
  );
  assert.deepEqual(
    buildPermissionResponse(permission, { decision: false, remember: true }),
    {
      response_kind: "deny",
      decision: false,
      remember: false,
      category: "workspace_write",
    },
  );

  const ask = normalizeComposerInteraction({
    interaction_id: "ask-1",
    kind: "user_input",
    tool_name: "ask_user",
    question: "Continue?",
    options: [
      { index: 1, text: "Continue" },
      { index: 2, text: "Switch to debug", mode: "debug" },
    ],
  });

  assert.equal(ask.kind, "user_input");
  assert.equal(ask.summary, "Input requested");
  assert.equal(ask.options[0].shortcut, "1");
  assert.equal(ask.options[1].mode, "debug");
  assert.deepEqual(buildUserInputResponse(ask, { option: ask.options[1] }), {
    response_kind: "answer",
    answer: "Switch to debug",
    selected_index: 2,
    selected_mode: "debug",
    selected_option_text: "Switch to debug",
  });
  assert.deepEqual(buildUserInputResponse(ask, { answer: "custom path" }), {
    response_kind: "answer",
    answer: "custom path",
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
