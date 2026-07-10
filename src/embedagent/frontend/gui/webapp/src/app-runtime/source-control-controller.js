import { createDiffSurfaceState } from "../session-runtime/diff-model.js";
import {
  getSourceControlDiff as requestSourceControlDiff,
  getSourceControlStatus as requestSourceControlStatus,
  refreshSourceControlStatus as requestSourceControlRefresh,
} from "../source-control/source-control-api.js";
import { sourceControlCapabilityEnabled } from "../source-control/source-control-capability.js";

function readAppCapabilities({ appCapabilities, getAppCapabilities }) {
  const value =
    typeof getAppCapabilities === "function" ? getAppCapabilities() : appCapabilities;
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function readChrome(reader) {
  const value = typeof reader === "function" ? reader() : {};
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function formatTemplate(template = "", values = {}) {
  return String(template || "").replace(/\{([a-zA-Z0-9_]+)\}/g, (_match, key) =>
    values[key] === undefined || values[key] === null ? "" : String(values[key]),
  );
}

export function createSourceControlController({
  dispatch,
  appCapabilities,
  getAppCapabilities,
  hasActiveWorkspace,
  getSourceControlStatus = requestSourceControlStatus,
  refreshSourceControlStatus = requestSourceControlRefresh,
  getSourceControlDiff = requestSourceControlDiff,
  getSourceControlChrome,
  getDiffPanelChrome,
} = {}) {
  const send = typeof dispatch === "function" ? dispatch : () => {};

  function capabilitiesFor(overrideCapabilities) {
    return overrideCapabilities && typeof overrideCapabilities === "object"
      ? overrideCapabilities
      : readAppCapabilities({ appCapabilities, getAppCapabilities });
  }

  function workspaceActive(assumeWorkspace) {
    if (assumeWorkspace !== undefined) return Boolean(assumeWorkspace);
    return typeof hasActiveWorkspace === "function" ? Boolean(hasActiveWorkspace()) : true;
  }

  async function loadStatus(refresh = false, assumeWorkspace, overrideCapabilities) {
    const capabilities = capabilitiesFor(overrideCapabilities);
    if (!workspaceActive(assumeWorkspace) || !sourceControlCapabilityEnabled(capabilities)) {
      send({ type: "source_control_reset" });
      return null;
    }
    send({ type: "source_control_load_started" });
    const sourceControlChrome = readChrome(getSourceControlChrome);
    try {
      const payload = refresh
        ? await refreshSourceControlStatus()
        : await getSourceControlStatus();
      send({ type: "source_control_status_loaded", status: payload });
      return payload;
    } catch (error) {
      send({
        type: "source_control_load_failed",
        error: error.message || sourceControlChrome.statusUnavailableNotice,
      });
      return null;
    }
  }

  async function openFile(file, scope = "unstaged") {
    if (!sourceControlCapabilityEnabled(capabilitiesFor())) return null;
    const path = file?.path || "";
    if (!path) return null;
    const sourceControlChrome = readChrome(getSourceControlChrome);
    const diffPanelChrome = readChrome(getDiffPanelChrome);
    const selectedScope = scope || file?.diffScopes?.[0] || "unstaged";
    send({ type: "source_control_file_selected", path, scope: selectedScope });
    send({ type: "source_control_diff_started" });
    try {
      const diff = await getSourceControlDiff(path, selectedScope);
      send({ type: "source_control_diff_loaded", diff });
      if (diff.available && diff.diff) {
        send({
          type: "diff_surface_opened",
          diffSurface: createDiffSurfaceState({
            title:
              formatTemplate(diffPanelChrome.sourceControlTitleTemplate, { path }) ||
              path ||
              diffPanelChrome.defaultTitle,
            diff: diff.diff,
            source: "source-control",
            filePath: path,
            chrome: diffPanelChrome,
          }),
        });
        return diff;
      }
      send({
        type: "source_control_diff_failed",
        error: diff.reason || sourceControlChrome.diffUnavailableNotice,
      });
      return null;
    } catch (error) {
      send({
        type: "source_control_diff_failed",
        error: error.message || sourceControlChrome.diffUnavailableNotice,
      });
      return null;
    }
  }

  return {
    loadStatus,
    openFile,
  };
}
