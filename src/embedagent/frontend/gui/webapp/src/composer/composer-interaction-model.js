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

function boundedActiveIndex(index, length) {
  if (length <= 0) return 0;
  const value = Number(index);
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(Math.trunc(value), length - 1));
}

function normalizeHintDescriptor(input = {}) {
  const value = input && typeof input === "object" && !Array.isArray(input) ? input : {};
  const id = String(value.id || "").trim();
  if (!id) return null;
  return {
    id,
    label: String(value.label || ""),
    visibleWhen: String(value.visibleWhen || value.visible_when || "always"),
    tone: String(value.tone || ""),
    status: String(value.status || ""),
  };
}

function isHintVisible(hint, isRunning, hasInteraction) {
  if (hint.visibleWhen === "always" || !hint.visibleWhen) return true;
  if (hint.visibleWhen === "running") return isRunning;
  if (hint.visibleWhen === "interaction") return hasInteraction;
  if (hint.visibleWhen === "idle") return !isRunning && !hasInteraction;
  return false;
}

function visibleHints(hintDescriptors, isRunning, hasInteraction) {
  return (Array.isArray(hintDescriptors) ? hintDescriptors : [])
    .map((item) => normalizeHintDescriptor(item))
    .filter((hint) => hint && isHintVisible(hint, isRunning, hasInteraction));
}

function hasVisibleHint(hints, id) {
  const normalizedId = String(id || "").trim();
  return (Array.isArray(hints) ? hints : []).some((hint) => hint.id === normalizedId);
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
  fileTree = [],
  currentMode = "",
  isRunning = false,
  hasInteraction = false,
  dismissedTriggerKey = "",
  activeIndex = 0,
  commandMenuChrome = {},
  commandGroupLabels = {},
  hintDescriptors = [],
} = {}) {
  const textValue = String(value || "");
  const boundedCursor = Math.max(0, Math.min(Math.trunc(Number(cursor) || 0), textValue.length));
  const disabled = Boolean(isRunning || hasInteraction);
  const trigger = detectComposerTrigger(textValue, boundedCursor);
  const triggerKey = composerTriggerKey(trigger);
  const hints = visibleHints(hintDescriptors, isRunning, hasInteraction);
  const pathContextEnabled = hasVisibleHint(hints, "file");
  const menuOpen = Boolean(
    !disabled &&
      trigger &&
      triggerKey !== dismissedTriggerKey &&
      (trigger.kind !== "path" || pathContextEnabled),
  );
  const slashItems = buildComposerCommandItems(
    commands,
    commandGroupLabels,
    commandMenuChrome,
  );
  const pathCandidates = pathContextEnabled ? flattenComposerPathCandidates(fileTree) : [];

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
    hints,
  };
}
