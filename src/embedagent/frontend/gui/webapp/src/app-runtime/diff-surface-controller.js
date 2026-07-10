import { createDiffSurfaceState } from "../session-runtime/diff-model.js";

function readChrome(getDiffPanelChrome) {
  const value =
    typeof getDiffPanelChrome === "function" ? getDiffPanelChrome() : {};
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function diffTextFromItem(item) {
  const data = item?.data || {};
  if (typeof data.diff === "string" && data.diff) return data.diff;
  if (typeof data.diff_preview === "string" && data.diff_preview) return data.diff_preview;
  if (typeof data.unified_diff === "string" && data.unified_diff) return data.unified_diff;
  if (typeof item?.diff === "string" && item.diff) return item.diff;
  return "";
}

function findRuntimeDiff({ runtimeState, turnId = "", filePath = "" } = {}) {
  const items = Array.isArray(runtimeState?.timelineItems) ? runtimeState.timelineItems : [];
  const match = items.find((candidate) => {
    if (turnId && candidate.turnId !== turnId) return false;
    const data = candidate.data || {};
    const args = candidate.arguments || {};
    if (filePath && data.path !== filePath && args.path !== filePath) return false;
    return Boolean(diffTextFromItem(candidate));
  });
  return diffTextFromItem(match);
}

export function createDiffSurfaceController({
  dispatch,
  getRuntimeState,
  getDiffPanelChrome,
} = {}) {
  const send = typeof dispatch === "function" ? dispatch : () => {};
  const runtime = typeof getRuntimeState === "function" ? getRuntimeState : () => ({});

  function open({ title = "", diff = "", turnId = "", filePath = "" } = {}) {
    const resolvedDiff =
      diff || findRuntimeDiff({ runtimeState: runtime(), turnId, filePath });
    if (!resolvedDiff) return false;
    const chrome = readChrome(getDiffPanelChrome);
    send({
      type: "diff_surface_opened",
      diffSurface: createDiffSurfaceState({
        title: filePath || title || chrome.defaultTitle,
        diff: resolvedDiff,
        source: "gui",
        turnId,
        filePath,
        chrome,
      }),
    });
    return true;
  }

  return { open };
}
