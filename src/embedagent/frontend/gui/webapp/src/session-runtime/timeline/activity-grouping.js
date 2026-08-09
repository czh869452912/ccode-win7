function textValue(value, fallback = "") {
  if (value == null) return fallback;
  return String(value);
}

function numberValue(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function optionalNumberValue(value) {
  if (value === undefined || value === null || value === "") return undefined;
  const number = Number(value);
  return Number.isFinite(number) ? number : undefined;
}

function firstValue(...values) {
  for (const value of values) {
    if (value !== undefined && value !== null) return value;
  }
  return undefined;
}

function firstText(...values) {
  const value = firstValue(...values);
  return textValue(value);
}

export function buildInteractionNotice(snapshot, currentInteraction) {
  const interaction = snapshot?.pending_interaction;
  if (interaction && (snapshot?.pending_interaction_valid === false || interaction.valid === false || interaction.status === "expired")) {
    return {
      kind: "expired",
      interactionId: interaction.interaction_id || "",
      source: "session_snapshot",
    };
  }
  if (!currentInteraction && snapshot?.restore_stop_reason === "interaction_expired") {
    return {
      kind: "expired",
      interactionId: "",
      source: "session_restore",
    };
  }
  return null;
}

export function currentInteractionFromSnapshot(snapshot) {
  const interaction = snapshot?.pending_interaction;
  if (!interaction || snapshot?.pending_interaction_valid === false) return null;
  if (interaction.valid === false || interaction.status === "expired") return null;
  return normalizeComposerInteraction(interaction);
}

function normalizeActivityKind(kind) {
  const value = textValue(kind).trim();
  if (value === "user" || value === "assistant" || value === "reasoning" || value === "tool") {
    return value;
  }
  if (value === "compact") return "compact";
  if (value === "interaction_requested" || value === "interaction_resolved") return value;
  if (value === "command_result") return value;
  return value || "system";
}

export function normalizeHistoryActivities(activities = []) {
  return (Array.isArray(activities) ? activities : []).map((item, index) => {
    const data = item?.data && typeof item.data === "object" ? item.data : {};
    const kind = normalizeActivityKind(item?.kind);
    const turnId = textValue(item?.turnId || item?.turn_id);
    const stepId = textValue(item?.stepId || item?.step_id);
    const stepIndex = numberValue(item?.stepIndex || item?.step_index);
    const callId = textValue(item?.callId || item?.call_id);
    const toolName = textValue(item?.toolName || item?.tool_name);
    const interactionId = firstText(
      item?.interactionId,
      item?.interaction_id,
      item?.request?.request_id,
      item?.request?.permission_id,
      item?.request_id,
      item?.permission_id,
    );
    const commandName = firstText(item?.commandName, item?.command_name, data.commandName, data.command_name);
    const changedFiles = firstValue(item?.changedFiles, item?.changed_files, data.changedFiles, data.changed_files, []);
    return {
      ...(item || {}),
      id: textValue(item?.id || callId || `${kind}-${turnId || "session"}-${index}`),
      kind,
      turnId,
      stepId,
      stepIndex,
      content: textValue(item?.content),
      status: textValue(item?.status),
      projectionSource: textValue(item?.projectionSource || item?.projection_source),
      projectionKind: textValue(item?.projectionKind || item?.projection_kind || "activity"),
      synthetic: Boolean(item?.synthetic),
      toolName,
      tool_name: toolName,
      toolLabel: textValue(item?.toolLabel || item?.tool_label),
      tool_label: textValue(item?.toolLabel || item?.tool_label),
      callId,
      call_id: callId,
      arguments: item?.arguments && typeof item.arguments === "object" ? item.arguments : {},
      data: item?.data,
      error: textValue(item?.error),
      label: firstText(item?.label, item?.toolLabel, item?.tool_label, item?.toolTitle, item?.tool_title, toolName),
      itemType: firstText(item?.itemType, item?.item_type, data.itemType, data.item_type),
      item_type: firstText(item?.itemType, item?.item_type, data.itemType, data.item_type),
      requestKind: firstText(item?.requestKind, item?.request_kind, data.requestKind, data.request_kind),
      request_kind: firstText(item?.requestKind, item?.request_kind, data.requestKind, data.request_kind),
      toolTitle: firstText(item?.toolTitle, item?.tool_title, data.toolTitle, data.tool_title),
      tool_title: firstText(item?.toolTitle, item?.tool_title, data.toolTitle, data.tool_title),
      toolLifecycleStatus: firstText(
        item?.toolLifecycleStatus,
        item?.tool_lifecycle_status,
        data.toolLifecycleStatus,
        data.tool_lifecycle_status,
      ),
      tool_lifecycle_status: firstText(
        item?.toolLifecycleStatus,
        item?.tool_lifecycle_status,
        data.toolLifecycleStatus,
        data.tool_lifecycle_status,
      ),
      command: firstText(item?.command, data.command),
      rawCommand: firstText(item?.rawCommand, item?.raw_command, data.rawCommand, data.raw_command),
      raw_command: firstText(item?.rawCommand, item?.raw_command, data.rawCommand, data.raw_command),
      detail: firstText(item?.detail, data.detail),
      sourceActivityKind: firstText(
        item?.sourceActivityKind,
        item?.source_activity_kind,
        data.sourceActivityKind,
        data.source_activity_kind,
      ),
      source_activity_kind: firstText(
        item?.sourceActivityKind,
        item?.source_activity_kind,
        data.sourceActivityKind,
        data.source_activity_kind,
      ),
      changedFiles: Array.isArray(changedFiles) ? changedFiles : [],
      changed_files: Array.isArray(changedFiles) ? changedFiles : [],
      toolData: firstValue(item?.toolData, item?.tool_data, data.toolData, data.tool_data, data.item),
      tool_data: firstValue(item?.toolData, item?.tool_data, data.toolData, data.tool_data, data.item),
      commandName,
      command_name: commandName,
      success: Boolean(item?.success),
      request: item?.request || null,
      answered: Boolean(item?.answered),
      interactionId,
      interaction_id: interactionId,
      recentTurns: optionalNumberValue(firstValue(item?.recentTurns, item?.recent_turns)),
      summarizedTurns: optionalNumberValue(firstValue(item?.summarizedTurns, item?.summarized_turns)),
      approxTokensAfter: optionalNumberValue(firstValue(item?.approxTokensAfter, item?.approx_tokens_after)),
      permissionCategory: textValue(item?.permissionCategory || item?.permission_category),
      permission_category: textValue(item?.permissionCategory || item?.permission_category),
      supportsDiffPreview: Boolean(item?.supportsDiffPreview || item?.supports_diff_preview),
      supports_diff_preview: Boolean(item?.supportsDiffPreview || item?.supports_diff_preview),
      progressRendererKey: textValue(item?.progressRendererKey || item?.progress_renderer_key),
      progress_renderer_key: textValue(item?.progressRendererKey || item?.progress_renderer_key),
      resultRendererKey: textValue(item?.resultRendererKey || item?.result_renderer_key),
      result_renderer_key: textValue(item?.resultRendererKey || item?.result_renderer_key),
    };
  });
}

function createTurnGroup(turnId) {
  return {
    turnId,
    userItem: null,
    leadingSystemItems: [],
    steps: [],
    trailingTurnItems: [],
    sessionFallbackItems: [],
    _stepMap: new Map(),
  };
}

function getTurnGroup(groups, turnMap, item) {
  const fallbackId = item.kind === "user" ? item.id : `session-${item.id}`;
  const key = item.turnId || fallbackId;
  if (!turnMap.has(key)) {
    const group = createTurnGroup(key);
    turnMap.set(key, group);
    groups.push(group);
  }
  return turnMap.get(key);
}

function getStepGroup(turn, item) {
  const key = item.stepId || `step-${turn.steps.length + 1}`;
  if (!turn._stepMap.has(key)) {
    const step = {
      stepId: key,
      stepIndex: item.stepIndex || turn.steps.length + 1,
      projectionSource: item.projectionSource || "",
      projectionKind: item.projectionKind || "",
      synthetic: Boolean(item.synthetic),
      activityItems: [],
      assistantItem: null,
    };
    turn._stepMap.set(key, step);
    turn.steps.push(step);
  }
  const step = turn._stepMap.get(key);
  if (item.projectionSource && !step.projectionSource) step.projectionSource = item.projectionSource;
  if (item.projectionKind && !step.projectionKind) step.projectionKind = item.projectionKind;
  if (item.synthetic) step.synthetic = true;
  return step;
}

export function projectActivityTurnGroups(items = []) {
  const groups = [];
  const turnMap = new Map();
  for (const item of items || []) {
    const group = getTurnGroup(groups, turnMap, item);
    if (item.kind === "user") {
      group.userItem = item;
      continue;
    }
    if (item.kind === "command_result" && !item.turnId) {
      group.sessionFallbackItems.push({ ...item, kind: "command_result_fallback" });
      continue;
    }
    if (item.stepId) {
      const step = getStepGroup(group, item);
      if (item.kind === "assistant") {
        step.assistantItem = item;
      } else {
        step.activityItems.push(item);
      }
      continue;
    }
    if (item.kind === "system" || item.kind === "compact") {
      if (group.steps.length === 0 && group.trailingTurnItems.length === 0) {
        group.leadingSystemItems.push(item);
      } else {
        group.trailingTurnItems.push(item);
      }
      continue;
    }
    if (!item.turnId) {
      group.sessionFallbackItems.push(item);
      continue;
    }
    group.trailingTurnItems.push(item);
  }
  return groups.map((group) => ({
    turnId: group.turnId,
    userItem: group.userItem,
    leadingSystemItems: group.leadingSystemItems,
    steps: group.steps.sort((left, right) => (left.stepIndex || 0) - (right.stepIndex || 0)),
    trailingTurnItems: group.trailingTurnItems,
    sessionFallbackItems: group.sessionFallbackItems,
  }));
}

import { normalizeComposerInteraction } from "../interaction-model.js";
