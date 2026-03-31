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
    "inspector.plan": "Plan",
    "inspector.review": "Review",
    "inspector.permissions": "Permissions",
    "inspector.preview": "Preview",
    "inspector.log": "Log",

    // Panel empty states
    "inspector.noTodos": "No todos in this session.",
    "inspector.noArtifacts": "No artifacts yet.",
    "inspector.noPlan": "No active plan in this session.",
    "inspector.noReview": "No review results yet.",
    "inspector.noReviewFindings": "No structured findings.",
    "inspector.noPermissions": "No permission context loaded.",
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
    "timeline.runningToolchain": "Toolchain step is running…",
    "timeline.runningCommand": "Command is running…",
    "timeline.runningGit": "Git operation is running…",
    "timeline.toolchainTests": "{n} failing tests",
    "timeline.toolchainDiagnostics": "{n} diagnostics",
    "timeline.commandExitCode": "Exit code {n}",
    "timeline.gitFilesChanged": "{n} files changed",
    "timeline.gitEntries": "{n} git entries",
    "timeline.qualityPassed": "Quality gate passed",
    "timeline.qualityFailed": "{n} quality gate reasons",
    "timeline.todoCount": "{n} todos",
    "timeline.residualRisks": "Residual Risks",

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
    "modal.remember": "Remember for this session",
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
    "inspector.plan": "计划",
    "inspector.review": "审查",
    "inspector.permissions": "权限",
    "inspector.preview": "预览",
    "inspector.log": "日志",

    "inspector.noTodos": "本次会话暂无待办。",
    "inspector.noArtifacts": "暂无产物。",
    "inspector.noPlan": "当前会话暂无计划。",
    "inspector.noReview": "当前还没有审查结果。",
    "inspector.noReviewFindings": "当前没有结构化问题。",
    "inspector.noPermissions": "当前没有权限上下文。",
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
    "timeline.runningToolchain": "工具链步骤执行中…",
    "timeline.runningCommand": "命令执行中…",
    "timeline.runningGit": "Git 操作执行中…",
    "timeline.toolchainTests": "{n} 个失败测试",
    "timeline.toolchainDiagnostics": "{n} 条诊断",
    "timeline.commandExitCode": "退出码 {n}",
    "timeline.gitFilesChanged": "{n} 个变更文件",
    "timeline.gitEntries": "{n} 条 Git 记录",
    "timeline.qualityPassed": "质量门已通过",
    "timeline.qualityFailed": "{n} 条质量门原因",
    "timeline.todoCount": "{n} 个待办",
    "timeline.residualRisks": "残余风险",

    "todos.title": "会话待办",
    "todos.done": "完成",
    "todos.todo": "待办",

    "artifacts.title": "产物",

    "modal.permissionRequired": "需要确认",
    "modal.tool": "工具",
    "modal.showDetails": "展开详情",
    "modal.remember": "本会话记住此类操作",
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
