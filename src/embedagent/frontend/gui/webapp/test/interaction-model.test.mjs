import assert from "node:assert/strict";

import {
  buildPermissionResponse,
  buildUserInputResponse,
  currentInteractionFromActivities,
  interactionNoticeView,
  normalizeComposerInteraction,
} from "../src/session-runtime/interaction-model.js";

const COPY = Object.freeze({
  pendingApprovalKicker: "APPROVAL",
  inputRequiredKicker: "ANSWER",
  commandApprovalSummary: "Command approval requested",
  fileReadApprovalSummary: "File-read approval requested",
  fileChangeApprovalSummary: "File-change approval requested",
  expiredTitle: "Interaction expired",
  expiredBody: "Expired body",
  conflictTitle: "Interaction already handled",
  conflictBody: "Conflict body",
  approveOnceLabel: "Approve once",
  declineLabel: "Decline",
  cancelTurnLabel: "Cancel turn",
  alwaysAllowSessionLabel: "Always allow this session",
  inputSummary: "Input requested",
  customAnswerPlaceholder: "Or type a custom answer...",
  submitLabel: "Submit",
  modeLabelPrefix: "mode:",
});

export function runInteractionModelTests() {
  const permission = normalizeComposerInteraction({
    interaction_id: "perm-1",
    kind: "permission",
    tool_name: "edit_file",
    category: "workspace_write",
    reason: "Edit src/demo.c",
    details: { path: "src/demo.c" },
  }, null, COPY);

  assert.equal(permission.kind, "permission");
  assert.equal(permission.interactionId, "perm-1");
  assert.equal(permission.requestKind, "file-change");
  assert.equal(permission.summary, "File-change approval requested");
  assert.equal(permission.primaryLabel, "Approve once");
  assert.equal(permission.secondaryLabel, "Decline");
  assert.equal(permission.cancelLabel, "Cancel turn");
  assert.equal(permission.rememberLabel, "Always allow this session");
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
  }, null, COPY);

  assert.equal(ask.kind, "user_input");
  assert.equal(ask.summary, "Input requested");
  assert.equal(ask.kicker, "ANSWER");
  assert.equal(ask.customPlaceholder, "Or type a custom answer...");
  assert.equal(ask.submitLabel, "Submit");
  assert.equal(ask.modeLabelPrefix, "mode:");
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

  const customQuestion = normalizeComposerInteraction({
    interaction_id: "ask-target",
    kind: "user_input",
    questions: [
      {
        id: "target",
        question: "Choose target?",
        options: [{ index: 1, label: "Python", value: "python" }],
      },
    ],
  }, null, COPY);
  assert.deepEqual(buildUserInputResponse(customQuestion, { option: customQuestion.options[0] }), {
    answers: { target: "python" },
  });
  assert.deepEqual(buildUserInputResponse(customQuestion, { answer: "embedded" }), {
    answers: { target: "embedded" },
  });

  const expired = interactionNoticeView({ kind: "expired", detail: "gone" }, COPY);
  assert.equal(expired.kind, "notice");
  assert.equal(expired.tone, "expired");
  assert.equal(expired.title, "Interaction expired");
  assert.equal(expired.detail, "gone");

  const conflict = normalizeComposerInteraction(null, { kind: "conflict" }, COPY);
  assert.equal(conflict.kind, "notice");
  assert.equal(conflict.title, "Interaction already handled");

  const noCopy = normalizeComposerInteraction({
    interaction_id: "perm-no-copy",
    kind: "permission",
    category: "workspace_write",
  });
  assert.equal(noCopy.summary, "");
  assert.equal(noCopy.primaryLabel, "");

  const activityPermission = currentInteractionFromActivities([
    {
      id: "act-approval",
      kind: "interaction",
      sourceActivityKind: "approval.requested",
      requestId: "perm-activity",
      status: "pending",
      turnId: "turn-1",
      payload: {
        requestKind: "file-change",
        toolName: "edit_file",
        summary: "File-change approval requested",
        reason: "Edit src/demo.c",
        details: { path: "src/demo.c" },
      },
    },
  ]);
  assert.equal(activityPermission.kind, "permission");
  assert.equal(activityPermission.interactionId, "perm-activity");
  assert.equal(activityPermission.summary, "");
  assert.equal(activityPermission.detailRows[0].value, "src/demo.c");
  assert.equal(
    normalizeComposerInteraction(activityPermission, null, COPY).summary,
    "File-change approval requested",
  );

  const closedPermission = currentInteractionFromActivities([
    {
      id: "act-approval",
      kind: "interaction",
      sourceActivityKind: "approval.requested",
      requestId: "perm-activity",
      status: "pending",
      payload: { summary: "Edit src/demo.c" },
    },
    {
      id: "act-approval-resolved",
      kind: "interaction",
      sourceActivityKind: "approval.resolved",
      requestId: "perm-activity",
      status: "resolved",
      payload: { decision: "accept" },
    },
  ]);
  assert.equal(closedPermission, null);

  const activityInput = currentInteractionFromActivities([
    {
      id: "act-input",
      kind: "interaction",
      sourceActivityKind: "user-input.requested",
      requestId: "ask-activity",
      status: "pending",
      payload: {
        toolName: "ask_user",
        questions: [
          {
            id: "answer",
            question: "Continue?",
            options: [{ index: 1, label: "Continue" }],
          },
        ],
      },
    },
  ]);
  assert.equal(activityInput.kind, "user_input");
  assert.equal(activityInput.interactionId, "ask-activity");
  assert.equal(activityInput.options[0].label, "Continue");

  const activityInputWithoutToolName = currentInteractionFromActivities([
    {
      id: "act-input-generic",
      kind: "interaction",
      sourceActivityKind: "user-input.requested",
      requestId: "ask-generic",
      status: "pending",
      payload: {
        questions: [
          {
            id: "answer",
            question: "Continue?",
            options: [{ index: 1, label: "Continue" }],
          },
        ],
      },
    },
  ]);
  assert.equal(activityInputWithoutToolName.kind, "user_input");
  assert.equal(activityInputWithoutToolName.toolName, "");
}
