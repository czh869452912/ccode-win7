function cleanString(value) {
  return String(value || "").trim();
}

function permissionRequestKind(interaction) {
  const category = cleanString(interaction?.category);
  const explicitKind = cleanString(interaction?.request_kind || interaction?.requestKind);
  if (["command", "file-read", "file-change"].includes(explicitKind)) {
    return explicitKind;
  }
  if (category === "read") {
    return "file-read";
  }
  if (category === "workspace_write" || category === "git_write") {
    return "file-change";
  }
  if (
    category === "command" ||
    category === "shell" ||
    category === "shell_exec" ||
    category === "toolchain_exec" ||
    category === "network" ||
    category === "telemetry"
  ) {
    return "command";
  }
  return "file-change";
}

function summaryForPermission(kind) {
  if (kind === "command") return "Command approval requested";
  if (kind === "file-read") return "File-read approval requested";
  return "File-change approval requested";
}

function detailRowsFor(details) {
  if (!details || typeof details !== "object" || Array.isArray(details)) {
    return [];
  }
  return Object.keys(details)
    .sort()
    .map((key) => ({
      label: key,
      value:
        typeof details[key] === "string"
          ? details[key]
          : JSON.stringify(details[key]),
    }))
    .filter((row) => cleanString(row.value));
}

function normalizeOptions(options) {
  return (Array.isArray(options) ? options : []).map((option, index) => {
    const selectedIndex = Number(option?.index || index + 1);
    const label = cleanString(option?.label || option?.text || option?.value);
    return {
      index: selectedIndex,
      label,
      text: label,
      value: cleanString(option?.value || label),
      description: cleanString(option?.description),
      mode: cleanString(option?.mode),
      shortcut: selectedIndex >= 1 && selectedIndex <= 9 ? String(selectedIndex) : "",
    };
  }).filter((option) => option.text);
}

export function interactionNoticeView(notice) {
  if (!notice) return null;
  const kind = cleanString(notice.kind);
  if (kind === "expired") {
    return {
      kind: "notice",
      tone: "expired",
      title: "Interaction expired",
      body: "This request is no longer active. Trigger the action again to continue.",
      detail: cleanString(notice.detail),
    };
  }
  if (kind === "conflict") {
    return {
      kind: "notice",
      tone: "conflict",
      title: "Interaction already handled",
      body: "This request changed in another flow. Refresh the current interaction and try again if needed.",
      detail: cleanString(notice.detail),
    };
  }
  return null;
}

export function normalizeComposerInteraction(interaction, notice = null) {
  const noticeView = interactionNoticeView(notice);
  if (noticeView) return noticeView;
  if (!interaction) return null;
  const kind = cleanString(interaction.kind);
  if (kind === "permission") {
    const requestKind = permissionRequestKind(interaction);
    return {
      kind: "permission",
      interactionId: cleanString(interaction.interaction_id || interaction.permission_id),
      requestKind,
      summary: summaryForPermission(requestKind),
      toolName: cleanString(interaction.tool_name || interaction.toolName),
      category: cleanString(interaction.category),
      reason: cleanString(interaction.reason),
      details: interaction.details || {},
      detailRows: detailRowsFor(interaction.details),
      primaryLabel: "Approve",
      secondaryLabel: "Deny",
      rememberLabel: "Remember for this session",
      rawInteraction: interaction,
    };
  }
  const rawQuestions = Array.isArray(interaction.questions) ? interaction.questions : [];
  const questions = rawQuestions.length
    ? rawQuestions.map((question, index) => ({
        id: cleanString(question?.id || (index === 0 ? "answer" : `answer_${index + 1}`)),
        question: cleanString(question?.question),
        options: normalizeOptions(question?.options),
        multi_select: Boolean(question?.multi_select || question?.multiSelect),
      })).filter((question) => question.question || question.options.length > 0)
    : [
        {
          id: "answer",
          question: cleanString(interaction.question),
          options: normalizeOptions(interaction.options),
          multi_select: false,
        },
      ];
  const firstQuestion = questions[0] || { question: "", options: [] };
  return {
    kind: "user_input",
    interactionId: cleanString(interaction.interaction_id || interaction.request_id),
    summary: "Input requested",
    toolName: cleanString(interaction.tool_name || interaction.toolName),
    questions,
    question: firstQuestion.question || "",
    options: firstQuestion.options || [],
    customPlaceholder: "Or type a custom answer...",
    submitLabel: "Submit",
    rawInteraction: interaction,
  };
}

function isResolvedInteractionActivity(item) {
  if (!item || item.kind !== "interaction" || !item.requestId) return false;
  const sourceKind = cleanString(item.sourceActivityKind || item.source_activity_kind);
  return (
    item.status === "resolved" ||
    item.status === "error" ||
    sourceKind === "approval.resolved" ||
    sourceKind === "approval.response.failed" ||
    sourceKind === "user-input.resolved" ||
    sourceKind === "user-input.response.failed"
  );
}

export function currentInteractionFromActivities(activities = []) {
  const records = Array.isArray(activities) ? activities : [];
  const closedRequestIds = new Set();
  for (const item of records) {
    if (isResolvedInteractionActivity(item)) {
      closedRequestIds.add(item.requestId);
    }
  }
  for (let index = records.length - 1; index >= 0; index -= 1) {
    const item = records[index];
    if (!item || item.kind !== "interaction" || item.status !== "pending") continue;
    if (!item.requestId || closedRequestIds.has(item.requestId)) continue;
    const sourceKind = cleanString(item.sourceActivityKind || item.source_activity_kind);
    const payload = item.payload && typeof item.payload === "object" ? item.payload : {};
    if (sourceKind === "approval.requested") {
      return normalizeComposerInteraction({
        interaction_id: item.requestId,
        kind: "permission",
        tool_name: payload.toolName || payload.tool_name,
        category: payload.permissionCategory || payload.permission_category,
        reason: payload.reason || payload.summary,
        details: payload.details || {},
        request_kind: payload.requestKind || payload.request_kind,
      });
    }
    if (sourceKind === "user-input.requested") {
      return normalizeComposerInteraction({
        interaction_id: item.requestId,
        kind: "user_input",
        tool_name: payload.toolName || payload.tool_name || "ask_user",
        questions: Array.isArray(payload.questions) ? payload.questions : [],
        question: payload.question || payload.summary,
        options: Array.isArray(payload.options) ? payload.options : [],
      });
    }
  }
  return null;
}

export function buildPermissionResponse(_interaction, decision) {
  return { decision };
}

export function buildUserInputResponse(interaction, options = {}) {
  const selected = options.option || null;
  const questions = Array.isArray(interaction?.questions) ? interaction.questions : [];
  const firstQuestion = questions[0] || {};
  const answerKey = cleanString(firstQuestion.id) || "answer";
  return {
    answers: {
      [answerKey]: selected
        ? selected.value || selected.label || selected.text || ""
        : cleanString(options.answer),
    },
  };
}
