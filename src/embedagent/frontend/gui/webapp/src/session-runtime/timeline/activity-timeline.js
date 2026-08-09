import { ACTIVITY_ROW_KINDS, numberValue, stringValue, timestampValue } from "./activity-types.js";
import { summarizeChangedFiles } from "./diff-activity.js";
import { normalizeWorkEntry } from "./tool-activity.js";

function messageRow(item, role) {
  return {
    id: stringValue(item?.id || `${role}-${item?.turnId || ""}`),
    kind: ACTIVITY_ROW_KINDS.MESSAGE,
    role,
    turnId: stringValue(item?.turnId || item?.turn_id),
    stepId: stringValue(item?.stepId || item?.step_id),
    stepIndex: numberValue(item?.stepIndex || item?.step_index),
    createdAt: timestampValue(item?.createdAt, item?.created_at),
    completedAt: timestampValue(item?.completedAt, item?.completed_at),
    content: stringValue(item?.content),
    streaming: Boolean(item?.streaming),
    rawItem: item || {},
  };
}

function reasoningRow(item) {
  const content = stringValue(item?.content);
  const wordCount = content.trim() ? content.trim().split(/\s+/).length : 0;
  return {
    id: stringValue(item?.id || `reasoning-${item?.turnId || item?.turn_id || "row"}`),
    kind: "reasoning",
    turnId: stringValue(item?.turnId || item?.turn_id),
    stepId: stringValue(item?.stepId || item?.step_id),
    stepIndex: numberValue(item?.stepIndex || item?.step_index),
    createdAt: timestampValue(item?.createdAt, item?.created_at),
    completedAt: timestampValue(item?.completedAt, item?.completed_at),
    label: stringValue(item?.label),
    content,
    wordCount,
    streaming: Boolean(item?.streaming),
    rawItem: item || {},
  };
}

function contextSummaryRow(item, placement = "fold_body") {
  return {
    id: stringValue(item?.id || `context-${item?.turnId || item?.turn_id || "row"}`),
    kind: ACTIVITY_ROW_KINDS.CONTEXT_SUMMARY,
    turnId: stringValue(item?.turnId || item?.turn_id),
    createdAt: timestampValue(item?.createdAt, item?.created_at),
    placement,
    tone: "context",
    label: stringValue(item?.label),
    content: stringValue(item?.content || item?.summary),
    summarizedTurns:
      item?.summarizedTurns !== undefined
        ? numberValue(item.summarizedTurns)
        : item?.summarized_turns !== undefined
          ? numberValue(item.summarized_turns)
          : undefined,
    recentTurns:
      item?.recentTurns !== undefined
        ? numberValue(item.recentTurns)
        : item?.recent_turns !== undefined
          ? numberValue(item.recent_turns)
          : undefined,
    approxTokensAfter:
      item?.approxTokensAfter !== undefined
        ? numberValue(item.approxTokensAfter)
        : item?.approx_tokens_after !== undefined
          ? numberValue(item.approx_tokens_after)
          : undefined,
    rawItem: item || {},
  };
}

function commandResultContent(item) {
  return stringValue(
    item?.content ||
      item?.message ||
      item?.summary ||
      item?.data?.message ||
      item?.data?.summary ||
      "",
  );
}

function commandResultRow(item) {
  const commandName = stringValue(item?.commandName || item?.command_name);
  return {
    id: stringValue(item?.id || `command-${commandName}-${item?.turnId || item?.turn_id || "row"}`),
    kind: ACTIVITY_ROW_KINDS.COMMAND_RESULT,
    turnId: stringValue(item?.turnId || item?.turn_id),
    createdAt: timestampValue(item?.createdAt, item?.created_at),
    commandName,
    label: stringValue(item?.label),
    success: item?.success !== false,
    tone: item?.success === false ? "error" : "context",
    content: commandResultContent(item),
    data: item?.data || {},
    rawItem: item || {},
  };
}

function normalizeReviewFinding(finding, index) {
  return {
    id: stringValue(finding?.id || `finding-${index + 1}`),
    severity: stringValue(finding?.severity || ""),
    priority: finding?.priority !== undefined ? numberValue(finding.priority) : undefined,
    title: stringValue(finding?.title || finding?.message),
    body: stringValue(finding?.body || finding?.detail || finding?.description || ""),
    file: stringValue(finding?.file || finding?.path || ""),
    line: finding?.line !== undefined ? numberValue(finding.line) : undefined,
  };
}

function reviewResultRow(item) {
  const review = item?.data?.review || item?.review || {};
  const findings = Array.isArray(review.findings)
    ? review.findings.map((finding, index) => normalizeReviewFinding(finding, index))
    : [];
  const residualRisks = Array.isArray(review.residual_risks)
    ? review.residual_risks.map((risk) => stringValue(risk)).filter(Boolean)
    : Array.isArray(review.residualRisks)
      ? review.residualRisks.map((risk) => stringValue(risk)).filter(Boolean)
      : [];
  return {
    ...commandResultRow(item),
    kind: ACTIVITY_ROW_KINDS.REVIEW_RESULT,
    commandName: stringValue(item?.commandName || item?.command_name),
    label: stringValue(item?.label),
    findings,
    residualRisks,
  };
}

function workingRow({ activeTurnId, idSuffix = "active", createdAt = "" } = {}) {
  return {
    id: `working-${activeTurnId || idSuffix || "active"}`,
    kind: ACTIVITY_ROW_KINDS.WORKING,
    turnId: stringValue(activeTurnId),
    createdAt: timestampValue(createdAt),
    streaming: true,
  };
}

function systemNoticeRow(item) {
  return {
    id: stringValue(item?.id || "system-notice"),
    kind: ACTIVITY_ROW_KINDS.SYSTEM_NOTICE,
    turnId: stringValue(item?.turnId || item?.turn_id),
    createdAt: timestampValue(item?.createdAt, item?.created_at),
    tone: stringValue(item?.tone || "context"),
    content: stringValue(item?.content || item?.label),
    rawItem: item || {},
  };
}

function experienceItemText(item) {
  if (item == null) return "";
  if (typeof item !== "object") return stringValue(item);
  const parts = [];
  for (const key of ["kind", "path", "command", "message", "reason"]) {
    const value = stringValue(item?.[key]).trim();
    if (value && !parts.includes(value)) parts.push(value);
  }
  return parts.join(" ");
}

function experienceListText(items) {
  if (!Array.isArray(items)) return "";
  return items.map(experienceItemText).filter(Boolean).join(", ");
}

function turnExperienceSummaryRow(turnExperience) {
  if (!turnExperience || typeof turnExperience !== "object") return null;
  const completed = experienceListText(turnExperience.completed);
  const unverified = experienceListText(turnExperience.unverified);
  const nextSteps = experienceListText(turnExperience.next_steps || turnExperience.nextSteps);
  const parts = [];
  if (completed) parts.push(`Done: ${completed}`);
  if (unverified) parts.push(`Unverified: ${unverified}`);
  if (nextSteps) parts.push(`Next: ${nextSteps}`);
  if (parts.length === 0) return null;
  return {
    id: "turn-experience-summary",
    kind: ACTIVITY_ROW_KINDS.SYSTEM_NOTICE,
    tone: unverified || turnExperience.status === "blocked" ? "warning" : "context",
    content: parts.join(" · "),
    rawItem: turnExperience,
  };
}

function activityRowForItem(item, context = {}) {
  if (!item) return null;
  if (item.kind === "tool") return normalizeWorkEntry(item, context);
  if (
    item.kind === "interaction" ||
    item.kind === "interaction_requested" ||
    item.kind === "interaction_resolved"
  ) return null;
  if (item.kind === "reasoning") return item.streaming ? null : reasoningRow(item);
  if (item.kind === "compact") return contextSummaryRow(item);
  if (item.kind === "command_result" || item.kind === "command_result_fallback") {
    if (item?.data?.review || item?.review) {
      return reviewResultRow(item);
    }
    return commandResultRow(item);
  }
  if (item.kind === "system") return systemNoticeRow(item);
  return null;
}

function allTurnItems(group) {
  const items = [];
  if (group?.userItem) items.push(group.userItem);
  for (const item of group?.leadingSystemItems || []) items.push(item);
  for (const item of group?.systemItems || []) items.push(item);
  for (const step of group?.steps || []) {
    for (const item of step?.activityItems || []) items.push(item);
    if (step?.assistantItem) items.push(step.assistantItem);
  }
  for (const item of group?.trailingTurnItems || []) items.push(item);
  for (const item of group?.detachedItems || []) items.push(item);
  for (const item of group?.sessionFallbackItems || []) items.push(item);
  return items;
}

function turnActivityEntries(group, context = {}) {
  const entries = [];
  function pushActivity(item) {
    const row = activityRowForItem(item, context);
    if (row) entries.push(row);
  }
  for (const item of (group?.leadingSystemItems || []).concat(group?.systemItems || [])) {
    if (item?.kind === "compact") pushActivity(item);
  }
  for (const step of group?.steps || []) {
    for (const item of step?.activityItems || []) {
      pushActivity(item);
    }
  }
  for (const item of group?.trailingTurnItems || []) {
    if (
      item?.kind === "tool" ||
      item?.kind === "compact" ||
      item?.kind === "interaction_requested" ||
      item?.kind === "interaction_resolved"
    ) {
      pushActivity(item);
    }
  }
  for (const item of group?.detachedItems || []) {
    if (
      item?.kind === "tool" ||
      item?.kind === "compact" ||
      item?.kind === "interaction_requested" ||
      item?.kind === "interaction_resolved"
    ) {
      pushActivity(item);
    }
  }
  return entries;
}

function assistantRowsForTurn(group) {
  const rows = [];
  for (const step of group?.steps || []) {
    if (step?.assistantItem) rows.push(messageRow(step.assistantItem, "assistant"));
  }
  return rows;
}

function rowForOpenPlacement(row, context) {
  if (context?.openPlacement && row?.kind === ACTIVITY_ROW_KINDS.CONTEXT_SUMMARY) {
    return { ...row, kind: ACTIVITY_ROW_KINDS.SYSTEM_NOTICE, placement: "active_turn_boundary" };
  }
  return row;
}

function orderedOpenRowsForTurn(group, context = {}) {
  const rows = [];
  for (const item of (group?.leadingSystemItems || []).concat(group?.systemItems || [])) {
    if (item?.kind !== "compact") continue;
    const row = activityRowForItem(item, context);
    if (row) rows.push(rowForOpenPlacement(row, context));
  }
  for (const step of group?.steps || []) {
    for (const item of step?.activityItems || []) {
      const row = activityRowForItem(item, context);
      if (row) rows.push(rowForOpenPlacement(row, context));
    }
    if (step?.assistantItem) {
      rows.push(messageRow(step.assistantItem, "assistant"));
    }
  }
  for (const item of (group?.trailingTurnItems || []).concat(group?.detachedItems || [])) {
    if (
      item?.kind === "tool" ||
      item?.kind === "compact" ||
      item?.kind === "interaction_requested" ||
      item?.kind === "interaction_resolved"
    ) {
      const row = activityRowForItem(item, context);
      if (row) rows.push(rowForOpenPlacement(row, context));
    }
  }
  return rows;
}

function terminalAssistantItemForTurn(group) {
  for (let index = (group?.steps || []).length - 1; index >= 0; index -= 1) {
    const item = group.steps[index]?.assistantItem;
    if (item) return item;
  }
  return null;
}

function stepOrderValue(step, fallback) {
  const value = numberValue(step?.stepIndex || step?.step_index, NaN);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function terminalAssistantStepOrder(group) {
  const terminalAssistantItem = terminalAssistantItemForTurn(group);
  if (!terminalAssistantItem) return NaN;
  const terminalId = stringValue(terminalAssistantItem?.id);
  const steps = group?.steps || [];
  for (let index = steps.length - 1; index >= 0; index -= 1) {
    const assistantItem = steps[index]?.assistantItem;
    if (!assistantItem) continue;
    const assistantId = stringValue(assistantItem?.id);
    if ((terminalId && assistantId === terminalId) || assistantItem === terminalAssistantItem) {
      return stepOrderValue(steps[index], index + 1);
    }
  }
  return NaN;
}

function foldEntriesForTurn(group, context = {}) {
  const terminalAssistantItem = terminalAssistantItemForTurn(group);
  return orderedOpenRowsForTurn(group, context).filter((row) => {
    if (row.kind !== ACTIVITY_ROW_KINDS.MESSAGE || row.role !== "assistant") return true;
    return row.id !== stringValue(terminalAssistantItem?.id);
  });
}

function hasInterruptedWork(entries) {
  return entries.some((entry) => entry.tone === "interrupted" || entry.tone === "discarded");
}

function isErrorWorkEntry(entry) {
  return entry?.kind === ACTIVITY_ROW_KINDS.WORK && (entry.status === "error" || entry.tone === "error");
}

function hasTerminalErrorWork(group, workEntries, context = {}) {
  if (!workEntries.some(isErrorWorkEntry)) return false;
  const terminalOrder = terminalAssistantStepOrder(group);
  if (!Number.isFinite(terminalOrder)) return true;

  let stepErrorCount = 0;
  const steps = group?.steps || [];
  for (let index = 0; index < steps.length; index += 1) {
    const stepOrder = stepOrderValue(steps[index], index + 1);
    for (const item of steps[index]?.activityItems || []) {
      const row = activityRowForItem(item, context);
      if (!isErrorWorkEntry(row)) continue;
      stepErrorCount += 1;
      if (stepOrder >= terminalOrder) return true;
    }
  }

  return workEntries.filter(isErrorWorkEntry).length > stepErrorCount;
}

function timestampMs(value) {
  const parsed = Date.parse(stringValue(value));
  return Number.isFinite(parsed) ? parsed : NaN;
}

function minTimestamp(...values) {
  let best = "";
  let bestMs = NaN;
  for (const value of values.flat()) {
    const text = stringValue(value);
    const parsed = timestampMs(text);
    if (!Number.isFinite(parsed)) continue;
    if (!Number.isFinite(bestMs) || parsed < bestMs) {
      best = text;
      bestMs = parsed;
    }
  }
  return best;
}

function maxTimestamp(...values) {
  let best = "";
  let bestMs = NaN;
  for (const value of values.flat()) {
    const text = stringValue(value);
    const parsed = timestampMs(text);
    if (!Number.isFinite(parsed)) continue;
    if (!Number.isFinite(bestMs) || parsed > bestMs) {
      best = text;
      bestMs = parsed;
    }
  }
  return best;
}

function turnStartTimestamp(group, entries) {
  const candidates = [
    group?.startedAt,
    group?.started_at,
    group?.userItem?.createdAt,
    group?.userItem?.created_at,
    ...(entries || []).map((entry) => entry.createdAt),
  ];
  return minTimestamp(candidates);
}

function turnEndTimestamp(group, entries) {
  const assistantRows = assistantRowsForTurn(group);
  const candidates = [
    group?.completedAt,
    group?.completed_at,
    ...assistantRows.map((row) => row.completedAt || row.createdAt),
    ...(entries || []).map((entry) => entry.completedAt || entry.createdAt),
  ];
  return maxTimestamp(candidates);
}

export function isTurnFoldedByDefault(group, context = {}) {
  const entries = turnActivityEntries(group, context);
  const foldEntries = foldEntriesForTurn(group, context);
  const workEntries = entries.filter((entry) => entry.kind === ACTIVITY_ROW_KINDS.WORK);
  if (foldEntries.length === 0) return false;
  if (group?.turnId && group.turnId === context.activeTurnId && context.currentStatus === "running") {
    return false;
  }
  if (hasInterruptedWork(workEntries)) return false;
  if (workEntries.some((entry) => entry.status === "running" || entry.tone === "running")) return false;
  if (hasTerminalErrorWork(group, workEntries, context)) return false;
  return assistantRowsForTurn(group).length > 0;
}

function pushLooseItem(push, item, context = {}) {
  if (!item) return;
  if (
    item.kind === "interaction" ||
    item.kind === "interaction_requested" ||
    item.kind === "interaction_resolved"
  ) return;
  if (item.kind === "assistant") push(messageRow(item, "assistant"));
  else if (item.kind === "user") push(messageRow(item, "user"));
  else {
    const row = activityRowForItem(item, context);
    push(row || systemNoticeRow(item));
  }
}

function diffSummaryRow(group, context = {}) {
  const changed = summarizeChangedFiles(allTurnItems(group), { toolCatalog: context.toolCatalog || {} });
  if (changed.files.length === 0) return null;
  return {
    id: `diff-summary-${group?.turnId || changed.files.map((file) => file.path).join("-")}`,
    kind: ACTIVITY_ROW_KINDS.DIFF_SUMMARY,
    turnId: stringValue(group?.turnId),
    files: changed.files,
    changedFiles: changed.files,
    additions: changed.additions,
    deletions: changed.deletions,
  };
}

export function buildActivityTimelineRows({
  turnGroups = [],
  currentStatus = "idle",
  activeTurnId = "",
  currentInteraction = null,
  interactionNotice = null,
  thinkingActive = false,
  turnExperience = null,
  toolCatalog = {},
} = {}) {
  const rows = [];
  const context = { currentStatus, activeTurnId, toolCatalog };
  function pushRow(row) {
    if (!row) return;
    rows.push(row);
  }
  for (const group of turnGroups || []) {
    if (group?.userItem) pushRow(messageRow(group.userItem, "user"));
    for (const item of group?.leadingSystemItems || []) {
      if (item?.kind === "compact") continue;
      pushLooseItem(pushRow, item, context);
    }
    for (const item of group?.systemItems || []) {
      if (item?.kind === "compact") continue;
      pushLooseItem(pushRow, item, context);
    }

    const entries = turnActivityEntries(group, context);
    const assistantRows = assistantRowsForTurn(group);
    const shouldFold = isTurnFoldedByDefault(group, context);
    const foldEntries = shouldFold ? foldEntriesForTurn(group, context) : [];
    if (entries.length > 0 || foldEntries.length > 0) {
      if (shouldFold) {
        pushRow({
          id: `turn-fold-${group.turnId || rows.length}`,
          kind: ACTIVITY_ROW_KINDS.TURN_FOLD,
          turnId: stringValue(group.turnId),
          createdAt: turnStartTimestamp(group, entries),
          completedAt: turnEndTimestamp(group, entries),
          interrupted: hasInterruptedWork(entries),
          label: stringValue(group?.label),
          workCount: entries.filter((entry) => entry.kind === ACTIVITY_ROW_KINDS.WORK).length,
          reasoningCount: entries.filter((entry) => entry.kind === "reasoning").length,
          entryCount: foldEntries.length,
          defaultOpen: false,
          entries: foldEntries,
        });
      } else {
        for (const row of orderedOpenRowsForTurn(group, { ...context, openPlacement: true })) pushRow(row);
      }
    }

    const changedRow = diffSummaryRow(group, context);
    if (changedRow) pushRow(changedRow);

    if (entries.length === 0 || shouldFold) {
      const terminalAssistantItem = shouldFold ? terminalAssistantItemForTurn(group) : null;
      for (const row of assistantRows) {
        if (terminalAssistantItem && row.id !== stringValue(terminalAssistantItem.id)) continue;
        pushRow(row);
      }
    }

    for (const item of (group?.trailingTurnItems || []).concat(group?.detachedItems || [])) {
      if (item?.kind !== "tool" && item?.kind !== "interaction_requested" && item?.kind !== "interaction_resolved") {
        if (item?.kind === "compact") continue;
        pushLooseItem(pushRow, item, context);
      }
    }
    for (const item of group?.sessionFallbackItems || []) pushLooseItem(pushRow, item, context);
  }

  if (!currentInteraction && interactionNotice) {
    pushRow({
      id: `interaction-notice-${interactionNotice.interactionId || interactionNotice.kind || "notice"}`,
      kind: ACTIVITY_ROW_KINDS.SYSTEM_NOTICE,
      tone: interactionNotice.kind === "expired" ? "context" : "warning",
      content: interactionNotice.detail || interactionNotice.kind || "interaction",
      rawItem: interactionNotice,
    });
  }

  pushRow(turnExperienceSummaryRow(turnExperience));

  const hasActiveTurnRow = rows.some(
    (row) =>
      row.turnId === activeTurnId ||
      (row.kind === ACTIVITY_ROW_KINDS.TURN_FOLD &&
        Array.isArray(row.entries) &&
        row.entries.some((entry) => entry.turnId === activeTurnId)),
  );
  if (currentStatus === "running" && thinkingActive && (activeTurnId || hasActiveTurnRow)) {
    const activeCreatedAt = minTimestamp(
      rows
        .filter((row) => row.turnId === activeTurnId)
        .map((row) => row.createdAt),
    );
    pushRow(workingRow({ activeTurnId, idSuffix: rows.length, createdAt: activeCreatedAt }));
  }

  if (currentStatus === "running" && rows.length === 0) {
    pushRow({
      id: "working",
      kind: ACTIVITY_ROW_KINDS.WORKING,
      createdAt: "",
    });
  }

  return rows;
}
