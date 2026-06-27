import assert from "node:assert/strict";

import {
  buildComposerInteractionModel,
  moveComposerMenuIndex,
  selectComposerMenuItem,
} from "../src/composer/composer-interaction-model.js";

const COMMANDS = [
  { id: "session.resume", group: "session", label: "Resume Session", slash: "/resume" },
  { id: "surface.diff", group: "surface", label: "Open Diff", slash: "/diff", keywords: ["git"] },
  { id: "mode.build", group: "mode", label: "Mode: Build", slash: "/mode build" },
  { id: "mode.debug", group: "mode", label: "Mode: Debug", slash: "/mode debug" },
  { id: "message.stop", group: "message", label: "Stop Running Turn", slash: "" },
];

const FILE_TREE = [
  {
    id: "src",
    path: "src",
    name: "src",
    kind: "dir",
    children: [
      { id: "src/main.c", path: "src/main.c", name: "main.c", kind: "file" },
      { id: "src/parser.c", path: "src/parser.c", name: "parser.c", kind: "file" },
    ],
  },
  { id: "README.md", path: "README.md", name: "README.md", kind: "file" },
];

export function runComposerInteractionModelTests() {
  const slashModel = buildComposerInteractionModel({
    value: "/mode d",
    cursor: "/mode d".length,
    commands: COMMANDS,
    fileTree: FILE_TREE,
    currentMode: "build",
    isRunning: false,
    hasInteraction: false,
    dismissedTriggerKey: "",
    activeIndex: 0,
  });

  assert.equal(slashModel.disabled, false);
  assert.equal(slashModel.action, "send");
  assert.equal(slashModel.canSend, true);
  assert.equal(slashModel.menu.open, true);
  assert.equal(slashModel.menu.triggerKind, "slash");
  assert.equal(slashModel.menu.items[0].slash, "/mode debug");
  assert.equal(slashModel.menu.activeItem.id, slashModel.menu.items[0].id);
  assert.equal(slashModel.hints.some((hint) => hint.id === "command"), true);

  assert.equal(moveComposerMenuIndex(0, "next", slashModel.menu.items.length), 0);
  assert.equal(moveComposerMenuIndex(0, "previous", slashModel.menu.items.length), 0);

  const selectedSlash = selectComposerMenuItem({
    value: "/mode d",
    cursor: "/mode d".length,
    trigger: slashModel.trigger,
    item: slashModel.menu.activeItem,
  });
  assert.equal(selectedSlash.text, "/mode debug ");
  assert.equal(selectedSlash.cursor, "/mode debug ".length);

  const pathModel = buildComposerInteractionModel({
    value: "inspect @par",
    cursor: "inspect @par".length,
    commands: COMMANDS,
    fileTree: FILE_TREE,
    currentMode: "build",
    isRunning: false,
    hasInteraction: false,
    dismissedTriggerKey: "",
    activeIndex: 0,
  });

  assert.equal(pathModel.menu.open, true);
  assert.equal(pathModel.menu.triggerKind, "path");
  assert.deepEqual(
    pathModel.menu.items.map((item) => item.path),
    ["src/parser.c"],
  );
  const selectedPath = selectComposerMenuItem({
    value: "inspect @par",
    cursor: "inspect @par".length,
    trigger: pathModel.trigger,
    item: pathModel.menu.activeItem,
  });
  assert.equal(selectedPath.text, "inspect @src/parser.c ");
  assert.equal(selectedPath.cursor, "inspect @src/parser.c ".length);

  const runningModel = buildComposerInteractionModel({
    value: "cannot edit while running",
    cursor: 4,
    commands: COMMANDS,
    fileTree: FILE_TREE,
    isRunning: true,
    hasInteraction: false,
    dismissedTriggerKey: "",
    activeIndex: 0,
  });
  assert.equal(runningModel.disabled, true);
  assert.equal(runningModel.action, "stop");
  assert.equal(runningModel.canSend, false);
  assert.equal(runningModel.menu.open, false);
  assert.equal(runningModel.hints.find((hint) => hint.id === "status.running").tone, "warning");
  assert.equal(runningModel.hints.find((hint) => hint.id === "status.running").status, "running");

  const interactionModel = buildComposerInteractionModel({
    value: "/diff",
    cursor: 5,
    commands: COMMANDS,
    fileTree: FILE_TREE,
    isRunning: false,
    hasInteraction: true,
    dismissedTriggerKey: "",
    activeIndex: 0,
  });
  assert.equal(interactionModel.disabled, true);
  assert.equal(interactionModel.action, "send");
  assert.equal(interactionModel.canSend, false);
  assert.equal(interactionModel.menu.open, false);
  assert.equal(
    interactionModel.hints.find((hint) => hint.id === "status.interaction").status,
    "interaction",
  );
}
