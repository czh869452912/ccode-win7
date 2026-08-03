export function capabilitySnapshot(overrides = {}) {
  return {
    schema_version: 1,
    modes: [],
    commands: [],
    tools: [],
    workflow_packages: [],
    agent_application: {},
    agent_applications: [],
    resources: [],
    model_profiles: [],
    empty_state: {},
    ...overrides,
  };
}

export function modeDescriptor(id, label = id, overrides = {}) {
  return {
    id,
    label,
    description: "",
    icon_key: "",
    color_token: "",
    command_id: `mode.${id}`,
    ...overrides,
  };
}

export function commandDescriptor(id, label, overrides = {}) {
  return {
    id,
    label,
    group: "command",
    dispatch: {},
    shortcut: "",
    availability: {},
    summary: "",
    source_type: "",
    source_id: "",
    ...overrides,
  };
}

export function toolDescriptor(name, label = name, overrides = {}) {
  return {
    name,
    label,
    icon_key: "",
    renderer_key: "generic",
    permission_category: "other",
    metadata: {},
    ...overrides,
  };
}

export function workflowPackageDescriptor(id, label = id, overrides = {}) {
  return {
    id,
    label,
    active: false,
    state: {},
    metadata: {},
    ...overrides,
  };
}

export function agentApplicationDescriptor(id, label = id, overrides = {}) {
  return {
    id,
    label,
    profile_id: "",
    workflow_package_ids: [],
    active: false,
    source_type: "",
    source_id: "",
    default: false,
    metadata: {},
    ...overrides,
  };
}
