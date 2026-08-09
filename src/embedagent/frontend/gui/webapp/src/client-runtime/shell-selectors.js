import { readComposerDraft } from "../composer/composer-state.js";
import { readActiveThreadId, readThreadSessions } from "../session-runtime/thread-state.js";

function object(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function array(value) {
  return Array.isArray(value) ? value : [];
}

function clone(value) {
  if (Array.isArray(value)) return value.map(clone);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, clone(item)]));
}

function freeze(value) {
  if (!value || typeof value !== "object") return value;
  for (const item of Object.values(value)) freeze(item);
  return Object.freeze(value);
}

function contributionView(state) {
  const contributions = object(state.contribution);
  const items = array(contributions.items).map(clone);
  return {
    items,
    activeId: String(contributions.activeId || ""),
    active: items.find((item) => item.id === contributions.activeId) || null,
    data: {
      app: clone(state.app),
      diff: clone(state.diffSurface),
      files: clone(state.fileTree),
      filePreviews: clone(state.filePreviewsByPath),
      plan: clone(state.plan),
      previewServers: clone(object(state.app?.capabilities).preview?.localServers || []),
      runOutput: clone(state.runOutput),
      sourceControl: clone(state.sourceControl),
      terminal: clone(state.terminal),
    },
  };
}

export function selectAgentShellView(state = {}, options = {}) {
  const snapshot = object(state.snapshot);
  const app = object(state.app);
  const capabilities = object(app.capabilities);
  const sessionCapabilities = object(state.sessionCapabilities);
  const activity = object(options.activityRuntime);
  const currentSessionId = readActiveThreadId(state);
  const currentStatus = String(snapshot.status || "idle");
  const modeCatalog = object(sessionCapabilities.modeCatalog);
  const currentMode = String(
    snapshot.current_mode || state.requestedMode || Object.keys(modeCatalog)[0] || "",
  );
  const interaction = options.interaction || activity.currentInteraction || null;
  const timelineItems = array(activity.timelineRows || activity.timelineItems);
  const shell = object(app.shell || capabilities.shell);
  const commandPalette = object(state.contribution?.palette);

  return freeze({
    sessions: {
      items: readThreadSessions(state).map(clone),
      currentId: currentSessionId,
      activeWorkspace: app.activeWorkspace ? clone(app.activeWorkspace) : null,
      workspaces: array(app.workspaces).map(clone),
      hasActiveWorkspace: Boolean(app.hasActiveWorkspace),
      workspacePathInput: String(app.workspacePathInput || ""),
      workspaceError: String(app.workspaceError || ""),
      activatingWorkspace: Boolean(app.activatingWorkspace),
      productName: String(app.app?.productName || "EmbedAgent"),
    },
    timeline: {
      items: timelineItems.map(clone),
      view: clone(object(activity.timelineView)),
      thinking: Boolean(state.thinkingActive),
      historyIntegrity: clone(object(options.historyIntegrity)),
      terminationReason: String(state.terminationDisplayReason || state.terminationReason || ""),
      terminationMessage: String(state.terminationMessage || ""),
      chrome: clone(capabilities.chrome?.timeline || {}),
    },
    composer: {
      draft: readComposerDraft(state),
      canSubmit: Boolean(currentSessionId) && currentStatus === "idle",
      isRunning: ["running", "waiting_permission", "waiting_user_input"].includes(currentStatus),
      commands: clone(array(options.composerCommands)),
      commandGroupLabels: clone(object(options.commandGroupLabels)),
      fileTree: clone(array(state.fileTree)),
      chrome: clone(capabilities.chrome?.composer || {}),
      interactionChrome: clone(capabilities.chrome?.interaction || {}),
      interactionBusy: Boolean(options.interactionBusy),
      interactionNotice: options.interactionNotice || activity.interactionNotice || null,
    },
    modes: {
      current: currentMode,
      catalog: clone(modeCatalog),
    },
    interaction: clone(interaction),
    connection: {
      status: String(options.connectionStatus || "connected"),
      recovering: Boolean(options.recovering),
    },
    status: {
      session: currentStatus,
      turnsUsed: Number(state.turnsUsed || 0),
      maxTurns: Number(state.maxTurns || 0),
      context: clone(object(snapshot.context_usage)),
    },
    workflow: clone(object(snapshot.workflow_state || state.workflow)),
    shell: {
      descriptor: clone(shell),
      commands: clone(array(capabilities.workbenchCommands || shell.commands)),
      keybindings: clone(array(capabilities.keybindings || shell.keybindings)),
      palette: {
        open: Boolean(commandPalette.open),
        query: String(commandPalette.query || ""),
        commands: clone(array(options.paletteCommands)),
        config: clone(object(capabilities.commandPalette)),
      },
      contributions: contributionView(state),
      chrome: clone(object(capabilities.chrome)),
      capabilities: clone(capabilities),
    },
  });
}
