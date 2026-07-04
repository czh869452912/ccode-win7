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

    // Right panel surfaces
    "inspector.plan": "Plan",
    "inspector.diff": "Diff",
    "inspector.settings": "Settings",
    "inspector.diagnostics": "Diagnostics",
    "inspector.confirmWorkspaceSwitch": "Confirm workspace switch",
    "inspector.showDiagnosticsBadge": "Show diagnostics badge",
    "inspector.capabilities": "Capabilities",
    "inspector.diagnostics.host": "Host",
    "inspector.diagnostics.runtime": "Runtime",
    "inspector.diagnostics.renderer": "Renderer",
    "inspector.diagnostics.workspace_registry": "Workspace Registry",
    "inspector.diagnostics.active_core": "Active Core",

    // Panel empty states
    "inspector.noInteraction": "No pending interaction.",
    "inspector.noPlan": "No active plan in this session.",
    "inspector.noDiagnostics": "No app diagnostics loaded.",

    // User input panel
    "inspector.inputRequired": "Input Required",
    "inspector.customAnswer": "Or type a custom answer…",
    "inspector.submit": "Submit",
    "interaction.expiredTitle": "Interaction expired",
    "interaction.expiredBody": "This request is no longer active. Trigger the action again to continue.",
    "interaction.conflictTitle": "Interaction already handled",
    "interaction.conflictBody": "This request changed in another flow. Refresh the current interaction and try again if needed.",

    // Composer
    "composer.placeholder": "Message… Enter to send, Shift+Enter for newline",
    "composer.send": "Send",
    "composer.stop": "Stop",
    "composer.hint.command": "/ commands",
    "composer.hint.file": "@ files",
    "composer.hint.select": "↑↓ select",
    "composer.hint.newline": "Shift+Enter newline",
    "composer.hint.running": "running turns disable editing",
    "composer.hint.interaction": "interaction pending",

    // Header
    "header.refresh": "Refresh",
    "header.toggleInspector": "Toggle inspector panel",

    // Timeline
    "timeline.thinking": "Thinking…",
    "timeline.thinkingLabel": "Thinking",
    "timeline.thinkingWords": "{n} words",
    "timeline.stepLabel": "Step {n}",
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
    "timeline.taskCount": "{n} tasks",
    "timeline.residualRisks": "Residual Risks",
    "timeline.compacted": "Context compacted",
    "timeline.compactSummarized": "summarized",
    "timeline.compactRetained": "retained",
    "timeline.toolInterrupted": "Cancelled",
    "timeline.toolDiscarded": "Skipped (retry boundary)",
    "timeline.maxTurnsReached": "Reached {max}-turn limit ({used} used). Continue by sending a new message.",
    "timeline.guardStop": "Repeated failures detected. Agent stopped. Describe the issue or adjust direction to continue.",
    "timeline.cancelled": "Cancelled.",
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

    "inspector.plan": "计划",
    "inspector.diff": "差异",

    "inspector.noInteraction": "当前没有待处理交互。",
    "inspector.noPlan": "当前会话暂无计划。",

    "inspector.inputRequired": "需要输入",
    "inspector.customAnswer": "或输入自定义回答…",
    "inspector.submit": "提交",
    "interaction.expiredTitle": "交互已过期",
    "interaction.expiredBody": "该请求已经失效，如仍需继续，请重新触发对应操作。",
    "interaction.conflictTitle": "交互已被处理",
    "interaction.conflictBody": "该请求已在其他流程中发生变化，请刷新当前交互后再决定下一步。",

    "composer.placeholder": "输入消息，Enter 发送，Shift+Enter 换行",
    "composer.send": "发送",
    "composer.stop": "停止",
    "composer.hint.command": "/ 命令",
    "composer.hint.file": "@ 文件",
    "composer.hint.select": "↑↓ 选择",
    "composer.hint.newline": "Shift+Enter 换行",
    "composer.hint.running": "running 时禁用",
    "composer.hint.interaction": "interaction pending",

    "header.refresh": "刷新",
    "header.toggleInspector": "切换检查面板",

    "timeline.thinking": "思考中…",
    "timeline.thinkingLabel": "思考",
    "timeline.thinkingWords": "{n} 词",
    "timeline.stepLabel": "步骤 {n}",
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
    "timeline.taskCount": "{n} 个任务",
    "timeline.residualRisks": "残余风险",
    "timeline.compacted": "上下文已压缩",
    "timeline.compactSummarized": "摘要",
    "timeline.compactRetained": "保留",
    "timeline.toolInterrupted": "已取消",
    "timeline.toolDiscarded": "已跳过（重试边界）",
    "timeline.maxTurnsReached": "已达到 {max} 轮上限（已用 {used} 轮）。如需继续，请继续输入。",
    "timeline.guardStop": "连续操作失败，Agent 已停止。请描述问题或调整方向后重新提交。",
    "timeline.cancelled": "已取消。",
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
