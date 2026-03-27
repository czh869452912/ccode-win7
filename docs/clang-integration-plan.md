# EmbedAgent Clang 工具链集成计划

> 更新日期：2026-03-28
> 适用阶段：Phase 4

---

## 1. 文档目标

记录当前 Phase 4 的实现策略、已落地能力和后续真实 Clang 工具链接入方向。

本文件聚焦“如何把工具先做成可用接口”，而不是最终离线打包细节。

---

## 2. 当前现实约束

当前仓库还没有：

- 真实的 C 项目源码
- 已固定的构建系统入口
- 已落盘的 Clang 二进制目录
- 可直接运行的 `clang` / `ctest` / `llvm-cov` 默认命令

因此当前 Phase 4 采用：

- 工具先行
- 命令显式传入
- 输出结构化解析

也就是：

- `compile_project`、`run_tests`、`run_clang_tidy`、`run_clang_analyzer`、`collect_coverage`
  当前都接受显式 `command`
- Tool Runtime 负责执行、超时终止和结构化解析
- 真实默认命令与 bundle 路径放到后续阶段补齐

---

## 3. 当前已落地能力

### 3.1 工具

已在 `src/embedagent/tools.py` 中落地：

- `compile_project`
- `run_tests`
- `run_clang_tidy`
- `run_clang_analyzer`
- `collect_coverage`
- `report_quality`

### 3.2 诊断解析

当前已支持两类常见编译器/检查器输出：

1. Clang/GCC 风格

```text
src/main.c:12:3: error: missing semicolon
```

2. MSVC 风格

```text
src\\main.c(12,3): error C2143: syntax error
```

解析结果统一为：

- `file`
- `line`
- `column`
- `level`
- `message`

### 3.3 测试统计

`run_tests` 当前会从输出中提取：

- `passed`
- `failed`
- `skipped`
- `total`

### 3.4 覆盖率统计

`collect_coverage` 当前会从输出中提取：

- `line_coverage`
- `function_coverage`
- `branch_coverage`
- `region_coverage`

### 3.5 质量门

`report_quality` 当前根据以下输入给出结论：

- `error_count`
- `test_failures`
- `warning_count`
- `line_coverage`
- `min_line_coverage`

---

## 4. 当前模式接入

Phase 4 已同步调整模式工具集：

- `code`：使用 `compile_project` 做最小编译验证
- `test`：使用 `run_tests`
- `verify`：使用 `compile_project`、`run_tests`、`run_clang_tidy`、`report_quality`

这样做的目的不是一次暴露全部工具，而是先让模式边界更稳定。

---

## 5. 后续接入顺序

建议按以下顺序继续推进：

1. 固化项目级默认命令来源
   - 例如 `config/build.toml` 或项目记忆
2. 接入真实 Clang 工具链路径
   - `clang`
   - `clang-tidy`
   - `clang --analyze`
   - `llvm-profdata`
   - `llvm-cov`
3. 在真实 C 示例项目上验证
   - 编译失败诊断
   - 测试结果汇总
   - 覆盖率提取
4. 在 Phase 7 中纳入离线 bundle

---

## 6. 当前结论

Phase 4 当前已经完成“接口层和解析层”的第一版实现。

这意味着：

- 即使真实 C 工程尚未接入，Core 侧的工具协议已经成立
- 后续只需要补项目默认命令和工具链目录，不必重写 Tool Runtime
