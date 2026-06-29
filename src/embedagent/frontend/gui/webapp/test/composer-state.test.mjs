import assert from "node:assert/strict";

import {
  createComposerState,
  draftKeyForSession,
  readComposerDraft,
  reduceComposerState,
} from "../src/composer/composer-state.js";

export function runComposerStateTests() {
  const initial = createComposerState();
  assert.deepEqual(initial.draftsByKey, {});
  assert.equal(initial.activeDraftKey, null);
  assert.equal(readComposerDraft({ composer: initial }), "");

  const typed = reduceComposerState(initial, {
    type: "set_composer",
    sessionId: "sess-1",
    value: "inspect @src",
  });
  assert.equal(typed.activeDraftKey, draftKeyForSession("sess-1"));
  assert.equal(typed.draftsByKey[draftKeyForSession("sess-1")].draft, "inspect @src");
  assert.equal(readComposerDraft({ composer: typed }), "inspect @src");
  assert.equal(readComposerDraft({ composer: "legacy draft" }), "");

  const secondTyped = reduceComposerState(typed, {
    type: "set_composer",
    sessionId: "sess-2",
    value: "debug second",
  });
  assert.equal(secondTyped.draftsByKey[draftKeyForSession("sess-1")].draft, "inspect @src");
  assert.equal(secondTyped.draftsByKey[draftKeyForSession("sess-2")].draft, "debug second");
  assert.equal(readComposerDraft({ composer: secondTyped, thread: { currentSessionId: "sess-1" } }), "inspect @src");

  const clearedAfterUserMessage = reduceComposerState(secondTyped, {
    type: "local_user_message",
    sessionId: "sess-2",
  });
  assert.equal(clearedAfterUserMessage.draftsByKey[draftKeyForSession("sess-2")].draft, "");
  assert.equal(clearedAfterUserMessage.draftsByKey[draftKeyForSession("sess-1")].draft, "inspect @src");

  const typedAgain = reduceComposerState(clearedAfterUserMessage, {
    type: "set_composer",
    sessionId: "sess-1",
    value: "/review",
  });
  const reset = reduceComposerState(typedAgain, { type: "workspace_scoped_state_reset" });
  assert.deepEqual(reset, createComposerState());
}
