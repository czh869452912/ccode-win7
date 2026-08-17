# Pi-Shaped Generic Agent Architecture Report

> 状态：`evaluation-ready`
> 读者：项目维护者、架构评估者和后续接续会话
> 评估目标：决定是否按方案 A 进入实现设计，而不是开始实现

## 1. 结论摘要

当前项目已经完成了足够深入的基础拆分。Core 的会话执行、durable event、restore、Host/Core ports、extension boundary 和 frontend protocol 已经接近可独立建库的形态，不需要推倒重写。

`minimal-cli` 仍表现出 C++ 工作流特征，不是因为 Core 算法本身依赖 C++，而是因为应用选择、默认注册、系统提示词、Host runtime catalog 和制品导出仍共享产品级默认值。也就是说，当前是“选择层 generic、所有权层仍有耦合”。

方案 A 的判断是：沿用现有 session/replay/extension 主干，收紧四条边界即可达到 Pi 风格的通用 Agent：

- Core 不解释 mode、profile、workflow 或产品 system prompt；
- Host 只提供通用运行时和注入协议；
- Application 拥有 prompt、tools、context、modes 和 workflow；
- Product 根据 selected dependency closure 导出并启动应用。

本报告不授权实现，也不替代已提交的架构规格。它是后续评估入口。

## 2. 已经做好的部分

这些部分应作为稳定主干保留：

- `Agent` / `AgentSession` public SDK；
- `HostedSessionController` 作为 Core/Host 的受控边界；
- journal append-before-reduce 的单写入 session truth；
- 同一 reducer 负责 live state 和 restore；
- `AgentLoop` 的 prepare/commit/execute/resume 执行脊柱；
- focused context/tool/projection/permission ports；
- permission 与 writable-path 的独立决策；
- `AgentExtensionHost`、capability records 和 source-aware event bus；
- canonical session event envelope 和通用 shell descriptor；
- Composition compiler 已有的 component dependency closure 能力。

这些结构说明项目确实已经接近“各部分独立建库”，后续重点是收紧 ownership 和发布边界，而不是重写 session engine。

## 3. 仍然存在的耦合

### 3.1 导出耦合

正式 bundle plan 仍使用固定六个 project distributions。虽然 composition export 已经能计算 selected component closure，但 release-oriented bundle path 没有用这个闭包决定 wheel 集合。

结果是：minimal-cli 可以不选择 C++ workflow，却仍然构建和归档 C++ distribution。

### 3.2 Product 对 C++ 的默认耦合

产品 application registry 在导入阶段就知道 C++ application，根产品 distribution 也声明 C++ workflow dependency。这样 generic product 无法成为真正的独立基础 Agent。

结果是：物理未激活不等于依赖未存在，应用选择仍受产品导入图影响。

### 3.3 Mode 与 system prompt 耦合

Core 的 runtime/session input/projection 仍要求或传递 `default_mode`、`current_mode` 和 mode policy。产品层另外固定注入模式提示框架。

结果是：通用 Agent 启动时自然呈现 `explore`、只读、模式切换和五模式表，即使应用没有声明这些能力。

### 3.4 Host 工具与工作区耦合

Host 默认 workspace intelligence 包含 Ctags、recipe、diagnostics 等应用级 provider，managed runtime 也把 Ctags 和 LLVM 作为全局工具集合。

结果是：minimal-cli 的运行时探测和上下文装配仍然感知 C/C++，而不是由 selected application 显式提供。

### 3.5 诊断契约不足

CLI 对未知异常只输出稳定码 `runtime_error`。这不改变架构方向，但会阻碍评估者判断“交互恢复输入错误”和“真正运行时异常”的区别，需要独立补齐安全诊断字段。

## 4. 方案 A 的目标边界

```text
Generic CLI / TUI / GUI
            |
     Product bootstrap
            |
  Selected Agent Application
       /              \
Generic application   C/C++ application
       \              /
        Generic Host runtime
                |
          Agent Core SDK
```

Core 只处理通用 Agent session、turn loop、durable event 和 restore。Host 提供 provider、store、tool adapter、context 基础设施和 permission。Application 定义 prompt、tools、context provider、optional modes、workflow state 和 shell contributions。Product 选择并组合它们，不把 C++ 作为根依赖。

## 5. 评估时必须确认的设计决策

### A. Core 是否真正无模式

评估问题：是否接受移除 Core 对 `default_mode/current_mode` 的强制执行路径，让 mode 成为 application-owned capability？

接受该决策意味着：旧的五模式不再是平台公共语义；C++ application 仍可以保留五模式，但 generic application 可以完全没有 mode。

### B. system prompt 是否完全由调用方/application 提供

评估问题：是否接受 Core 不生成产品 prompt frame，generic application 默认不出现模式、只读或 C/C++ 文本？

这是与 Pi 对齐的关键点：应用可以 replacement/append prompt，Core 只消费 prompt/context units。

### C. C++ 能力是否只由 selected application 注册

评估问题：是否接受 Ctags、LLVM、recipes、TaskGraph 和 C++ diagnostics 全部移到 C++ application，并从 generic Host 默认集合移除？

这会改变 minimal 与 cpp-desktop 的 capability 物理边界，但不会削弱 cpp-desktop 的功能。

### D. 是否接受按制品依赖闭包选择 distribution

评估问题：是否接受构建流水线继续可以验证全部 workspace wheels，但单个制品只 staging、安装和 hash selected closure？

这是解决“minimal 不激活 C++ 但仍携带 C++ wheel”的必要条件。

### E. 物理拆库的时机

建议先冻结 source/package/application contracts，再拆物理 repository。当前设计目标是“能够独立建库”，不是本轮立即移动 Git repository。

## 6. 评估结论建议

推荐继续采用方案 A，理由如下：

1. 复用已有的稳定执行脊柱，迁移风险集中在边界而不是 session correctness。
2. 能直接解释当前 minimal-cli 的错误表现，并逐项给出归属变化。
3. 与 Pi 的 `agent` / `coding-agent` 分层对应：Core 通用，application 提供 prompt/tool/resource，shell 只负责交互。
4. 支持 C++ 继续作为默认产品能力，同时允许 generic、Python、HTML 或用户应用独立演化。
5. 可以先在当前仓库完成契约验证，再决定哪些 distribution 值得独立建库。

不建议只做“导出 six wheels 改成按闭包选择”的局部修复；那只能解决交付体积，不能解决模式和 prompt 仍由 Core/Host 默认注入的问题。

## 7. 当前明确不做的事

- 不写实施计划；
- 不修改 Core/Host/Product 实现；
- 不立即拆物理 repository；
- 不引入 remote marketplace、运行时依赖安装或通用多 Agent orchestration；
- 不为旧 mode/profile 内部形状增加兼容代理；
- 不把 capability registry、workflow state 或 snapshot 变成执行权威。

## 8. 关联文档

- 目标架构规格：`docs/superpowers/specs/2026-08-16-pi-shaped-generic-agent-architecture-design.md`
- 当前跨层架构：`docs/overall-solution-architecture.md`
- Pi 风格方向：`docs/platform/agent-platform-blueprint.md`
- 产品组合：`docs/product/composition.md`
- 当前状态：`docs/current-status.md`

后续评估完成后，应先修改或确认目标架构规格，再决定是否生成 implementation plan。
