export function makeEventId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function createTreeNode(entry) {
  return {
    id: entry.path,
    path: entry.path,
    name: entry.name,
    kind: entry.kind,
    children: [],
    childrenLoaded: false,
    hasChildren: Boolean(entry.has_children),
  };
}

export function injectChildren(nodes, targetPath, children) {
  return nodes.map((node) => {
    if (node.path === targetPath) {
      return {
        ...node,
        childrenLoaded: true,
        children: children.map(createTreeNode),
      };
    }
    if (!node.children || !node.children.length) {
      return node;
    }
    return {
      ...node,
      children: injectChildren(node.children, targetPath, children),
    };
  });
}

export function timelineFromEvents(events) {
  const items = [];
  const toolIndex = {};
  for (const record of events || []) {
    const eventName = record.event;
    const payload = record.payload || {};
    if (eventName === "turn_started" && payload.text) {
      items.push({ id: record.event_id, kind: "user", content: payload.text });
    } else if (eventName === "reasoning_delta" && payload.text) {
      items.push({ id: record.event_id, kind: "reasoning", content: payload.text, open: true });
    } else if (eventName === "tool_started") {
      const item = {
        id: payload.call_id || record.event_id,
        kind: "tool",
        toolName: payload.tool_name,
        arguments: payload.arguments,
        status: "running",
      };
      toolIndex[item.id] = items.length;
      items.push(item);
    } else if (eventName === "tool_finished") {
      const callId = payload.call_id || record.event_id;
      const index = toolIndex[callId];
      const toolItem = {
        id: callId,
        kind: "tool",
        toolName: payload.tool_name,
        arguments: {},
        status: payload.success ? "success" : "error",
        data: payload.data,
        error: payload.error,
      };
      if (index === undefined) {
        items.push(toolItem);
      } else {
        items[index] = { ...items[index], ...toolItem };
      }
    } else if (eventName === "context_compacted") {
      items.push({
        id: record.event_id,
        kind: "system",
        tone: "context",
        content: `上下文已压缩：保留 ${payload.recent_turns || 0} 轮，摘要 ${payload.summarized_turns || 0} 轮`,
      });
    } else if (eventName === "session_error") {
      items.push({
        id: record.event_id,
        kind: "system",
        tone: "error",
        content: payload.error || "会话出错",
      });
    } else if (eventName === "session_finished" && payload.final_text) {
      items.push({
        id: record.event_id,
        kind: "assistant",
        content: payload.final_text,
      });
    }
  }
  return items;
}

export function normalizeSessionPayload(payload) {
  return {
    session_id: payload.session_id || "",
    status: payload.status || "idle",
    current_mode: payload.current_mode || "code",
    started_at: payload.started_at || payload.created_at || "",
    updated_at: payload.updated_at || "",
    has_pending_permission: Boolean(payload.has_pending_permission),
    has_pending_input: Boolean(payload.has_pending_input),
    pending_permission: payload.pending_permission || null,
    pending_user_input: payload.pending_user_input || null,
    last_error: payload.last_error || "",
  };
}
