import assert from "node:assert/strict";

import { createBrowserDialogService } from "../src/app-runtime/browser-dialog-service.js";

export function runBrowserDialogServiceTests() {
  const calls = [];
  const dialogs = createBrowserDialogService({
    windowObject: {
      prompt(message, initialValue) {
        calls.push(["prompt", message, initialValue]);
        return "renamed";
      },
      confirm(message) {
        calls.push(["confirm", message]);
        return true;
      },
    },
  });

  assert.equal(dialogs.prompt("Name", "old"), "renamed");
  assert.equal(dialogs.confirm("Archive?"), true);
  assert.deepEqual(calls, [
    ["prompt", "Name", "old"],
    ["confirm", "Archive?"],
  ]);

  const fallback = createBrowserDialogService({ windowObject: {} });
  assert.equal(fallback.prompt("Name", "old"), null);
  assert.equal(fallback.confirm("Archive?"), false);
}
