import { isRecord, validateShellDescriptor } from "./validation.js";
import { FRONTEND_PROTOCOL_SCHEMA_VERSION } from "../session-runtime/protocol-version.js";

export function emptyShellDescriptor() {
  return Object.freeze({
    schemaVersion: FRONTEND_PROTOCOL_SCHEMA_VERSION,
    commands: Object.freeze([]),
    surfaces: Object.freeze([]),
    keybindings: Object.freeze([]),
    toolPresentations: Object.freeze([]),
    timelineItems: Object.freeze([]),
    interactions: Object.freeze([]),
  });
}

function surfaceRecord(descriptor) {
  const metadata = isRecord(descriptor.metadata) ? descriptor.metadata : {};
  return Object.freeze({
    id: descriptor.id,
    kind: descriptor.id,
    title: descriptor.label,
    description: String(metadata.description || ""),
    placement: descriptor.placement,
    rendererKey: descriptor.rendererKey,
    launcher: true,
    launcherOrder: Number(metadata.order || 0),
    command: false,
    commandLabel: "",
    resourceId: String(metadata.resource_id || ""),
    defaultResourceId: String(metadata.default_resource_id || ""),
    closeBehavior: String(metadata.close_behavior || "closable"),
    readOnly: metadata.read_only === true,
    offline: metadata.offline === true,
    keywords: Array.isArray(metadata.keywords) ? metadata.keywords.map(String) : [],
    dispatch: {},
    bodyKind: String(metadata.body_kind || ""),
    panelKind: String(metadata.panel_kind || ""),
    openKind: String(metadata.open_kind || ""),
    activationKind: String(metadata.activation_kind || ""),
  });
}

function commandRecord(descriptor) {
  const availability = isRecord(descriptor.availability) ? descriptor.availability : {};
  const dispatch = isRecord(descriptor.dispatch) ? descriptor.dispatch : {};
  const commandName = dispatch.kind === "session.command"
    ? String(dispatch.command || "")
    : "";
  return Object.freeze({
    id: descriptor.id,
    group: descriptor.group,
    label: descriptor.label,
    description: descriptor.summary,
    slash: commandName ? `/${commandName}` : "",
    visibleWhen: String(availability.visible_when || "always"),
    keywords: [],
    dispatch,
  });
}

function keybindingRecord(descriptor) {
  const when = isRecord(descriptor.when) ? descriptor.when : {};
  return Object.freeze({
    commandId: descriptor.commandId,
    key: descriptor.keys.toLowerCase(),
    when: String(when.context || "always"),
  });
}

export function shellCapabilityModel(shell = emptyShellDescriptor()) {
  validateShellDescriptor(shell);
  const secondarySurfaces = shell.surfaces
    .filter((item) => item.placement === "secondary")
    .map(surfaceRecord);
  return Object.freeze({
    shell,
    appCommands: Object.freeze([]),
    workspaceCommands: Object.freeze([]),
    workbenchCommands: Object.freeze(shell.commands.map(commandRecord)),
    contributions: Object.freeze(secondarySurfaces),
    keybindings: Object.freeze(shell.keybindings.map(keybindingRecord)),
    commandPalette: Object.freeze({ groups: Object.freeze([]), labels: Object.freeze({}) }),
    chrome: Object.freeze({}),
    home: Object.freeze({}),
    sourceControl: Object.freeze({
      enabled: secondarySurfaces.some((item) => item.rendererKey === "source_control"),
    }),
    terminal: Object.freeze({
      enabled: secondarySurfaces.some((item) => item.rendererKey === "terminal"),
    }),
    preview: Object.freeze({
      enabled: secondarySurfaces.some((item) => item.rendererKey === "preview"),
    }),
    threadLifecycle: Object.freeze({}),
    emptyState: null,
  });
}
