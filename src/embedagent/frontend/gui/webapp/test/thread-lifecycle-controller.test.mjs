import assert from "node:assert/strict";

import { createThreadLifecycleController } from "../src/app-runtime/thread-lifecycle-controller.js";

function createHarness({ promptValues = [], confirmValues = [] } = {}) {
  const calls = {
    fetches: [],
    prompts: [],
    confirms: [],
    notices: [],
    loadSessions: 0,
    loadedSessionIds: [],
  };
  const actions = [
    {
      id: "retitle",
      capability: "rename",
      label: "Retitle",
      promptTitle: "Descriptor rename prompt",
      emptyTitle: "Descriptor rename blocked",
      emptyBody: "Descriptor title is required.",
      failureTitle: "Descriptor rename failed",
    },
    {
      id: "clone",
      capability: "fork",
      label: "Clone",
      promptTitle: "Descriptor fork prompt",
      promptInitial: "copy",
      failureTitle: "Descriptor fork failed",
    },
    {
      id: "hide",
      capability: "archive",
      label: "Hide",
      confirmTitle: "Descriptor archive confirm",
      successTitle: "Descriptor archive success",
      successBody: "Descriptor archive body.",
      failureTitle: "Descriptor archive failed",
    },
  ];
  const controller = createThreadLifecycleController({
    fetchJson: async (url, options = {}) => {
      calls.fetches.push({ url, options });
      return url.endsWith("/fork") ? { session_id: "sess-forked" } : {};
    },
    dispatch: (event) => {
      if (event?.type === "interaction_notice_set") calls.notices.push(event.notice);
    },
    loadSessions: async () => {
      calls.loadSessions += 1;
    },
    loadSession: async (sessionId) => {
      calls.loadedSessionIds.push(sessionId);
    },
    getThreadSessions: () => [
      { session_id: "sess-1", thread: { title: "Existing title" } },
    ],
    getThreadLifecycleCapabilities: () => ({ actions }),
    prompt: (message, initialValue) => {
      calls.prompts.push({ message, initialValue });
      return promptValues.length > 0 ? promptValues.shift() : null;
    },
    confirm: (message) => {
      calls.confirms.push(message);
      return confirmValues.length > 0 ? confirmValues.shift() : false;
    },
  });
  return { controller, calls };
}

export async function runThreadLifecycleControllerTests() {
  const blockedRename = createHarness({ promptValues: [""] });
  await blockedRename.controller.handleThreadLifecycleAction("retitle", "sess-1");
  assert.deepEqual(blockedRename.calls.prompts, [
    { message: "Descriptor rename prompt", initialValue: "Existing title" },
  ]);
  assert.deepEqual(blockedRename.calls.notices, [
    {
      kind: "thread_lifecycle",
      title: "Descriptor rename blocked",
      body: "Descriptor title is required.",
    },
  ]);
  assert.equal(blockedRename.calls.fetches.length, 0);

  const renamed = createHarness({ promptValues: ["New title"] });
  await renamed.controller.handleThreadLifecycleAction("retitle", "sess-1");
  assert.equal(renamed.calls.fetches[0].url, "/api/sessions/sess-1/rename");
  assert.equal(JSON.parse(renamed.calls.fetches[0].options.body).title, "New title");
  assert.equal(renamed.calls.loadSessions, 1);

  const archived = createHarness({ confirmValues: [true] });
  await archived.controller.handleThreadLifecycleAction("hide", "sess-1");
  assert.deepEqual(archived.calls.confirms, ["Descriptor archive confirm"]);
  assert.equal(archived.calls.fetches[0].url, "/api/sessions/sess-1/archive");
  assert.deepEqual(archived.calls.notices, [
    {
      kind: "thread_lifecycle",
      title: "Descriptor archive success",
      body: "Descriptor archive body.",
    },
  ]);

  const forked = createHarness({ promptValues: ["Fork title"] });
  await forked.controller.handleThreadLifecycleAction("clone", "sess-1");
  assert.deepEqual(forked.calls.prompts, [
    { message: "Descriptor fork prompt", initialValue: "copy" },
  ]);
  assert.equal(forked.calls.fetches[0].url, "/api/sessions/sess-1/fork");
  assert.equal(JSON.parse(forked.calls.fetches[0].options.body).title, "Fork title");
  assert.deepEqual(forked.calls.loadedSessionIds, ["sess-forked"]);
}
