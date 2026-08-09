export const ACTIVITY_ROW_KINDS = Object.freeze({
  MESSAGE: "message",
  WORK: "work",
  TURN_FOLD: "turn_fold",
  DIFF_SUMMARY: "diff_summary",
  CONTEXT_SUMMARY: "context_summary",
  COMMAND_RESULT: "command_result",
  REVIEW_RESULT: "review_result",
  WORKING: "working",
  SYSTEM_NOTICE: "system_notice",
});

export function stringValue(value, fallback = "") {
  if (value == null) return fallback;
  return String(value);
}

export function timestampValue(...values) {
  for (const value of values) {
    const text = stringValue(value);
    if (!text) continue;
    const parsed = Date.parse(text);
    if (Number.isFinite(parsed)) return text;
  }
  return "";
}

export function numberValue(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}
