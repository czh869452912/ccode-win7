import { startTransition, useEffect, useMemo, useReducer, useRef, useState } from "react";

import { buildCommandGroupLabels } from "../workbench/command-palette-model.js";
import {
  buildCommandVisibilityContext,
  visibleCommands,
} from "../workbench/commands.js";
import { buildSessionActivityRuntime } from "../session-runtime/activity-state.js";
import { buildComposerCommandsFromCapabilities } from "../session-runtime/command-capabilities.js";
import { createSessionTransportState } from "../session-runtime/session-transport-state.js";
import { readActiveThreadId, readThreadHistoryIntegrity } from "../session-runtime/thread-state.js";
import { createBrowserAppRuntime } from "../app-runtime/browser-app-runtime.js";
import { INITIAL_REQUESTED_MODE, initialState, runtimeReducer } from "./runtime-reducer.js";
import { selectAgentShellView } from "./shell-selectors.js";

export function useAgentShellRuntime(protocol) {
  const [state, dispatch] = useReducer(runtimeReducer, initialState);
  const [respondingRequestIds, setRespondingRequestIds] = useState([]);
  const [sessionTransport, setSessionTransport] = useState(() => createSessionTransportState());
  const timelineRef = useRef(null);
  const runtimeStateRef = useRef(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  const currentSessionId = readActiveThreadId(state);
  const currentMode = state.snapshot?.current_mode || state.requestedMode;
  const currentStatus = state.snapshot?.status || "idle";
  const sessionCapabilities = state.sessionCapabilities || {};
  const appCapabilities = state.app?.capabilities || {};
  const toolCatalog = sessionCapabilities.toolCatalog || {};

  const activityRuntime = useMemo(
    () => buildSessionActivityRuntime({
      snapshot: state.snapshot,
      sessionTransport,
      activities: state.activities,
      defaultMode: INITIAL_REQUESTED_MODE,
      activeTurnId: state.activeTurnId,
      thinkingActive: state.thinkingActive,
      toolCatalog,
    }),
    [
      sessionTransport,
      state.activeTurnId,
      state.activities,
      state.snapshot,
      state.thinkingActive,
      toolCatalog,
    ],
  );
  runtimeStateRef.current = activityRuntime;

  const browserAppRuntime = useMemo(
    () => createBrowserAppRuntime({
      protocol,
      dispatch,
      getState: () => stateRef.current,
      defaultMode: INITIAL_REQUESTED_MODE,
      getActivityRuntime: () => runtimeStateRef.current || {},
      getTimelineElement: () => timelineRef.current,
      onSessionTransportChange: setSessionTransport,
      onRespondingRequestIdsChange: setRespondingRequestIds,
      browser: {
        windowObject: window,
        documentObject: document,
        getComputedStyleFn: getComputedStyle,
        scheduleMessage: startTransition,
        timer: window,
      },
    }),
    [protocol],
  );
  const clientActions = browserAppRuntime.actions;

  useEffect(() => {
    void browserAppRuntime.start();
    return () => browserAppRuntime.close();
  }, [browserAppRuntime]);

  useEffect(() => {
    void clientActions.dispatchAction(
      "interaction.sync",
      activityRuntime.currentInteraction?.interactionId || "",
    );
  }, [activityRuntime.currentInteraction?.interactionId, clientActions]);

  useEffect(() => {
    void clientActions.dispatchAction("timeline.sync_bottom");
  }, [activityRuntime.currentInteraction, activityRuntime.timelineRows, clientActions, state.thinkingActive]);

  useEffect(() => {
    void clientActions.dispatchAction("visual_debug.refresh");
  }, [activityRuntime.timelineItems, clientActions, state.requestedMode]);

  const composerCommands = useMemo(
    () => buildComposerCommandsFromCapabilities(sessionCapabilities, {
      defaultGroupId: appCapabilities.chrome?.composer?.commandMenu?.defaultCommandGroupId || "",
    }),
    [appCapabilities.chrome, sessionCapabilities],
  );
  const commandGroupLabels = useMemo(
    () => buildCommandGroupLabels(appCapabilities.commandPalette),
    [appCapabilities.commandPalette],
  );
  const commandContext = useMemo(
    () => buildCommandVisibilityContext({
      currentSessionId,
      currentStatus,
      appState: state.app,
      paletteOpen: state.contribution?.palette?.open,
      sessionCapabilities,
      appCapabilities,
    }),
    [appCapabilities, currentSessionId, currentStatus, sessionCapabilities, state.app, state.contribution?.palette?.open],
  );
  const paletteCommands = useMemo(() => visibleCommands(commandContext), [commandContext]);
  const currentInteractionId = activityRuntime.currentInteraction?.interactionId || "";
  const view = useMemo(
    () => selectAgentShellView(state, {
      activityRuntime,
      commandGroupLabels,
      composerCommands,
      connectionStatus: activityRuntime.transportView?.connectionState,
      historyIntegrity: readThreadHistoryIntegrity(state),
      interaction: activityRuntime.currentInteraction,
      interactionBusy: Boolean(currentInteractionId && respondingRequestIds.includes(currentInteractionId)),
      interactionNotice: state.interactionNotice || activityRuntime.interactionNotice,
      paletteCommands,
      recovering: activityRuntime.transportView?.reloadState !== "healthy",
    }),
    [
      activityRuntime,
      commandGroupLabels,
      composerCommands,
      currentInteractionId,
      paletteCommands,
      respondingRequestIds,
      state,
    ],
  );

  const actions = useMemo(() => Object.freeze({
    activateWorkspace: clientActions.activateWorkspace,
    archiveSession: clientActions.archiveSession,
    cancelSession: clientActions.cancelSession,
    closeContribution: (surface) => clientActions.dispatchAction("surface.close", surface),
    createSession: clientActions.createSession,
    executeCommand: clientActions.executeCommand,
    forkSession: clientActions.forkSession,
    loadContribution: (key, ...args) => clientActions.dispatchAction(key, ...args),
    onTimelineScroll: (...args) => clientActions.dispatchAction("timeline.scroll", ...args),
    openCommandPalette: () => clientActions.dispatchAction("command_palette.open"),
    openDiff: (...args) => clientActions.dispatchAction("diff.open", ...args),
    openFile: (...args) => clientActions.dispatchAction("file.open", ...args),
    openWorkspace: (path) => clientActions.activateWorkspace({ path }),
    refreshSessions: () => clientActions.dispatchAction("session.reload_list"),
    renameSession: clientActions.renameSession,
    respondToInteraction: clientActions.respondToInteraction,
    selectContribution: (surface) => clientActions.dispatchAction("surface.activate", surface),
    selectPaletteCommand: (command) => clientActions.dispatchAction("command_palette.select_command", command),
    selectPaletteSession: (sessionId) => clientActions.dispatchAction("command_palette.select_session", sessionId),
    selectPaletteWorkspace: (workspaceId) => clientActions.dispatchAction("command_palette.select_workspace", workspaceId),
    selectSession: clientActions.selectSession,
    sendMessage: () => clientActions.dispatchAction("composer.send"),
    setComposerDraft: (value) => clientActions.dispatchAction("composer.set_draft", value),
    setMode: clientActions.setMode,
    setPaletteQuery: (query) => clientActions.dispatchAction("command_palette.query", query),
    setWorkspacePath: (value) => clientActions.dispatchAction("workspace.path_changed", value),
    closeCommandPalette: () => clientActions.dispatchAction("command_palette.close"),
  }), [clientActions]);

  return { actions, timelineRef, view };
}
