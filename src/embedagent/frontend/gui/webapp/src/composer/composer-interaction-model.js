import {
  buildComposerCommandItems,
  groupComposerCommandItems,
  searchComposerCommandItems,
} from "./composer-command-search.js";
import {
  buildPathContextInsertion,
  flattenComposerPathCandidates,
  groupComposerPathCandidates,
  searchComposerPathCandidates,
} from "./composer-path-context.js";
import {
  composerTriggerKey,
  detectComposerTrigger,
  replaceComposerTrigger,
} from "./composer-trigger.js";

function flattenGroups(groups) {
  return (Array.isArray(groups) ? groups : []).reduce((items, group) => {
    return items.concat(Array.isArray(group.items) ? group.items : []);
  }, []);
}

function commandsFromHints(commandHints) {
  return (Array.isArray(commandHints) ? commandHints : [])
    .filter(Boolean)
    .map((slash) => ({
      id: `hint.${String(slash).replace(/[^a-z0-9]+/gi, ".")}`,
      group: "command",
      label: slash,
      slash,
      visibleWhen: "always",
    }));
}

function boundedActiveIndex(index, length) {
  if (length <= 0) return 0;
  const value = Number(index);
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(Math.trunc(value), length - 1));
}

export function moveComposerMenuIndex(currentIndex, direction, itemCount) {
  const count = Math.max(0, Math.trunc(Number(itemCount) || 0));
  if (count <= 0) return 0;
  const current = boundedActiveIndex(currentIndex, count);
  if (direction === "previous") return (current - 1 + count) % count;
  return (current + 1) % count;
}

export function selectComposerMenuItem({ value = "", cursor = 0, trigger = null, item = null } = {}) {
  if (!trigger || !item) return null;
  const insertion =
    item.type === "path-context"
      ? buildPathContextInsertion(item)
      : item.insertion || item.slash || "";
  if (!insertion) return null;
  return replaceComposerTrigger(String(value || ""), trigger, insertion);
}

export function buildComposerInteractionModel({
  value = "",
  cursor = 0,
  commands = [],
  commandHints = [],
  fileTree = [],
  currentMode = "",
  isRunning = false,
  hasInteraction = false,
  dismissedTriggerKey = "",
  activeIndex = 0,
  commandMenuChrome = {},
  commandGroupLabels = {},
} = {}) {
  const textValue = String(value || "");
  const boundedCursor = Math.max(0, Math.min(Math.trunc(Number(cursor) || 0), textValue.length));
  const disabled = Boolean(isRunning || hasInteraction);
  const trigger = detectComposerTrigger(textValue, boundedCursor);
  const triggerKey = composerTriggerKey(trigger);
  const menuOpen = Boolean(!disabled && trigger && triggerKey !== dismissedTriggerKey);
  const commandSource = commands.length > 0 ? commands : commandsFromHints(commandHints);
  const slashItems = buildComposerCommandItems(
    commandSource,
    commandGroupLabels,
    commandMenuChrome,
  );
  const pathCandidates = flattenComposerPathCandidates(fileTree);

  let groups = [];
  if (menuOpen && trigger && trigger.kind === "slash") {
    groups = groupComposerCommandItems(
      searchComposerCommandItems(slashItems, trigger.query, 8),
      commandGroupLabels,
      commandMenuChrome,
    );
  } else if (menuOpen && trigger && trigger.kind === "path") {
    groups = groupComposerPathCandidates(
      searchComposerPathCandidates(pathCandidates, trigger.query, 8),
      commandMenuChrome,
    );
  }

  const items = flattenGroups(groups);
  const resolvedActiveIndex = boundedActiveIndex(activeIndex, items.length);
  const activeItem = items[resolvedActiveIndex] || null;
  const statusHint = isRunning
    ? { id: "status.running", status: "running", tone: "warning" }
    : hasInteraction
      ? { id: "status.interaction", status: "interaction", tone: "warning" }
      : null;

  return {
    disabled,
    action: isRunning ? "stop" : "send",
    canSend: Boolean(!disabled && textValue.trim()),
    currentMode: String(currentMode || ""),
    trigger,
    triggerKey,
    menu: {
      open: menuOpen,
      triggerKind: trigger ? trigger.kind : "",
      groups,
      items,
      activeIndex: resolvedActiveIndex,
      activeItem,
      emptyText:
        trigger && trigger.kind === "path"
          ? commandMenuChrome.pathEmptyText || ""
          : commandMenuChrome.commandEmptyText || "",
    },
    hints: [
      { id: "command" },
      { id: "file" },
      { id: "select" },
      { id: "newline" },
      ...(statusHint ? [statusHint] : []),
    ],
  };
}
