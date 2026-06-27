function clampCursor(text, cursor) {
  const source = String(text || "");
  const raw = Number.isFinite(cursor) ? cursor : source.length;
  return Math.max(0, Math.min(source.length, raw));
}

function isBoundary(source, index) {
  if (index <= 0) return true;
  return /\s/.test(source.charAt(index - 1));
}

function findTokenStart(source, cursor) {
  let index = cursor;
  while (index > 0 && !/\s/.test(source.charAt(index - 1))) {
    index -= 1;
  }
  return index;
}

function findSlashCommandStart(source, cursor) {
  let index = cursor - 1;
  while (index >= 0) {
    const char = source.charAt(index);
    if (char === "\n") return -1;
    if (char === "/" && isBoundary(source, index)) return index;
    index -= 1;
  }
  return -1;
}

export function detectComposerTrigger(text = "", cursor = undefined) {
  const source = String(text || "");
  const end = clampCursor(source, cursor);
  const start = findTokenStart(source, end);
  if (!isBoundary(source, start)) return null;

  const token = source.slice(start, end);
  if (!token) return null;

  if (token.charAt(0) === "/") {
    return {
      kind: "slash",
      marker: "/",
      query: token.slice(1),
      start,
      end,
      text: token,
    };
  }

  const slashStart = findSlashCommandStart(source, end);
  if (slashStart >= 0 && slashStart < start) {
    const slashText = source.slice(slashStart, end);
    if (!slashText.includes("\n")) {
      return {
        kind: "slash",
        marker: "/",
        query: slashText.slice(1),
        start: slashStart,
        end,
        text: slashText,
      };
    }
  }

  if (token.charAt(0) === "@") {
    return {
      kind: "path",
      marker: "@",
      query: token.slice(1),
      start,
      end,
      text: token,
    };
  }

  return null;
}

export function composerTriggerKey(trigger) {
  if (!trigger) return "";
  return `${trigger.kind}:${trigger.start}:${trigger.end}:${trigger.text}`;
}

export function replaceComposerTrigger(text, trigger, replacement) {
  const source = String(text || "");
  const insertion = String(replacement || "");
  if (!trigger || trigger.start < 0 || trigger.end < trigger.start || trigger.end > source.length) {
    const cursor = source.length + insertion.length;
    return { text: `${source}${insertion}`, cursor };
  }
  const before = source.slice(0, trigger.start);
  const after = source.slice(trigger.end);
  const nextText = `${before}${insertion}${after}`;
  return {
    text: nextText,
    cursor: before.length + insertion.length,
  };
}
