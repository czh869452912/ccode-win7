export function createThreadLifecycleController({
  fetchJson,
  dispatch,
  loadSessions,
  loadSession,
  getThreadSessions,
  prompt,
  confirm,
}) {
  async function renameThread(sessionId) {
    const current = getThreadSessions().find((item) => item.session_id === sessionId) || {};
    const initialTitle = current.thread?.title || current.title || current.user_goal || "";
    const title = prompt("Rename thread", initialTitle);
    if (title === null) return;
    const normalizedTitle = String(title || "").trim();
    if (!normalizedTitle) {
      dispatch({
        type: "interaction_notice_set",
        notice: {
          kind: "thread_lifecycle",
          title: "Rename failed",
          body: "Thread title cannot be empty.",
        },
      });
      return;
    }
    await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/rename`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: normalizedTitle }),
    });
    await loadSessions();
  }

  async function archiveThread(sessionId) {
    if (!confirm("Archive this thread?")) return;
    await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/archive`, {
      method: "POST",
    });
    await loadSessions();
    dispatch({
      type: "interaction_notice_set",
      notice: {
        kind: "thread_lifecycle",
        title: "Thread archived",
        body: "The thread was archived and hidden from the normal thread list.",
      },
    });
  }

  async function forkThread(sessionId) {
    const title = prompt("Fork thread title", "");
    if (title === null) return;
    const payload = await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/fork`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: String(title || "").trim() }),
    });
    await loadSessions();
    if (payload.session_id) {
      await loadSession(payload.session_id);
    }
  }

  async function handleThreadLifecycleAction(actionId, sessionId) {
    try {
      if (actionId === "rename") return await renameThread(sessionId);
      if (actionId === "archive") return await archiveThread(sessionId);
      if (actionId === "fork") return await forkThread(sessionId);
    } catch (error) {
      dispatch({
        type: "interaction_notice_set",
        notice: {
          kind: "thread_lifecycle",
          title: "Thread action failed",
          body: error?.message || String(error || "thread_lifecycle_failed"),
        },
      });
    }
  }

  return { renameThread, archiveThread, forkThread, handleThreadLifecycleAction };
}
