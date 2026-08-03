import assert from "node:assert/strict";

import { createThreadLifecycleController } from "../src/app-runtime/thread-lifecycle-controller.js";

function defaultThreadLifecycleActions() {
  return [
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
}

function createHarness({ promptValues = [], confirmValues = [], actions = defaultThreadLifecycleActions() } = {}) {
  const calls = {
    protocol: [],
    prompts: [],
    confirms: [],
    notices: [],
    loadSessions: 0,
    loadedSessionIds: [],
  };
  const protocol = {
    renameSession: async (sessionId, title) => {
      calls.protocol.push({ name: "renameSession", args: [sessionId, title] });
      return {};
    },
    archiveSession: async (sessionId) => {
      calls.protocol.push({ name: "archiveSession", args: [sessionId] });
      return {};
    },
    forkSession: async (sessionId, title) => {
      calls.protocol.push({ name: "forkSession", args: [sessionId, title] });
      return { session_id: "sess-forked" };
    },
  };
  const controller = createThreadLifecycleController({
    protocol,
    dispatch: (event) => {
      if (event?.type === "interaction_notice_set") calls.notices.push(event.notice);
    },
    loadSessions: async () => {
      calls.loadSessions += 1;
    },
    loadSession: async (sessionId) => calls.loadedSessionIds.push(sessionId),
    getThreadSessions: () => [{ session_id: "sess-1", thread: { title: "Existing title" } }],
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
  assert.equal(blockedRename.calls.protocol.length, 0);
  assert.equal(blockedRename.calls.notices[0].title, "Descriptor rename blocked");

  const missingEmptyCopy = createHarness({
    promptValues: [""],
    actions: [{ id: "bare-retitle", capability: "rename", label: "Bare Retitle" }],
  });
  await missingEmptyCopy.controller.handleThreadLifecycleAction("bare-retitle", "sess-1");
  assert.deepEqual(missingEmptyCopy.calls.notices, []);

  const renamed = createHarness({ promptValues: ["New title"] });
  await renamed.controller.handleThreadLifecycleAction("retitle", "sess-1");
  assert.deepEqual(renamed.calls.protocol[0], {
    name: "renameSession",
    args: ["sess-1", "New title"],
  });
  assert.equal(renamed.calls.loadSessions, 1);

  const archived = createHarness({ confirmValues: [true] });
  await archived.controller.handleThreadLifecycleAction("hide", "sess-1");
  assert.deepEqual(archived.calls.confirms, ["Descriptor archive confirm"]);
  assert.deepEqual(archived.calls.protocol[0], {
    name: "archiveSession",
    args: ["sess-1"],
  });
  assert.equal(archived.calls.notices[0].title, "Descriptor archive success");

  const forked = createHarness({ promptValues: ["Fork title"] });
  await forked.controller.handleThreadLifecycleAction("clone", "sess-1");
  assert.deepEqual(forked.calls.protocol[0], {
    name: "forkSession",
    args: ["sess-1", "Fork title"],
  });
  assert.deepEqual(forked.calls.loadedSessionIds, ["sess-forked"]);

  const missingProtocol = createThreadLifecycleController({
    protocol: {},
    getThreadLifecycleCapabilities: () => ({ actions: defaultThreadLifecycleActions() }),
  });
  assert.equal(await missingProtocol.renameThread("sess-1"), undefined);
}
