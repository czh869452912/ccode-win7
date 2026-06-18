import assert from "node:assert/strict";

import {
  composerTriggerKey,
  detectComposerTrigger,
  replaceComposerTrigger,
} from "../src/composer/composer-trigger.js";

export function runComposerTriggerTests() {
  assert.deepEqual(detectComposerTrigger("/mo", 3), {
    kind: "slash",
    marker: "/",
    query: "mo",
    start: 0,
    end: 3,
    text: "/mo",
  });

  assert.deepEqual(detectComposerTrigger("please /di", 10), {
    kind: "slash",
    marker: "/",
    query: "di",
    start: 7,
    end: 10,
    text: "/di",
  });

  assert.equal(detectComposerTrigger("src/parser.c", 6), null);
  assert.equal(detectComposerTrigger("http://localhost", 7), null);
  assert.equal(detectComposerTrigger("email/name", 7), null);

  assert.deepEqual(detectComposerTrigger("@src/pa", 7), {
    kind: "path",
    marker: "@",
    query: "src/pa",
    start: 0,
    end: 7,
    text: "@src/pa",
  });

  assert.deepEqual(detectComposerTrigger("inspect @parser", 15), {
    kind: "path",
    marker: "@",
    query: "parser",
    start: 8,
    end: 15,
    text: "@parser",
  });

  assert.equal(detectComposerTrigger("mail@example.com", 7), null);
  assert.equal(detectComposerTrigger("ask @", 5)?.query, "");

  const replacement = replaceComposerTrigger(
    "run /di now",
    detectComposerTrigger("run /di now", 7),
    "/diff ",
  );
  assert.deepEqual(replacement, {
    text: "run /diff  now",
    cursor: 10,
  });

  assert.equal(
    composerTriggerKey(detectComposerTrigger("ask @parser", 11)),
    "path:4:11:@parser",
  );
  assert.equal(composerTriggerKey(null), "");
}
