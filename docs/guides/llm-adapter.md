# EmbedAgent LLM Adapter 兼容记录

> 更新日期：2026-03-27
> 适用阶段：Phase 1 完成后

---

## 1. 文档目标

记录 Phase 1 中已经验证过的 OpenAI-compatible 兼容点，避免后续在不同模型服务上重复踩坑。

本文件只记录已经实际验证到的问题，不记录纯推测。

---

## 2. 当前已验证环境

### 2.1 本地运行时

- Python：`3.8.10`
- 入口：`src/embedagent/`
- 验证方式：
  - 本地假模型闭环
  - Moonshot `kimi-k2.5` 真实 function calling 闭环

### 2.2 已验证模型服务

| 服务 | 模型 | 结果 |
|------|------|------|
| Moonshot OpenAI-compatible API | `kimi-k2.5` | 已跑通最小工具闭环 |

### 2.3 当前未验证模型

- `GLM5 int4`
- `Qwen3.5`

说明：

- 当前环境不具备这两个目标模型的联调条件，因此 Phase 1 不再阻塞于这两项验证。
- 若后续环境具备，应补做一次真实 function calling 验证。

---

## 3. 已确认的兼容点

### 3.1 Base URL 规范

对 Moonshot 来说：

- `https://api.moonshot.cn/v` 会返回 `404`
- `https://api.moonshot.cn/v1` 可以正常工作

因此 `OpenAICompatibleClient` 的 `base_url` 需要传入可拼接到 `/chat/completions` 的根路径。

### 3.2 不应硬编码 temperature

`kimi-k2.5` 会拒绝默认写死的 `temperature=0.2`，返回：

- `invalid temperature: only 1 is allowed for this model`

当前处理策略：

- `OpenAICompatibleClient` 默认不发送 `temperature`
- 只有显式传入时才带上该字段

### 3.3 必须保留 reasoning_content

`kimi-k2.5` 在工具调用场景下会返回：

- `reasoning_content`
- `tool_calls`

如果在下一轮把 assistant tool call message 回传给模型时丢掉 `reasoning_content`，会返回错误：

- `thinking is enabled but reasoning_content is missing in assistant tool call message`

当前处理策略：

- `AssistantReply` 保留 `reasoning_content`
- `Session` 在 assistant message 回放时原样带回 `reasoning_content`
- 流式与非流式解析都支持该字段

---

## 4. 当前适配层结论

Phase 1 的 LLM 适配层已经具备以下能力：

- OpenAI-compatible `/chat/completions`
- 非流式响应解析
- SSE 流式响应解析
- `tool_calls` 解析
- 非标准工具参数 JSON 的宽松解析
- `reasoning_content` 透传

当前仍未覆盖：

- 多 provider 的系统化差异矩阵
- `Responses API` 风格在更多服务上的兼容验证
- GLM5 / Qwen3.5 的真实联调结论

---

## 5. 后续建议

1. 若接入新模型服务，先做一次“只回复文本”的 ping 测试，再做一次“必须调用 read_file”的工具闭环测试。
2. 将 provider 差异收敛到 `llm.py`，不要把兼容逻辑扩散到 Loop 或工具层。
3. 在具备条件时补做 `GLM5 int4` 和 `Qwen3.5` 的实际验证，并在本文件追加记录。
