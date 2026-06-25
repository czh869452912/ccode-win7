import assert from "node:assert/strict";

import {
  createComposerState,
  readComposerDraft,
  reduceComposerState,
} from "../src/composer/composer-state.js";

export function runComposerStateTests() {
  const initial = createComposerState();
  assert.equal(initial.draft, "");
  assert.equal(readComposerDraft({ composer: initial }), "");

  const typed = reduceComposerState(initial, { type: "set_composer", value: "inspect @src" });
  assert.equal(typed.draft, "inspect @src");
  assert.equal(readComposerDraft({ composer: typed }), "inspect @src");
  assert.equal(readComposerDraft({ composer: "legacy draft" }), "");

  const clearedAfterUserMessage = reduceComposerState(typed, { type: "local_user_message" });
  assert.equal(clearedAfterUserMessage.draft, "");

  const typedAgain = reduceComposerState(clearedAfterUserMessage, {
    type: "set_composer",
    value: "/review",
  });
  const reset = reduceComposerState(typedAgain, { type: "workspace_scoped_state_reset" });
  assert.deepEqual(reset, createComposerState());
}
