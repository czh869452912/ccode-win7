/**
 * All user-visible strings, keyed by ID.
 * Add a new language by adding a matching key block.
 */
const STRINGS = {
  en: {
    // Brand
    "brand.sub": "Codex-grade local shell",

    // Sidebar
    "sidebar.chats": "Chats",
    "sidebar.files": "Files",
    "sidebar.newSession": "New Session",

    // Inspector tabs
    "inspector.todos": "Todos",
    "inspector.artifacts": "Artifacts",
    "inspector.preview": "Preview",
    "inspector.log": "Log",

    // Panel empty states
    "inspector.noTodos": "No todos in this session.",
    "inspector.noArtifacts": "No artifacts yet.",
    "inspector.noPreview": "Select a file or artifact to preview.",
    "inspector.noLog": "No events yet.",

    // User input panel
    "inspector.inputRequired": "Input Required",
    "inspector.customAnswer": "Or type a custom answer…",
    "inspector.submit": "Submit",

    // Composer
    "composer.placeholder": "Message… Enter to send, Shift+Enter for newline",
    "composer.send": "Send",
    "composer.stop": "Stop",

    // Header
    "header.refresh": "Refresh",
    "header.toggleInspector": "Toggle inspector panel",

    // Timeline
    "timeline.thinking": "Thinking…",
    "timeline.thinkingLabel": "Thinking",
    "timeline.thinkingWords": "{n} words",
    "timeline.toolDetails": "Details",
    "timeline.diffChanges": "File changes",

    // Todos
    "todos.title": "Session Todos",
    "todos.done": "done",
    "todos.todo": "todo",

    // Artifacts
    "artifacts.title": "Artifacts",

    // Permission modal
    "modal.permissionRequired": "Permission Required",
    "modal.tool": "Tool",
    "modal.showDetails": "Show details",
    "modal.deny": "Deny",
    "modal.approve": "Approve",

    // Language toggle (shows what you switch TO)
    "lang.toggle": "中文",
  },

  zh: {
    "brand.sub": "本地离线编码助手",

    "sidebar.chats": "对话",
    "sidebar.files": "文件",
    "sidebar.newSession": "新建会话",

    "inspector.todos": "待办",
    "inspector.artifacts": "产物",
    "inspector.preview": "预览",
    "inspector.log": "日志",

    "inspector.noTodos": "本次会话暂无待办。",
    "inspector.noArtifacts": "暂无产物。",
    "inspector.noPreview": "选择文件或产物以预览。",
    "inspector.noLog": "暂无事件。",

    "inspector.inputRequired": "需要输入",
    "inspector.customAnswer": "或输入自定义回答…",
    "inspector.submit": "提交",

    "composer.placeholder": "输入消息，Enter 发送，Shift+Enter 换行",
    "composer.send": "发送",
    "composer.stop": "停止",

    "header.refresh": "刷新",
    "header.toggleInspector": "切换检查面板",

    "timeline.thinking": "思考中…",
    "timeline.thinkingLabel": "思考",
    "timeline.thinkingWords": "{n} 词",
    "timeline.toolDetails": "详情",
    "timeline.diffChanges": "文件变更",

    "todos.title": "会话待办",
    "todos.done": "完成",
    "todos.todo": "待办",

    "artifacts.title": "产物",

    "modal.permissionRequired": "需要确认",
    "modal.tool": "工具",
    "modal.showDetails": "展开详情",
    "modal.deny": "拒绝",
    "modal.approve": "批准",

    "lang.toggle": "English",
  },
};

/**
 * Translate a key to the given language, with optional {param} substitution.
 * Falls back to "en" then to the key itself.
 */
export function t(key, lang = "en", params = {}) {
  let str = STRINGS[lang]?.[key] ?? STRINGS["en"]?.[key] ?? key;
  for (const [k, v] of Object.entries(params)) {
    str = str.replace(`{${k}}`, String(v));
  }
  return str;
}

export const SUPPORTED_LANGS = ["en", "zh"];
