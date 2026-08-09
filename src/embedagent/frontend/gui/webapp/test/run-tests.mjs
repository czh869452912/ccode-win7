import { runActiveWorkspaceDataLoaderTests } from "./active-workspace-data-loader.test.mjs";
import { runActivityStateTests } from "./activity-state.test.mjs";
import { runActivityTimelineTests } from "./activity-timeline.test.mjs";
import { runAgentShellSourceTests } from "./agent-shell-source.test.mjs";
import { runAppCapabilityModelTests } from "./app-capability-model.test.mjs";
import { runAppCompositionTests } from "./app-composition.test.mjs";
import { runAppShellModelTests } from "./app-shell-model.test.mjs";
import { runAppWorkspaceTests } from "./app-workspaces.test.mjs";
import { runBrowserDialogServiceTests } from "./browser-dialog-service.test.mjs";
import { runClientRuntimeTests } from "./client-runtime.test.mjs";
import { runCommandCapabilitiesTests } from "./command-capabilities.test.mjs";
import { runCommandPaletteModelTests } from "./command-palette-model.test.mjs";
import { runCommandPaletteSourceTests } from "./command-palette-source.test.mjs";
import { runComposerCommandSearchTests } from "./composer-command-search.test.mjs";
import { runComposerComponentsSourceTests } from "./composer-components-source.test.mjs";
import { runComposerIntegrationSourceTests } from "./composer-integration-source.test.mjs";
import { runComposerInteractionModelTests } from "./composer-interaction-model.test.mjs";
import { runComposerPathContextTests } from "./composer-path-context.test.mjs";
import { runComposerStateTests } from "./composer-state.test.mjs";
import { runComposerTriggerTests } from "./composer-trigger.test.mjs";
import { runContributionModelTests } from "./contribution-model.test.mjs";
import { runContributionSurfaceStoreTests } from "./contribution-surface-store.test.mjs";
import { runControllerProtocolOwnershipTests } from "./controller-protocol-ownership.test.mjs";
import { runDiffModelTests } from "./diff-model.test.mjs";
import { runDiffSurfaceControllerTests } from "./diff-surface-controller.test.mjs";
import { runDynamicAgentCapabilityTests } from "./dynamic-agent-capabilities.test.mjs";
import { runFilePreviewControllerTests } from "./file-preview-controller.test.mjs";
import { runFilePreviewModelTests } from "./file-preview-model.test.mjs";
import { runHttpTransportTests } from "./http-transport.test.mjs";
import { runInitialAppLoadControllerTests } from "./initial-app-load-controller.test.mjs";
import { runInteractionModelTests } from "./interaction-model.test.mjs";
import { runInteractionResponseControllerTests } from "./interaction-response-controller.test.mjs";
import { runPreviewControllerTests } from "./preview-controller.test.mjs";
import { runPreviewSurfaceModelTests } from "./preview-surface-model.test.mjs";
import { runPreviewSurfaceSourceTests } from "./preview-surface-source.test.mjs";
import { runProtocolNormalizerTests } from "./protocol-normalizer.test.mjs";
import { runRespondingRequestIdsHandleTests } from "./responding-request-ids-handle.test.mjs";
import { runRunOutputStateTests } from "./run-output-state.test.mjs";
import { runSessionActivationControllerTests } from "./session-activation-controller.test.mjs";
import { runSessionCapabilityModelTests } from "./session-capability-model.test.mjs";
import { runSessionControllerTests } from "./session-controller.test.mjs";
import { runSessionListControllerTests } from "./session-list-controller.test.mjs";
import { runSessionLoadersTests } from "./session-loaders.test.mjs";
import { runSessionRuntimeTests } from "./session-runtime.test.mjs";
import { runSessionTransportControllerTests } from "./session-transport-controller.test.mjs";
import { runSessionTransportHandleTests } from "./session-transport-handle.test.mjs";
import { runShellSelectorTests } from "./shell-selectors.test.mjs";
import { runSocketEffectExecutorTests } from "./socket-effect-executor.test.mjs";
import { runSocketMessageControllerTests } from "./socket-message-controller.test.mjs";
import { runSocketMessageEffectsTests } from "./socket-message-effects.test.mjs";
import { runSourceControlCapabilityTests } from "./source-control-capability.test.mjs";
import { runSourceControlControllerTests } from "./source-control-controller.test.mjs";
import { runSourceControlStateTests } from "./source-control-state.test.mjs";
import { runStoreReducerTests } from "./store-reducer.test.mjs";
import { runTerminalControllerTests } from "./terminal-controller.test.mjs";
import { runTerminalShellSourceTests } from "./terminal-shell-source.test.mjs";
import { runTerminalStateTests } from "./terminal-state.test.mjs";
import { runThreadLifecycleControllerTests } from "./thread-lifecycle-controller.test.mjs";
import { runThreadStateTests } from "./thread-state.test.mjs";
import { runTimelineScrollControllerTests } from "./timeline-scroll-controller.test.mjs";
import { runTimelineUiStateTests } from "./timeline-ui-state.test.mjs";
import { runVisualDebugControllerTests } from "./visual-debug-controller.test.mjs";
import { runVisualDebugFixturesTests } from "./visual-debug-fixtures.test.mjs";
import { runVisualDebugRunnerTests } from "./visual-debug-runner.test.mjs";
import { runVisualLanguageCssTests } from "./visual-language-css.test.mjs";
import { runWebSocketLifecycleTests } from "./websocket-lifecycle.test.mjs";
import { runWorkbenchCommandControllerTests } from "./workbench-command-controller.test.mjs";
import { runWorkbenchKeyboardControllerTests } from "./workbench-keyboard-controller.test.mjs";
import { runWorkspaceControllerTests } from "./workspace-controller.test.mjs";
import { runWorkspaceFilesControllerTests } from "./workspace-files-controller.test.mjs";

async function main() {
  const synchronous = [
    runAgentShellSourceTests, runAppCapabilityModelTests, runAppCompositionTests,
    runAppShellModelTests, runAppWorkspaceTests, runActivityStateTests,
    runActivityTimelineTests, runBrowserDialogServiceTests, runCommandCapabilitiesTests,
    runCommandPaletteModelTests, runCommandPaletteSourceTests, runComposerCommandSearchTests,
    runComposerComponentsSourceTests, runComposerIntegrationSourceTests,
    runComposerInteractionModelTests, runComposerPathContextTests, runComposerStateTests,
    runComposerTriggerTests, runContributionModelTests, runContributionSurfaceStoreTests,
    runControllerProtocolOwnershipTests, runDiffModelTests, runDiffSurfaceControllerTests,
    runDynamicAgentCapabilityTests, runFilePreviewModelTests, runInteractionModelTests,
    runPreviewSurfaceModelTests, runPreviewSurfaceSourceTests, runProtocolNormalizerTests,
    runRespondingRequestIdsHandleTests, runRunOutputStateTests, runSessionCapabilityModelTests,
    runSessionRuntimeTests, runShellSelectorTests, runSocketMessageControllerTests,
    runSocketMessageEffectsTests, runSourceControlCapabilityTests, runSourceControlStateTests,
    runStoreReducerTests, runTerminalShellSourceTests, runTerminalStateTests, runThreadStateTests,
    runTimelineScrollControllerTests, runTimelineUiStateTests, runVisualDebugControllerTests,
    runVisualDebugFixturesTests, runVisualLanguageCssTests, runWebSocketLifecycleTests,
    runWorkbenchKeyboardControllerTests,
  ];
  synchronous.forEach((run) => run());

  const asynchronous = [
    runActiveWorkspaceDataLoaderTests, runClientRuntimeTests, runFilePreviewControllerTests,
    runHttpTransportTests, runInitialAppLoadControllerTests, runInteractionResponseControllerTests,
    runPreviewControllerTests, runSessionActivationControllerTests, runSessionControllerTests,
    runSessionListControllerTests, runSessionLoadersTests, runSessionTransportControllerTests,
    runSessionTransportHandleTests, runSocketEffectExecutorTests, runSourceControlControllerTests,
    runTerminalControllerTests, runThreadLifecycleControllerTests, runVisualDebugRunnerTests,
    runWorkbenchCommandControllerTests, runWorkspaceControllerTests, runWorkspaceFilesControllerTests,
  ];
  for (const run of asynchronous) await run();

  console.log("frontend helper checks passed");
}

await main();
