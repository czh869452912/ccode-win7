# AI 智能体平台上下文管理深度调研报告

> 调研日期：2026-03-27
> 覆盖平台：Claude Code、Cursor、Windsurf、Cline、Aider、OpenHands、SWE-agent 及相关学术框架
> 报告用途：为轻量化 Agentic Coding 平台设计提供参考

---

## 一、全局概览：上下文工程的演化

2025 年，**上下文工程（Context Engineering）** 从小众技术话题升级为 AI 代理系统的核心基础设施问题。其驱动力是三重矛盾：

| 矛盾 | 描述 |
|------|------|
| **窗口 vs 代价** | 1M token 窗口技术上可用，但 Transformer 注意力机制的 O(n²) 计算复杂度使其经济成本呈二次方增长 |
| **信息 vs 质量** | 窗口越大，"上下文腐烂（Context Rot）"越严重——模型在超长上下文中注意力分散、遵循指令的能力下降 |
| **持久 vs 隔离** | 跨会话记忆需要持久化，但多任务/多智能体需要上下文隔离，两者形成根本张力 |

Anthropic 工程师将这一领域的核心定义为：**在推理时，精心策划并维护送入 LLM 的最优 token 集合（curating and maintaining the optimal set of tokens during LLM inference）**。

---

## 二、上下文窗口管理策略

### 2.1 主流压缩/摘要技术对比

#### 2.1.1 滑动窗口截断（FIFO Truncation）

最简单的方案：超出限制时丢弃最旧的消息。

- **优点**：实现零成本，无需额外 LLM 调用
- **缺点**：关键早期指令（如系统规则）可能丢失；无法感知语义重要性
- **适用场景**：低成本场景、对话轮次较短的场景

#### 2.1.2 LLM 摘要压缩

使用独立的 LLM 调用将旧交互压缩成摘要，近期内容保持完整。

**OpenHands 实现（Context Condensation，2025年11月发布）**：
- 触发条件：会话长度超过阈值
- 摘要目标：用户目标、代理进展、剩余任务、关键技术细节（相关文件、失败的测试）
- 利用 prompt caching 在特定断点触发，最大化缓存复用收益
- 效果：每轮 API 成本降低 **50%**，问题解决率从 53% 提升至 **54%**（基本无损）
- 扩展性：从二次方扩展改善为线性扩展

**Anthropic Compaction API（2026年初 beta）**：
- 在会话接近限制时，服务端自动生成历史摘要替换原始记录
- 通过 `/compact` 命令手动触发，支持聚焦方向（如 `/compact focus on the API changes`）
- `CLAUDE.md` 的 "Compact Instructions" 章节控制摘要保留的核心内容

**JetBrains Research 实验结论（2025年12月）**：
> 在 500 个 SWE-bench 实例上测试，LLM 摘要相比观测遮蔽（Observation Masking）有以下缺陷：
> - 额外 API 调用占总成本的 **7%+**
> - 导致 agent 运行时间增加 **13-15%**
> - 遮蔽了任务终止信号，使代理难以判断何时停止

#### 2.1.3 观测遮蔽（Observation Masking）

**核心思想**：只对"环境观测"（工具输出、命令结果）应用截断/遮蔽，保留 agent 的完整推理过程和动作历史。

**SWE-agent 实现**：
- 历史交互保留最近 5 步，更早的步骤折叠为摘要
- 文件查看器以滑动窗口（典型 100 行）展示内容，带行号和省略标记
- `HistoryProcessor` 组件负责在发送给 LLM 前压缩历史

**JetBrains Research 实验结论**：
- 成本节省超过 **52%**（相比无管理的基准）
- 在 5 个测试配置中的 4 个中，性能等于或优于 LLM 摘要
- 推荐策略：**默认使用观测遮蔽，仅在上下文密度达到临界阈值时才触发 LLM 摘要**

#### 2.1.4 ACON 框架（Adaptive Context Optimization，2025年10月）

**核心创新**：梯度无关的提示优化框架，无需参数更新，直接兼容闭源 API。

**算法流程**：
1. 压缩两类内容：交互历史（超阈值时）和环境观测（超大小时）
2. **对比反馈循环**：比较"有压缩的失败轨迹"与"无压缩的成功轨迹"
3. LLM 优化器分析差异，迭代更新压缩 prompt（"文本梯度下降"）
4. 两阶段优化：效用最大化（UT）+ 压缩最大化（CO）

**实验结果（AppWorld、OfficeBench 等三个基准）**：
- Token 峰值减少 **26-54%**
- 大型模型性能持平或改善
- 小型代理性能提升 **20-46%**
- 知识可蒸馏到小模型，保留 **95%+** 精度

#### 2.1.5 层级摘要（Hierarchical Summarization）

对旧内容进行多级压缩：最近交互保持原文 → 次近交互被压缩一次 → 更旧的交互被压缩多次。

**Mem0 实现**：
- 取最近 m 条消息 + 滚动摘要 + 最新交换，送入 LLM 提取候选记忆
- 对每个候选与向量库中 top-s 相似条目比较，检测冲突
- LLM 驱动的更新解析器决定：添加、合并、废弃或跳过

### 2.2 各平台策略汇总

| 平台 | 主要策略 | 特色机制 |
|------|----------|----------|
| **Claude Code** | 自动 compaction + 手动 `/compact` | CLAUDE.md 跨 compaction 持久化；子智能体隔离 |
| **OpenHands** | LLM 摘要（Context Condensation） | CondensationEvent 标记，原始事件流保持完整 |
| **SWE-agent** | 观测遮蔽 + 滑动窗口文件查看 | HistoryProcessor；最近 5 步保全，更早的折叠 |
| **Cline** | 层级裁剪 + Auto-compact 选项 | 按语义相关性而非时间顺序保留；硬限制 50k |
| **Aider** | 动态 repo-map + 显式文件选择 | Token 预算控制；PageRank 排名代码重要性 |
| **Windsurf/Cascade** | 实时动作追踪 + RAG 检索 | 不需要用户手动提供上下文；AST 索引 |
| **Cursor** | RAG + @-mention 显式引用 | 向量库（Turbopuffer）；每 5 分钟增量更新 |

---

## 三、记忆系统设计

### 3.1 记忆类型分类

业界已形成共识的四层记忆模型：

```
┌─────────────────────────────────────────────────┐
│            工作记忆 (Working Memory)             │
│  当前任务的中间状态、scratchpad、TODO 列表        │
│  载体：context window（最高优先级）              │
├─────────────────────────────────────────────────┤
│            短期记忆 (Short-term Memory)          │
│  当前会话的对话历史、工具调用结果                  │
│  载体：context window（会话内持续累积）           │
├─────────────────────────────────────────────────┤
│            情节记忆 (Episodic Memory)            │
│  特定事件的记录：过去的错误、成功的方案             │
│  载体：向量数据库、结构化日志                     │
├─────────────────────────────────────────────────┤
│            语义记忆 (Semantic Memory)            │
│  通用知识：项目架构、编码规范、API 约定            │
│  载体：CLAUDE.md / AGENTS.md / .cursorrules      │
└─────────────────────────────────────────────────┘
```

### 3.2 MemGPT/Letta：OS Paging 式虚拟上下文管理

MemGPT（现为 Letta 框架基础）将操作系统的虚拟内存分页思想应用于 LLM：

```
虚拟上下文（Virtual Context）= 所有可用信息的全集
物理上下文（Physical Context）= 当前 context window（有限）

LLM OS 的职责：在两者之间智能换页（paging）
```

**三级记忆层次**：
1. **Core Memory（RAM）**：常驻 context window；包含人物信息（persona）和用户画像（human），LLM 通过函数调用直接读写
2. **Archival Memory（磁盘）**：外部向量数据库；无限容量；通过 `archival_memory_search` 工具检索
3. **Recall Memory（会话日志）**：历史对话存档；通过 `conversation_search` 工具访问

**自我管理机制**：LLM 通过调用内置函数（`core_memory_replace`、`core_memory_append`、`archival_memory_insert`）主动管理自己的记忆，而非被动接受截断。

### 3.3 Claude Code 记忆系统

#### CLAUDE.md 文件层次

```
优先级由高到低（更具体的优先）：
1. 企业管理策略 (Managed Policy CLAUDE.md)
   macOS: /Library/Application Support/ClaudeCode/CLAUDE.md
   Linux: /etc/claude-code/CLAUDE.md
   Windows: C:\Program Files\ClaudeCode\CLAUDE.md

2. 用户全局规则 (~/.claude/CLAUDE.md)
   个人偏好，跨所有项目

3. 项目规则 (./CLAUDE.md 或 ./.claude/CLAUDE.md)
   团队共享，通过版本控制分发

4. 子目录规则（按需加载）
   访问子目录文件时才加载对应 CLAUDE.md
```

**加载机制**：
- 当前工作目录及其所有父目录的 CLAUDE.md 在启动时**全量加载**
- 子目录的 CLAUDE.md **按需加载**（只在 Claude 读取该子目录文件时）
- `@path/to/file` 导入语法支持引用外部文件，最大递归深度 5 层
- HTML 注释 `<!-- ... -->` 在注入上下文前被剥离（节省 token）

**路径作用域规则（`.claude/rules/`）**：
```yaml
---
paths:
  - "src/api/**/*.ts"
---
# 仅当 Claude 处理匹配文件时，此规则才加载到上下文
```

#### Auto Memory（自动记忆）

- 由 Claude 自主写入，存储在 `~/.claude/projects/<project>/memory/`
- 结构：`MEMORY.md`（索引，每次会话开始时加载前 200 行/25KB） + 按主题分拆的文件（`debugging.md`、`api-conventions.md` 等，按需读取）
- Claude 判断哪些信息值得记忆（构建命令、调试洞察、架构决策）
- 子智能体可维护独立的 auto memory

#### Skills（技能文件）的懒加载

```
会话启动时：只读取技能名称 + 描述（约 80 tokens/技能）
↓
Claude 判断技能相关时：加载技能体（275-8000 tokens）
↓
技能体引用其他文件时：按需读取这些文件
```

这是**三级惰性加载**的典范：metadata → body → referenced files。

### 3.4 Windsurf Cascade Memories

**两种类型**：
- **Auto-generated Memories**：Cascade 在会话中自动创建，与工作区绑定，存储于 `~/.codeium/windsurf/memories/`，仅本机有效
- **User Rules**（用户定义规则）：明确编写的规范，可在 `.windsurfrules` 文件中版本化

**检索机制**：Cascade 自动判断哪些记忆与当前任务相关并加载（未公开算法细节）

**关键区别**：Auto memories 仅本机有效，团队共享知识应使用 Rules 或 `AGENTS.md`

### 3.5 Mem0：生产级长期记忆框架

**双存储架构**：
```
输入消息
    ↓
Entity Extractor → 节点（人、地点、概念）
Relations Generator → 有向边（关系标签）
    ↓                              ↓
向量数据库（语义相似检索）    图数据库（Neo4j/Neptune/Kuzu 等）
                  ↓
        混合检索（向量相似 + 图遍历）
```

**两阶段管道**：
1. **Extraction（提取）**：取最近消息 + 滚动摘要 + 最新交换 → LLM 提取候选记忆
2. **Update（更新）**：与向量库 top-s 相似条目比较 → 冲突检测 → LLM 决定 添加/合并/废弃/跳过

**生产性能**：
- 相比 OpenAI 记忆系统：准确率提升 **26%**，p95 延迟降低 **91%**，token 成本节省 **90%**
- 图记忆变体在基础配置上再提升约 **2%**

### 3.6 A-MEM：Zettelkasten 式智能记忆（2025年2月）

受知识管理方法 Zettelkasten 启发的 agent 记忆系统：
- 新记忆生成时：同时生成上下文描述、关键词、标签
- 建立链接时：分析历史记忆，识别相关连接
- 动态演化：新记忆整合时，可触发对现有记忆的上下文重新表示和属性更新

---

## 四、代码库上下文注入

### 4.1 Aider 的 Repo-Map 方案

**核心思想**：不把整个代码库放入上下文，而是生成一张"代码导航图"（repo map），让 LLM 了解整体结构，再按需读取具体文件。

**技术实现**：
```
Tree-sitter 解析 → 提取所有语言的符号定义（函数、类、方法签名）
                              ↓
构建依赖图：每个源文件为节点，文件间依赖为有向边
                              ↓
PageRank 算法：对节点按被引用频率排名
                              ↓
二分搜索 → 在 token 预算（默认 1k token）内选择最重要的符号
                              ↓
生成紧凑的 repo map（仅包含签名和文件路径）
```

**动态调整**：当聊天中没有指定文件时，repo map 显著扩展；添加文件到聊天后，map 收缩以腾出 token 空间。

支持 **130+ 编程语言**（通过 tree-sitter）。

### 4.2 Cursor 的 RAG 代码库索引

**索引流程**：
```
代码库 → 语义分块（函数/类/逻辑块）→ 自定义 Embedding 模型 → 向量化
                                                                  ↓
                                               Turbopuffer 向量数据库
```

**检索触发**：
- 用户提问时，查询被向量化
- 与存储的代码向量做相似度匹配
- 嵌入在客户端侧解密（安全设计）

**增量更新**：每 5 分钟同步，仅处理变更文件；索引 80% 完成后语义搜索可用；6 周不活跃后删除。

**语义精度**：相比传统关键词搜索，准确率提升 **12.5%**。

**文件过滤**：遵守 `.gitignore` 和 `.cursorignore`；推荐忽略大型生成文件以提高精度。

### 4.3 Windsurf Cascade 的 AST 级索引

与文件级索引或朴素分块不同，Windsurf 使用代码的 **AST（抽象语法树）表示**进行索引：
- 对大型文件和企业代码库表现尤为出色
- 理解代码语义结构，而非仅做文本处理

**M-Query（上下文组装管道）**：
```
每次用户交互时自动执行：
1. 加载全局 .windsurfrules
2. 加载项目级规则
3. 加载相关 Memories
4. 读取当前打开文件
5. M-Query：从 AST 索引中语义检索相关片段
6. 读取当前会话的最近动作（文件编辑、终端命令、导航历史）
7. 组装最终 prompt
```

**实时动作追踪**：Cascade 追踪你的所有行为（编辑、命令、对话历史、剪贴板、终端命令），推断意图并实时调整，**消除了用户手动提供上下文的需要**。

### 4.4 代码图谱方法（Graph-RAG for Code）

2025 年出现的前沿方案：

**AST + 知识图谱**：
- 解析 AST → 构建知识图谱（函数调用 → 边，类继承 → 边，模块导入 → 边）
- Graph-RAG 支持多跳推理（"这个函数的所有调用者的测试覆盖情况"）

**代表工具**：
- `code-graph-rag`：专为 monorepo 设计，支持多语言
- `contextplus`（MCP）：结合 RAG、Tree-sitter AST、谱聚类（Spectral Clustering）和 Obsidian 风格链接
- 基于 AST 的可靠 Graph-RAG（arXiv 2601.08773）

**方案对比**：

| 方案 | 精度 | 扩展性 | 多跳推理 | 实现复杂度 |
|------|------|--------|----------|------------|
| 关键词搜索 | 低 | 高 | 无 | 低 |
| 向量 RAG | 中 | 高 | 弱 | 中 |
| Aider repo-map | 高（结构化） | 中（token 预算限制） | 无 | 中 |
| AST + Graph RAG | 高 | 中 | 强 | 高 |

### 4.5 Codified Context 分层架构（arXiv 2602.20478）

在 108,256 行 C# 代码库、283 个开发会话的实证研究中，提出三层上下文组织：

```
┌────────────────────────────────────────────────────┐
│  Tier 1: Project Constitution（热记忆，~660行）     │
│  每次会话全量加载；编码质量标准、命名约定、构建命令  │
│  包含任务路由表：文件变更 → 触发对应专业 agent      │
├────────────────────────────────────────────────────┤
│  Tier 2: 专业领域 Agent（~9,300行，19个规范）       │
│  50%+ 内容是领域知识（非指令）                     │
│  高能力 agent 处理复杂领域；标准 agent 处理聚焦任务 │
├────────────────────────────────────────────────────┤
│  Tier 3: Codified Context Base（冷记忆，~16,250行） │
│  34 个子系统规范；通过 MCP 服务器按关键词按需检索   │
│  专为机器消费编写（含文件路径、函数名、明确模式）    │
└────────────────────────────────────────────────────┘
```

**关键发现**：
- 嵌入领域知识的 agent 显著优于仅依赖检索的 agent
- 上下文基础设施占代码库大小的 **24.2%**（26,200 行 / 108,256 行）
- 规范陈旧（Specification Staleness）是最主要的失败模式，需每周 1-2 小时维护

---

## 五、任务/计划状态管理

### 5.1 TODO 系统设计

**Claude Code 的 TodoWrite 机制**：
- 维护结构化 TODO 列表（`content` + `status: pending/in_progress/completed`）
- 在 agentic 循环中主动更新，反映实时进度
- 作为"工作记忆"存在于 context window 中

**关键原则**（Anthropic 工程师建议）：
> 将 agent 视为无状态函数：接收输入状态，产生新输出状态。状态本身由外部管理（数据库/文件），每轮以上下文形式传入 LLM。

**外部文件作为状态存储**：

Anthropic 总结的三种长时任务策略之一是"结构化笔记记录（Structured Note-Taking）"：
- Agent 维护外部记忆文件（`NOTES.md`、`todo.md`）
- 需要时通过工具访问
- 允许跨复杂工作流追踪进度，而不需将所有内容存储在活跃上下文中

### 5.2 计划-执行框架

2025 年成熟的闭环模式：

```
问题描述 + 当前状态/记忆
            ↓
         Planner LLM
            ↓ 生成计划或命令
         Executor
            ↓ 执行动作，返回结果
       Summarizer/Memory
            ↓ 压缩动作-观测对，执行 token 预算
         更新状态
            ↓
          ↺ 循环
```

**JSON 计划格式**：已成为机器可执行计划的标准（Planner 生成 JSON，Executor 解析执行）。

**上下文供给 Planner**：压缩或滑动窗口版本的所有动作-观测对 + Summarizer 模块裁剪冗余。

### 5.3 Claude Code Agent Teams 的任务协调

**共享任务列表**：所有 agent 可见任务状态（pending/in_progress/completed），支持依赖关系声明。

**文件锁防竞争**：多个 teammate 同时认领任务时，使用**文件锁（file locking）**防止竞争条件。

**存储位置**：
- Team config：`~/.claude/teams/{team-name}/config.json`
- Task list：`~/.claude/tasks/{team-name}/`

**质量门控 Hooks**：
- `TeammateIdle`：teammate 空闲前触发，退出码 2 可发送反馈让其继续工作
- `TaskCompleted`：任务标记完成前触发，退出码 2 可阻止完成并发送反馈

### 5.4 Scratchpad 模式

用于复杂推理的中间工作空间：

| 类型 | 描述 | 使用场景 |
|------|------|----------|
| 上下文可见 Scratchpad | 作为 prompt/输出 token 存在 | 链式思维推理 |
| 结构化 Scratchpad | JSON/YAML 格式 | 机器可解析的状态 |
| 工具追踪 | 动作-观测序列 | agentic 循环日志 |
| 隐式推理 | 模型内部计算（非 token） | 最终答案前的隐式规划 |

---

## 六、上下文优先级与过滤

### 6.1 动态上下文组装

**相关性评分维度**（主流实践）：
1. **语义相似度**：BM25 + 余弦相似度（向量空间）的混合
2. **时间衰减**：最近的信息权重更高
3. **重要性/显著性（Salience）**：手动标注或 LLM 推断的重要程度
4. **实体关系**：图遍历发现间接相关内容

**Graphlit Context Engine 定义**：
> "动态为给定任务组装最相关结构化记忆的引擎，结合语义检索、时间感知、实体关系和重要性评分，选择当前最重要的上下文。"

### 6.2 上下文分层（System Prompt vs User Context）

**Claude Code 的分层**：
```
Tier 1（最高优先）：企业 Managed Policy CLAUDE.md（系统级，不可排除）
Tier 2：项目 CLAUDE.md（版本控制，团队共享）
Tier 3：用户个人 CLAUDE.md（~/.claude/CLAUDE.md）
Tier 4：子目录 CLAUDE.md（按需加载）
Tier 5：Auto Memory（Claude 自动写入的学习笔记）
Tier 6：当前会话对话历史
Tier 7：当前任务上下文（工具输出、文件内容）
```

**注意**：CLAUDE.md 内容作为**用户消息**（而非系统提示的一部分）注入，这意味着其遵从性不能被技术强制——只能影响行为，无法硬性执行。真正的硬性执行需通过 `settings.json` 的 `permissions.deny`。

### 6.3 上下文失败模式（四大陷阱）

Weaviate 的 Context Engineering 框架总结了四种上下文失败：

| 陷阱 | 描述 | 对策 |
|------|------|------|
| **Context Poisoning** | 错误信息通过重用不断复合 | 及时清理/更新上下文；验证后再注入 |
| **Context Distraction** | 过多历史数据淹没决策 | 观测遮蔽；层级剪枝 |
| **Context Confusion** | 不相关工具/文档触发错误选择 | 精准工具描述；按需加载工具 |
| **Context Clash** | 矛盾信息产生冲突假设 | 定期审查规则文件；消除重复指令 |

### 6.4 技能/工具的按需加载

**Anthropic 2025年10月发布的 Agent Skills 格式**：
```markdown
---
name: deploy-frontend
description: 部署前端到生产环境的完整流程（约 80 tokens 的描述）
disable-model-invocation: false
---
# 实际指令体（275-8000 tokens，仅在 Claude 判断相关时加载）
...
```

同一格式在发布后数周内被 OpenAI、Google、GitHub、Cursor 采用。

**MCP 工具的延迟加载**：MCP 工具定义默认延迟加载，只有工具名称消耗上下文，完整 schema 仅在 Claude 实际使用该工具时加载（通过 `/mcp` 检查每个服务器的上下文成本）。

---

## 七、多智能体上下文共享

### 7.1 父子智能体上下文传递

**Claude Code 的两种范式**：

**Subagents（轻量隔离）**：
- 每个子智能体拥有独立的 fresh context window
- 不继承父智能体的对话历史
- 加载相同的项目上下文（CLAUDE.md、MCP 服务器、Skills）
- 完成后：向父智能体返回**摘要**（不是原始上下文）
- 效果：子任务的工作不膨胀父智能体的上下文

**Agent Teams（协作隔离）**：
- 每个 teammate 都是完全独立的 Claude Code 会话
- 通过**共享任务列表**（文件系统）协调
- 通过**邮箱系统（Mailbox）**直接相互发送消息
- Lead 发消息给 teammates：按需（message）或广播（broadcast，慎用，成本随团队规模线性增长）
- Teammates 完成时，自动通知 Lead（无需轮询）

```
父智能体 / Lead
    │
    ├── 通过 spawn prompt 传递初始上下文（不含对话历史）
    ├── 通过 mailbox 发送消息（结构化）
    └── 通过 shared task list 协调工作

Teammate A / Subagent A     Teammate B / Subagent B
    │                           │
    └── 独立 context window      └── 独立 context window
    └── 可直接发消息给 B（Teams） └── 完成后通知 Lead
```

### 7.2 Google ADK 的上下文共享协议

**同层级共享**：父智能体调用子智能体时，传递同一 `InvocationContext`，子智能体可通过 `context.state['data_key']` 共享临时状态。

**`output_key` 机制**：`LlmAgent` 的 `output_key` 属性自动将代理最终响应保存到指定状态键，供下游代理读取。

### 7.3 Chain-of-Agents 框架（Google Research）

对于超长上下文任务（如分析百万 token 代码库）：
- Worker agents 按序处理不同上下文块
- 每个 Worker 接收上一个 Worker 的消息 + 自己的上下文块
- 将有用信息传递给下一个 Worker
- 最终 Worker 合成全局答案

**优势**：避免单个 LLM 处理超长上下文时的注意力退化。

### 7.4 上下文隔离的安全考量

**信息泄露风险**：子智能体的上下文不应包含父智能体的敏感信息（API 密钥、个人数据）。

**OpenHands SecretRegistry**：
- 延迟绑定凭证注入，支持 mid-conversation 轮换
- 扫描 bash 命令中的密钥引用，自动导出为环境变量
- 在输出和日志中自动遮蔽密钥值

---

## 八、"一切皆上下文"：新兴架构范式

### 8.1 Agentic File System 抽象（arXiv 2512.05470，2025年12月）

受 Unix "一切皆文件" 启发，提出统一的上下文工程基础设施：

```
上下文文件系统命名空间
    ├── REST/OpenAPI 资源 → 自动投影为文件
    ├── GraphQL 类型 → 自动投影为文件
    ├── MCP 工具 → 自动投影为文件
    ├── 记忆存储 → 自动投影为文件
    └── 外部 API → 自动投影为文件
```

**三组件管道**：
- **Context Constructor**：组装上下文（schema 驱动）
- **Context Loader**：在 token 约束下交付上下文
- **Context Evaluator**：验证上下文质量和完整性

**优势**：异构数据源（REST、GraphQL、MCP、记忆、工具）通过统一语义接口访问，消除集成代码。

### 8.2 Agentic Context Engineering 演化框架（arXiv 2510.04618）

提出上下文工程的"持续演化"视角：
- 原始数据追加到历史（History）
- 转换为优化检索的记忆表示（Memory）
- 推理期间写入 Scratchpad
- Scratchpad 内容选择性归档到 Memory 或 History

这使得系统能够**持续自改进**，而非依赖静态知识。

---

## 九、各平台完整对比矩阵

### 9.1 上下文管理能力矩阵

| 维度 | Claude Code | Cursor | Windsurf | Cline | Aider | OpenHands | SWE-agent |
|------|-------------|--------|----------|-------|-------|-----------|-----------|
| **代码库索引** | 按需读取 + MCP | 向量 RAG (Turbopuffer) | AST RAG | 无（显式文件） | Repo-Map (PageRank) | 无（工具调用） | 无（工具调用） |
| **跨会话记忆** | CLAUDE.md + Auto Memory | .cursorrules + Memories | .windsurfrules + Memories | 无内置 | 无内置 | 无内置 | 无内置 |
| **上下文压缩** | Auto Compaction | 隐式（未公开） | 未公开 | Auto-compact + 层级剪枝 | Token 预算截断 | Context Condensation | Observation Masking |
| **任务状态管理** | TodoWrite + 共享任务列表 | 未公开 | 未公开 | 未公开 | 无 | Event Stream | 无 |
| **多智能体** | Subagents + Agent Teams | Background Agents | 未公开 | 无 | 无 | 多 Agent（实验） | 单 Agent |
| **规则文件格式** | CLAUDE.md + .claude/rules/*.md | .cursor/rules/*.mdc | .windsurfrules | 无 | 无 | AGENTS.md | 无 |
| **工具懒加载** | Skills + MCP 延迟加载 | 未公开 | 未公开 | 否 | 否 | 是（MCP） | 否 |

### 9.2 记忆存储格式对比

| 平台/框架 | 短期记忆 | 长期记忆 | 工作记忆 |
|-----------|----------|----------|----------|
| **Claude Code** | Context Window | CLAUDE.md + MEMORY.md（本地文件） | TodoWrite（context 内） |
| **MemGPT/Letta** | Core Memory（context） | Archival Memory（向量库） | Recall Memory（对话日志） |
| **Mem0** | Context Window | 向量库 + 图数据库 + KV Store | 滚动摘要 |
| **Windsurf** | Context Window | ~/.codeium/windsurf/memories/ | 实时动作追踪 |
| **OpenHands** | Event Stream（当前会话） | 无（跨会话记忆依赖外部） | CondensationEvent 摘要 |
| **A-MEM** | Context Window | Zettelkasten 互连笔记网络 | 链接图谱 |

---

## 十、业界最佳实践总结

### 10.1 上下文窗口管理

1. **默认使用观测遮蔽**：相比 LLM 摘要，成本更低（无额外 API 调用），延迟更小，且在多数基准上性能相当或更优
2. **LLM 摘要作为后备**：仅在上下文密度接近临界时触发
3. **系统指令放入持久文件**：不依赖对话历史来传递规则（`CLAUDE.md`、`.cursorrules`），因为压缩/截断后这些指令会丢失
4. **子智能体承接重型任务**：将探索性工作委托给子智能体，只接收摘要，避免父智能体上下文膨胀
5. **"有效窗口"约为声明窗口的 50-70%**：超过这个阈值，模型注意力开始分散

### 10.2 记忆系统设计

1. **明确分层**：语义记忆（规则文件）、情节记忆（向量库/图库）、工作记忆（context 内）严格分离
2. **惰性加载**：技能/工具描述（metadata）始终可见，完整内容（body）只在相关时加载
3. **记忆持久化格式首选纯文本**：Markdown 文件易于人工审查、编辑和版本控制
4. **建立记忆更新机制**：避免"规范陈旧"，定期（如每周）审查和更新上下文文件
5. **向量库 + 图库的混合存储**：向量库处理语义相似搜索，图库处理关系推理，各有擅长

### 10.3 代码库上下文注入

1. **忽略文件至关重要**：`.gitignore`、`.cursorignore` 排除生成文件，显著提高检索精度
2. **结构感知分块**：使用 Tree-sitter 按语义单元（函数/类）分块，而非按行数截断
3. **PageRank/引用频率排序**：识别核心 API 和高度被依赖的模块，优先放入 repo map
4. **三层渐进加载**：文件树摘要 → 关键文件签名 → 具体实现，按需深入
5. **领域知识嵌入 Agent 规范**：实证研究表明，包含领域知识（>50%）的专业 agent 优于纯检索 agent

### 10.4 多智能体上下文设计

1. **上下文隔离是默认**：子智能体/teammate 不继承父智能体对话历史，防止上下文污染
2. **返回摘要而非原始上下文**：子智能体完成任务后，向父智能体返回精炼摘要（1000-2000 tokens），而非完整工作上下文
3. **共享任务列表作为协调媒介**：避免 agent 间直接传递大量上下文，通过结构化任务状态协调
4. **文件系统作为共享状态**：多 agent 通过读写共同可见的文件（而非直接消息传递）共享信息，可审计、可恢复
5. **广播慎用**：广播消息成本随团队规模线性增长，优先使用定向消息

### 10.5 面向未来的架构建议

1. **将上下文工程视为基础设施**：不是 prompt 技巧，而是需要版本控制、测试和维护的系统
2. **统一上下文接口**（参考 AFS 论文）：通过类文件系统的统一语义接口管理所有类型的上下文来源
3. **持续演化的上下文**（参考 ACE 论文）：系统应能从交互中学习，自动更新记忆表示，而非依赖静态规则
4. **ACON 式自适应压缩**：使用对比学习方法自动发现哪些信息对特定任务至关重要

---

## 十一、参考资料

### 主要平台文档
- [How Claude Code Works](https://code.claude.com/docs/en/how-claude-code-works)
- [Claude Code Memory System](https://code.claude.com/docs/en/memory)
- [Claude Code Agent Teams](https://code.claude.com/docs/en/agent-teams)
- [Cursor Codebase Indexing Docs](https://cursor.com/docs/context/codebase-indexing)
- [Windsurf Cascade Memories](https://docs.windsurf.com/windsurf/cascade/memories)
- [Cline Context Management](https://docs.cline.bot/prompting/understanding-context-management)
- [Aider Repository Map](https://aider.chat/docs/repomap.html)
- [SWE-agent Architecture](https://swe-agent.com/latest/background/architecture/)
- [OpenHands Context Condensation Blog](https://openhands.dev/blog/openhands-context-condensensation-for-more-efficient-ai-agents)

### 学术论文
- [Codified Context: Infrastructure for AI Agents (arXiv 2602.20478)](https://arxiv.org/html/2602.20478v1)
- [ACON: Optimizing Context Compression (arXiv 2510.00615)](https://arxiv.org/html/2510.00615v1)
- [A-MEM: Agentic Memory for LLM Agents (arXiv 2502.12110)](https://arxiv.org/abs/2502.12110)
- [Mem0: Production-Ready AI Agents (arXiv 2504.19413)](https://arxiv.org/abs/2504.19413)
- [Everything is Context: Agentic File System (arXiv 2512.05470)](https://arxiv.org/abs/2512.05470)
- [SWE-agent Paper (arXiv 2405.15793)](https://arxiv.org/pdf/2405.15793)
- [OpenHands SDK Paper (arXiv 2511.03690)](https://arxiv.org/html/2511.03690v1)
- [MemGPT Paper (arXiv 2310.08560)](https://arxiv.org/abs/2310.08560)

### 技术博客与分析
- [Anthropic: Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [JetBrains Research: Efficient Context Management (Dec 2025)](https://blog.jetbrains.com/research/2025/12/efficient-context-management/)
- [Weaviate: Context Engineering - LLM Memory and Retrieval](https://weaviate.io/blog/context-engineering)
- [Letta: Agent Memory Architecture](https://www.letta.com/blog/agent-memory)
- [Mem0: Graph Memory](https://docs.mem0.ai/open-source/features/graph-memory)
- [Augment Code: Context Engine](https://www.augmentcode.com/context-engine)
- [How Cursor Actually Indexes Your Codebase (Jan 2026)](https://bardai.ai/2026/01/26/how-cursor-actually-indexes-your-codebase/)
- [Claude Code Context Buffer Analysis](https://claudefa.st/blog/guide/mechanics/context-buffer-management)
