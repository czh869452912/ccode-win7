import assert from "node:assert/strict";

import { buildSurfacePanelProps } from "../src/app-runtime/surface-panel-props.js";

export function runSurfacePanelPropsTests() {
  const controller = {
    focusDiffFile: () => "focus",
    refreshSourceControl: () => "refresh",
    selectSourceControlFile: () => "select",
    changeAppSettings: () => "settings",
  };
  const state = {
    plan: { title: "Plan" },
    diffSurface: { title: "Diff" },
    sourceControl: { branch: "main" },
    app: { app: { productName: "EmbedAgent" } },
  };
  const appChrome = {
    surfacePanel: { emptyTitle: "No surface" },
  };
  const sourceControlChrome = { title: "Source Control" };
  const diffPanelChrome = { defaultTitle: "Diff" };

  const props = buildSurfacePanelProps({
    state,
    appChrome,
    sourceControlChrome,
    diffPanelChrome,
    surfacePanelController: controller,
  });

  assert.equal(props.plan, state.plan);
  assert.equal(props.diffSurface, state.diffSurface);
  assert.equal(props.sourceControl, state.sourceControl);
  assert.equal(props.sourceControlChrome, sourceControlChrome);
  assert.equal(props.diffPanelChrome, diffPanelChrome);
  assert.equal(props.appShell, state.app);
  assert.equal(props.chrome, appChrome.surfacePanel);
  assert.equal(props.onFocusDiffFile, controller.focusDiffFile);
  assert.equal(props.onRefreshSourceControl, controller.refreshSourceControl);
  assert.equal(props.onSelectSourceControlFile, controller.selectSourceControlFile);
  assert.equal(props.onAppSettingsChange, controller.changeAppSettings);

  const fallbackProps = buildSurfacePanelProps();
  assert.deepEqual(fallbackProps.chrome, {});
  assert.equal(typeof fallbackProps.onFocusDiffFile, "undefined");
}
