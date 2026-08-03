function optionalProtocolMethod(protocol, name) {
  const method = protocol && protocol[name];
  return typeof method === "function" ? method.bind(protocol) : null;
}

export function createThreadLifecycleController({
  protocol,
  dispatch,
  loadSessions,
  loadSession,
  getThreadSessions,
  getThreadLifecycleCapabilities,
  prompt,
  confirm,
}) {
  const renameSession = optionalProtocolMethod(protocol, "renameSession");
  const archiveSession = optionalProtocolMethod(protocol, "archiveSession");
  const forkSession = optionalProtocolMethod(protocol, "forkSession");

  function currentActions() {
    const capabilities = getThreadLifecycleCapabilities ? getThreadLifecycleCapabilities() : {};
    return Array.isArray(capabilities?.actions) ? capabilities.actions : [];
  }

  function actionDescriptor(actionId) {
    const id = String(actionId || "").trim();
    const action = currentActions().find((item) => item?.id === id) || null;
    return action || { id, capability: id };
  }

  function actionText(action, key, fallback = "") {
    return String(action?.[key] || fallback || "").trim();
  }

  function dispatchLifecycleNotice(title, body) {
    const noticeTitle = String(title || "").trim();
    const noticeBody = String(body || "").trim();
    if (!noticeTitle && !noticeBody) return;
    dispatch({
      type: "interaction_notice_set",
      notice: { kind: "thread_lifecycle", title: noticeTitle, body: noticeBody },
    });
  }

  async function renameThread(sessionId, action = actionDescriptor("rename")) {
    if (!renameSession) return;
    const current = getThreadSessions().find((item) => item.session_id === sessionId) || {};
    const initialTitle = current.thread?.title || current.title || current.user_goal || "";
    const title = prompt(actionText(action, "promptTitle", action.label), initialTitle);
    if (title === null) return;
    const normalizedTitle = String(title || "").trim();
    if (!normalizedTitle) {
      dispatchLifecycleNotice(actionText(action, "emptyTitle"), actionText(action, "emptyBody"));
      return;
    }
    await renameSession(sessionId, normalizedTitle);
    await loadSessions();
  }

  async function archiveThread(sessionId, action = actionDescriptor("archive")) {
    if (!archiveSession) return;
    const confirmTitle = actionText(action, "confirmTitle", action.label);
    if (confirmTitle && !confirm(confirmTitle)) return;
    await archiveSession(sessionId);
    await loadSessions();
    dispatchLifecycleNotice(actionText(action, "successTitle"), actionText(action, "successBody"));
  }

  async function forkThread(sessionId, action = actionDescriptor("fork")) {
    if (!forkSession) return;
    const title = prompt(
      actionText(action, "promptTitle", action.label),
      actionText(action, "promptInitial"),
    );
    if (title === null) return;
    const payload = await forkSession(sessionId, String(title || "").trim());
    await loadSessions();
    if (payload.session_id) await loadSession(payload.session_id);
  }

  async function handleThreadLifecycleAction(actionId, sessionId) {
    const action = actionDescriptor(actionId);
    const capability = actionText(action, "capability", action.id);
    try {
      if (capability === "rename") return await renameThread(sessionId, action);
      if (capability === "archive") return await archiveThread(sessionId, action);
      if (capability === "fork") return await forkThread(sessionId, action);
    } catch (error) {
      dispatchLifecycleNotice(
        actionText(action, "failureTitle"),
        error?.message || String(error || "thread_lifecycle_failed"),
      );
    }
  }

  return { renameThread, archiveThread, forkThread, handleThreadLifecycleAction };
}
