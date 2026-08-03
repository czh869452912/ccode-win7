# Standalone Agent Platform Extraction Readiness Archive

> 状态：`archive`
> 类型：`completed slice`
> 负责人：`Agent platform maintainers`
> 关闭日期：`2026-08-03`

本包保存 standalone Agent Platform 独立提取准备的实施计划。当前行为只以 `docs/platform/agent-core.md`、`docs/platform/tools-and-extensions.md` 和发行包验证脚本为准。

## Contents

- `2026-08-03-standalone-agent-platform-extraction-readiness.md`

## Closure Boundary

- `embedagent_core` 根包公开独立构造和驱动 `Agent` / `AgentSession` 所需的既有 contracts、safe defaults 和 errors。
- `examples/standalone_agent.py` 只使用 Core 根包，以显式 ports 完成运行、挂起和同一 durable session 恢复。
- `core_only` wheel smoke 直接执行该示例，并确认 Host、Protocol、Composition、C/C++ workflow 和 product 分发不可发现。
- 本切片没有执行物理迁仓；独立仓库、版本发布和产品消费迁移仍需单独设计。
