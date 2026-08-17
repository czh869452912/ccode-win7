# Continue — Pi-Shaped Generic Agent Architecture Evaluation

## Last action

已完成当前架构审计，用户已认可结合 Pi 与 DeepSeek Harness 的方案 A 收敛版；目标架构规格已转为 `accepted`，并新增 ADR-0008。没有修改实现代码，下一步生成实施计划。

## Next action

按已接受规格执行 implementation plan，随后进入 TDD 实施：

- `docs/superpowers/plans/2026-08-17-generic-agent-application-plugin-closure-export.md`
- `docs/superpowers/specs/2026-08-16-pi-shaped-generic-agent-architecture-design.md`

## Why

当前目标已从评估转为迁移准备。spec 和 ADR 记录目标边界、插件契约、通用 shell 和 closure export；实现仍需按 plan 分阶段完成。

## Resolved decisions

- Core 移除 `default_mode/current_mode` 的强制执行路径；
- application-owned prompt 成为唯一产品 prompt 来源；
- Ctags、LLVM、recipes、TaskGraph 只由 C++ application 注册；
- selected dependency closure 成为每个导出制品的 distribution 真相；
- application plugin 使用 manifest + 显式 registration entry + source-aware disposer；
- runtime error 诊断在迁移阶段补齐安全 DTO；
- 物理 repository 拆分延后到公共契约冻结之后。

## Do not

- 不要在 plan 执行前修改实现代码；
- 不要把 `accepted` 规格当成已实施架构；
- 不要先修改 Core mode/session API 来验证想法；
- 不要用固定六 wheel 流程推断 generic application 的最终发布边界；
- 不要删除或回退提交 `197dcb9d`。

## Workspace note

当前项目没有 `.gsd` active slice、`STATE.md` 或可更新的 GSD summary；本文件作为项目内 handoff 入口，直到 implementation plan 完成并迁移验收后归档。
