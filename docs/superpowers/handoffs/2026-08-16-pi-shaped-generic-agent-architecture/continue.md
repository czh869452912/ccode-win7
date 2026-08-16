# Continue — Pi-Shaped Generic Agent Architecture Evaluation

## Last action

已完成当前架构审计，用户认可方案 A；已提交目标架构规格 `197dcb9d`，并新增 evaluation report。没有修改实现代码，也没有编写实施计划。

## Next action

冷读以下两份文档，记录需要保留、删除或改写的设计决策；评估通过后，再由用户明确授权生成 implementation plan：

- `docs/superpowers/reports/2026-08-16-pi-shaped-generic-agent-architecture-report.md`
- `docs/superpowers/specs/2026-08-16-pi-shaped-generic-agent-architecture-design.md`

## Why

当前目标是评估架构方向，不是开始迁移。report 解释现状和评估问题，spec 记录方案 A 的目标边界和验收条件。

## Open threads

- 是否接受 Core 移除 `default_mode/current_mode` 的强制执行路径；
- application-owned prompt 是否成为唯一 system prompt 来源；
- Ctags、LLVM、recipes、TaskGraph 是否全部只由 C++ application 注册；
- selected dependency closure 是否成为每个导出制品的 distribution 真相；
- application registration 使用何种显式 entry contract；
- `runtime_error` 安全诊断字段的最终 DTO 形状；
- 何时从当前 workspace 进一步拆分物理 repository。

## Do not

- 不要在评估完成前写 implementation plan；
- 不要把 `proposed` 规格当成已实施架构；
- 不要先修改 Core mode/session API 来验证想法；
- 不要用固定六 wheel 流程推断 generic application 的最终发布边界；
- 不要删除或回退提交 `197dcb9d`。

## Workspace note

当前项目没有 `.gsd` active slice、`STATE.md` 或可更新的 GSD summary；本文件作为项目内 handoff 入口，直到评估结束后再决定是否转入正式 slice。
