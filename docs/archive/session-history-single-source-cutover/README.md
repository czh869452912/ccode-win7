# Session History Single-Source Cutover Archive

这组文档记录了 `2026-04-07 session history single-source cutover` 这一轮问题分析、审查、handoff 与实施计划。

归档时间：`2026-04-07`

最近补充归档：`2026-06-27`

归档原因：

- session-history cutover 已完成并合并到 `main`
- GUI session activation、transcript-backed history、bootstrap contract 与 raw fallback 清理都已收口
- TUI activities history cutover 已完成，TUI 现在消费同一条 `history.activities` 读模型
- 当前不再需要把这组 issue/plan 文档保留在活动 `docs/issues/` / `docs/superpowers/` 入口

归档内容：

- [gui_session_switch_raw_fallback.md](/D:/Claude-project/ccode-win7/docs/archive/session-history-single-source-cutover/gui_session_switch_raw_fallback.md)
- [gui_session_switch_raw_fallback_plan_review.md](/D:/Claude-project/ccode-win7/docs/archive/session-history-single-source-cutover/gui_session_switch_raw_fallback_plan_review.md)
- [gui_session_switch_raw_fallback_handoff.md](/D:/Claude-project/ccode-win7/docs/archive/session-history-single-source-cutover/gui_session_switch_raw_fallback_handoff.md)
- [2026-04-07-session-history-single-source-cutover.md](/D:/Claude-project/ccode-win7/docs/archive/session-history-single-source-cutover/2026-04-07-session-history-single-source-cutover.md)
- [2026-04-07-session-history-single-source-cutover-implementation.md](/D:/Claude-project/ccode-win7/docs/archive/session-history-single-source-cutover/2026-04-07-session-history-single-source-cutover-implementation.md)
- [2026-06-26-tui-activities-history-cutover.md](/D:/Claude-project/ccode-win7/docs/archive/session-history-single-source-cutover/2026-06-26-tui-activities-history-cutover.md)

当前活跃状态请看：

- [README.md](/D:/Claude-project/ccode-win7/README.md)
- [frontend-protocol.md](/D:/Claude-project/ccode-win7/docs/frontend-protocol.md)
- [frontend-tui.md](/D:/Claude-project/ccode-win7/docs/modules/frontend-tui.md)
- [design-change-log.md](/D:/Claude-project/ccode-win7/docs/design-change-log.md)
