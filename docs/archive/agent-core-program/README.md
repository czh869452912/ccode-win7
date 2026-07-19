# Agent Core Program Archive

> 状态：`archive`
> 归档日期：`2026-07-19`
> 当前真相：`README.md`、`AGENTS.md`、`docs/overall-solution-architecture.md`、`docs/implementation-roadmap.md`

本包保存 2026-07-02 至 2026-07-11 期间关于 Agent Core 独立化、C/C++ workflow package、GUI 协议/壳层解耦、确定性 composition/export 和 Python distribution split 的设计与实施计划。

这些切片已经完成并回写到当前架构文档。文档中的早期目录和迁移步骤只描述历史状态，不能作为当前代码入口；当前 C/C++ workflow package 位于 `packages/embedagent-workflow-cpp/`。

## Archived Materials

- Agent Core / T3 GUI design and implementation plan
- Core boundary and workflow package contract extraction
- Independent Agent / adaptive GUI design and roadmap
- Core public API and neutral runtime
- C/C++ workflow distribution
- Deterministic Agent composition
- Legacy removal and release validation
- Python distribution split

后续架构变化必须先更新活动 source-of-truth 文档，再新增或修改当前切片材料。