# ADR-0006: Separate Agent Platform, Applications, And Product

- Status: accepted
- Date: 2026-08-01
- Owners: project maintainers

## Context

仓库同时包含可复用 Agent 底座、C/C++ 工作流和 EmbedAgent 产品交付。旧文档按历史模块与改造批次组织，使同一执行链、会话真相和工作流语义同时出现在多个活跃权威中。GUI/TUI 也容易被误解为默认工作流的专用壳，而不是注册协议上的通用交互层。

长期方向是使 Agent Platform 可从仓库迁出，成为独立的 Windows 7/Python 3.8/offline-compatible 底座；C/C++ 继续是一等上层应用，EmbedAgent 继续是一种产品组合。

## Decision

1. `docs/platform/` 拥有工作流无关的 Agent Core、持久会话、Host 能力、工具/扩展、权限/上下文、Host/UI 协议、mode contract 和可注册 GUI/TUI shell。
2. `docs/applications/` 拥有上层工作流。C/C++ 应用拥有其 profile、phase、任务图、packs、recipes、quality evidence 和 workflow projection。
3. `docs/product/` 拥有 EmbedAgent product catalog、默认注册、shell 选择、配置与 Windows 7 离线交付。

`docs/overall-solution-architecture.md` 只拥有跨领域拓扑和不变式，`docs/README.md` 只路由到单一权威。活跃文档不保留旧路径兼容页，也不以完成的批次或版本后缀命名稳定权威。

GUI/TUI 契约和 shell 行为是平台级通用能力；当前实现可继续随 `embedagent` 产品发行。product copy、default application、launcher 选择、bundled browser runtime 和离线资产属于产品层。

## Alternatives Considered

### Keep One Module-Oriented Tree

拒绝。仅按源码目录组织权威无法表达平台、应用与产品的依赖方向，也不能阻止通用文档重新吸收应用语义。

### Keep Generic And Product-Specific Copies

拒绝。这会继续产生两套会话、工具和前端真相，使一个变更必须同步多个活跃权威。

### Move All UI Documentation Into Product

拒绝。GUI/TUI 的协议、事件、capability-driven rendering 和注册边界可在不同产品中复用。只有默认组合、文案、launcher 和交付资产是产品特有的。

## Consequences

- 文档地图和代码-文档矩阵可机械检查每个领域的唯一地址。
- 平台权威必须保持 application-neutral，应用不能反向改变 Core/Host/UI 契约。
- 新上层应用应新增自己的 application authority，通过 registry/extension/capability 边界接入。
- Agent Platform 迁出可以公开发行包和注册契约为分界，不需带走 EmbedAgent product catalog 或默认工作流。
- 文档所有权和 distribution placement 不必完全相同；shell 实现当前仍可发行在产品包中。

## Enforcement

- `tests/test_documentation_navigation.py` 检查领域路径、退役路由、生命周期文件名和平台文档的应用语义泄漏。
- `tests/test_pre_release_architecture_guards.py` 和 `tests/test_current_architecture_boundaries.py` 检查发行包与执行边界。
- 所有权变更必须同步 `docs/references/code-doc-matrix.md`。
