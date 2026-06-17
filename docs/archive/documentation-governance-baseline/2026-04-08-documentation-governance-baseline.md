# Documentation Governance Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立仓库文档治理基线、第一批核心模块文档，以及 `superpowers -> 全局项目文档 -> archive` 的同步闭环。

**Architecture:** 本计划只执行已批准设计中的第 1 批和第 2 批：先建立 `docs/` 下的治理规则、工作流、参考索引和模板，再补齐核心子系统模块文档，并把新的治理模型同步回 `README.md`、`AGENTS.md` 和项目跟踪文档。GUI、TUI、打包交付模块文档，以及大规模历史归档清理，留给后续独立切片。

**Tech Stack:** Markdown, Mermaid, ripgrep, Git

---

> **Execution note:** 执行本计划前，先切到独立 feature branch 或 worktree；不要直接在 `main` 上做这一轮文档重构。

## File Structure

### Governance scaffold

- Create: `docs/README.md`
- Create: `docs/documentation-governance.md`
- Create: `docs/documentation-style-guide.md`
- Create: `docs/workflows/README.md`
- Create: `docs/workflows/code-doc-sync.md`
- Create: `docs/workflows/architecture-change-process.md`
- Create: `docs/workflows/release-doc-checklist.md`

### References and templates

- Create: `docs/references/glossary.md`
- Create: `docs/references/code-doc-matrix.md`
- Create: `docs/references/diagrams-conventions.md`
- Create: `docs/templates/architecture-doc-template.md`
- Create: `docs/templates/module-doc-template.md`
- Create: `docs/templates/workflow-doc-template.md`
- Create: `docs/templates/adr-template.md`
- Create: `docs/templates/change-entry-template.md`

### Root source-of-truth updates

- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

### Core module docs

- Create: `docs/modules/README.md`
- Create: `docs/modules/agent-core.md`
- Create: `docs/modules/session-runtime.md`
- Create: `docs/modules/harness.md`
- Create: `docs/modules/tools-and-tooling.md`
- Create: `docs/modules/permissions-and-context.md`

### Verification

- Verify: `rg --files docs`
- Verify: `rg -n "superpowers|archive|模块文档|术语表" README.md AGENTS.md docs`
- Verify: `rg -n "```mermaid" docs/modules/*.md docs/workflows/*.md`

### Task 1: Create The Governance Scaffold

**Files:**
- Create: `docs/README.md`
- Create: `docs/documentation-governance.md`
- Create: `docs/documentation-style-guide.md`
- Create: `docs/workflows/README.md`
- Create: `docs/workflows/code-doc-sync.md`
- Create: `docs/workflows/architecture-change-process.md`
- Create: `docs/workflows/release-doc-checklist.md`

- [ ] **Step 1: Create the new directories and write the docs index**

Create the directory structure:

```powershell
New-Item -ItemType Directory -Force docs/workflows
New-Item -ItemType Directory -Force docs/references
New-Item -ItemType Directory -Force docs/templates
New-Item -ItemType Directory -Force docs/modules
```

Write `docs/README.md` with this section structure:

```md
# 文档导航

## 1. 文档分层

- `docs/superpowers/`：当前切片说明书
- `docs/` 活动文档：长期 source-of-truth
- `docs/archive/`：历史留痕

## 2. 项目级官方文档

- `overall-solution-architecture.md`
- `implementation-roadmap.md`
- `development-tracker.md`
- `design-change-log.md`
- `mode-schema.md`
- `tool-contracts.md`
- `permission-model.md`
- `frontend-protocol.md`
- `agent-harness-v2.md`

## 3. 模块文档

## 4. 工作流文档

## 5. 参考与模板

## 6. Archive 使用规则
```

- [ ] **Step 2: Write the governance rules document**

Write `docs/documentation-governance.md` with these exact sections:

```md
# Documentation Governance

## 1. Purpose

## 2. Document Layers

### 2.1 `superpowers` process docs

### 2.2 global project docs

### 2.3 archive docs

## 3. Source-of-Truth Rules

## 4. Active Document Types

## 5. Ownership And Update Rules

## 6. Code-Doc Sync Policy

## 7. Archive Policy

## 8. Related Documents
```

The content must explicitly encode:

- `superpowers` 文档是“当前一轮切片说明书”
- 全局项目文档是长期真相
- 已完成切片必须回写全局文档并归档
- 活动文档不得依赖 archive 作为当前真相

- [ ] **Step 3: Write the style guide**

Write `docs/documentation-style-guide.md` with these exact sections:

```md
# Documentation Style Guide

## 1. Language Rules

## 2. Metadata Block

## 3. Required Sections By Document Type

## 4. Terminology Rules

## 5. Code Mapping Rules

## 6. Mermaid And Diagram Rules

## 7. Historical Content Rules

## 8. Review Checklist
```

The guide must require:

- 中文主叙述
- 英文术语和代码标识保留原文并使用反引号
- `architecture` / `module` / `workflow` 的固定章节骨架
- Mermaid 图的强制场景
- 历史术语仅允许出现在兼容或历史章节

- [ ] **Step 4: Write the workflow docs**

Write `docs/workflows/README.md` as the workflow index and create the three workflow files with these top-level headings:

```md
# Documentation Workflows

## 1. Code-Doc Sync

## 2. Architecture Change Process

## 3. Release Doc Checklist
```

```md
# Code-Doc Sync Workflow

## 1. Trigger Conditions

## 2. Change Classification

## 3. Impact Assessment

## 4. Implementation And Sync

## 5. Verification

## 6. Tracker / Change Log / ADR Updates

## 7. Archive Handoff
```

```md
# Architecture Change Process

## 1. When This Workflow Applies

## 2. Required Inputs

## 3. `superpowers` Design Output

## 4. Global Doc Sync Rules

## 5. Review Gates

## 6. Closeout Rules
```

```md
# Release Doc Checklist

## 1. Scope Confirmation

## 2. User-Facing Guide Check

## 3. Validation Doc Check

## 4. Source-of-Truth Check

## 5. Archive Check
```

At least one workflow document must include a Mermaid `flowchart` describing `superpowers -> implementation -> global docs -> archive`.

- [ ] **Step 5: Verify the governance scaffold exists and is cross-linkable**

Run:

```powershell
rg --files docs/workflows docs | Sort-Object
```

Expected:

- the new `docs/workflows/` files are listed
- `docs/README.md`, `docs/documentation-governance.md`, and `docs/documentation-style-guide.md` are listed

Run:

```powershell
rg -n "^# |^## " docs/README.md docs/documentation-governance.md docs/documentation-style-guide.md docs/workflows/*.md
```

Expected:

- every file returns its expected section headings
- no file is empty

- [ ] **Step 6: Commit the scaffold**

```bash
git add docs/README.md docs/documentation-governance.md docs/documentation-style-guide.md docs/workflows
git commit -m "docs: add documentation governance scaffold"
```

### Task 2: Add References And Reusable Templates

**Files:**
- Create: `docs/references/glossary.md`
- Create: `docs/references/code-doc-matrix.md`
- Create: `docs/references/diagrams-conventions.md`
- Create: `docs/templates/architecture-doc-template.md`
- Create: `docs/templates/module-doc-template.md`
- Create: `docs/templates/workflow-doc-template.md`
- Create: `docs/templates/adr-template.md`
- Create: `docs/templates/change-entry-template.md`

- [ ] **Step 1: Write the glossary**

Write `docs/references/glossary.md` with these sections and tables:

```md
# Glossary

## 1. Official Product Vocabulary

## 2. Official Document Vocabulary

## 3. Historical Terms And Their Status

## 4. Usage Rules
```

Include rows for at least:

- `explore`
- `spec`
- `build`
- `debug`
- `verify`
- `TaskGraph`
- `task_status`
- `discipline_profile`
- `execution_phase`
- `transcript.jsonl`
- `SessionHistoryAssembler`
- `superpowers process docs`
- `global project docs`
- `archive docs`

Mark at least these as historical / disallowed in active docs:

- `code` as first-class mode
- `todos`
- `manage_todos`

- [ ] **Step 2: Write the code-doc matrix**

Write `docs/references/code-doc-matrix.md` with a table shaped like this:

```md
# Code-Doc Matrix

| Code Area | Primary Paths | Global Docs | Module Docs | Workflow / Reference Docs |
|---|---|---|---|---|
| Agent Core | `src/embedagent/query_engine.py`, `src/embedagent/inprocess_adapter.py`, `src/embedagent/session_runtime.py` | `overall-solution-architecture.md`, `agent-harness-v2.md` | `modules/agent-core.md` | `references/glossary.md` |
```

Populate rows for:

- Agent Core
- Session Runtime
- Harness
- Tools / Tooling
- Permissions / Context
- Protocol / Core
- Frontend TUI
- Frontend GUI
- Packaging / Deployment

- [ ] **Step 3: Write the diagram conventions**

Write `docs/references/diagrams-conventions.md` with these sections:

```md
# Diagram Conventions

## 1. Preferred Diagram Types

## 2. When Mermaid Is Required

## 3. Labeling Rules

## 4. Code And Document Boundaries

## 5. Update Rules
```

Include examples for:

- `flowchart`
- `sequenceDiagram`
- `stateDiagram-v2`

- [ ] **Step 4: Write all reusable templates**

Create the five template files with these top-level structures:

```md
# Architecture Document Template

## Metadata

## 1. Purpose And Scope

## 2. Audience

## 3. Official Model

## 4. Code Mapping

## 5. Key Flows

## 6. Verification

## 7. Change Triggers

## 8. Related Documents
```

```md
# Module Document Template

## Metadata

## 1. Purpose And Scope

## 2. Responsibilities

## 3. Code Mapping

## 4. Dependencies And Consumers

## 5. Data / Control Flow

## 6. Verification And Tests

## 7. Change Triggers

## 8. Related Documents
```

```md
# Workflow Document Template

## Metadata

## 1. Purpose And Scope

## 2. Trigger Conditions

## 3. Required Inputs

## 4. Execution Steps

## 5. Verification

## 6. Related Documents
```

```md
# ADR Template

## Status

## Context

## Decision

## Consequences

## Follow-Up
```

```md
# Change Entry Template

- 日期：
- 变更主题：
- 变更摘要：
- 影响范围：
- 关联文档：
- 是否需要 ADR：
- 后续动作：
```

- [ ] **Step 5: Verify the references and templates**

Run:

```powershell
rg --files docs/references docs/templates | Sort-Object
```

Expected:

- all eight new files are listed

Run:

```powershell
rg -n "^# |^## " docs/references/*.md docs/templates/*.md
```

Expected:

- every file exposes the required section skeleton

- [ ] **Step 6: Commit the references and templates**

```bash
git add docs/references docs/templates
git commit -m "docs: add documentation references and templates"
```

### Task 3: Update Root Entry Points And Governance Rules

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/implementation-roadmap.md`

- [ ] **Step 1: Add documentation navigation to the root README**

Update `README.md` to add a short documentation navigation section under the current architecture summary. The new section must include these bullets:

```md
## Documentation Model

- `docs/superpowers/` stores design and implementation materials for the current slice.
- `docs/` active documents store the long-lived project source of truth.
- `docs/archive/` stores completed slice artifacts and historical references.

## Documentation Entry Points

- `docs/README.md`
- `docs/documentation-governance.md`
- `docs/documentation-style-guide.md`
- `docs/workflows/code-doc-sync.md`
- `docs/references/glossary.md`
```

- [ ] **Step 2: Extend AGENTS.md with the new documentation layering model**

Update the `Documentation Maintenance` section in `AGENTS.md` to add these exact rules:

```md
- `docs/superpowers/` design and plan documents are slice-local working materials, not permanent architecture truth.
- When a slice is completed, its durable conclusions must be synchronized back into global source-of-truth docs and module docs.
- Governance rules, workflow rules, terminology, and templates live under `docs/` active documentation, not inside archived or slice-local files.
- Completed slice documents should be moved to `docs/archive/` after global docs are synchronized.
```

Do not remove the existing source-of-truth file list.

- [ ] **Step 3: Add documentation governance to the roadmap**

Update `docs/implementation-roadmap.md` to add a short subsection under near-term work with this shape:

```md
### 4.X Documentation Governance Baseline

- establish the active docs governance scaffold
- create module-level documentation for core code areas
- standardize terminology, templates, and Mermaid usage
- keep `superpowers -> global docs -> archive` synchronization as the default closure path
```

- [ ] **Step 4: Verify the root entry points**

Run:

```powershell
rg -n "Documentation Model|docs/superpowers|docs/archive|documentation-governance|code-doc-sync|Documentation Governance Baseline" README.md AGENTS.md docs/implementation-roadmap.md
```

Expected:

- each file contains the new governance references
- the roadmap contains the new documentation governance subsection

- [ ] **Step 5: Commit the root entry-point updates**

```bash
git add README.md AGENTS.md docs/implementation-roadmap.md
git commit -m "docs: wire governance model into root entry points"
```

### Task 4: Update Tracker And Change Log

**Files:**
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Record the governance initiative in the tracker**

Update `docs/development-tracker.md` in three places:

```md
- 当前重点：补齐文档治理基线、模块文档和代码-文档同步流程
```

```md
| R-024 | 文档分层、模块映射和同步流程尚未完全建立 | 高 | 通过文档治理基线、模块文档和同步门禁收口 |
```

```md
| 2026-04-08 | 启动文档治理基线实施：建立 docs 分层、模板、术语表、同步工作流和第一批模块文档入口 |
```

- [ ] **Step 2: Add a new change-log entry**

Prepend a new `DC-100` entry to `docs/design-change-log.md` with this exact field structure:

```md
### DC-100

- 日期：2026-04-08
- 变更主题：建立文档治理基线与 `superpowers -> 全局文档 -> archive` 回写闭环
- 变更摘要：
  - 建立 `docs/` 下的治理规则、工作流、术语和模板体系
  - 明确 `superpowers` 文档是当前切片说明书，而不是长期架构真相
  - 建立核心模块文档入口和代码-文档映射规则
- 影响范围：
  - `README.md`
  - `AGENTS.md`
  - `docs/README.md`
  - `docs/documentation-governance.md`
  - `docs/documentation-style-guide.md`
  - `docs/workflows/`
  - `docs/references/`
  - `docs/templates/`
  - `docs/modules/`
- 关联文档：
  - `docs/superpowers/specs/2026-04-08-documentation-governance-baseline-design.md`
- 是否需要 ADR：`否，先作为文档治理基线实施`
- 后续动作：
  - 继续补齐协议、前端、交付模块文档
  - 分批归档 superseded 活动文档
```

- [ ] **Step 3: Verify tracker and change-log updates**

Run:

```powershell
rg -n "文档治理基线|superpowers -> 全局文档 -> archive|docs 分层|模块文档入口" docs/development-tracker.md docs/design-change-log.md
```

Expected:

- the tracker and change log both return the new governance wording

- [ ] **Step 4: Commit the tracking updates**

```bash
git add docs/development-tracker.md docs/design-change-log.md
git commit -m "docs: record documentation governance rollout"
```

### Task 5: Create The Module Index And The First Two Core Module Docs

**Files:**
- Create: `docs/modules/README.md`
- Create: `docs/modules/agent-core.md`
- Create: `docs/modules/session-runtime.md`

- [ ] **Step 1: Create the modules index**

Write `docs/modules/README.md` with this structure:

```md
# 模块文档索引

## 1. 当前已建立模块

- `agent-core.md`
- `session-runtime.md`
- `harness.md`
- `tools-and-tooling.md`
- `permissions-and-context.md`

## 2. 后续模块

- `protocol-and-core.md`
- `frontend-tui.md`
- `frontend-gui.md`
- `packaging-and-deployment.md`

## 3. 模块文档维护规则

## 4. 与全局文档的关系
```

- [ ] **Step 2: Write `agent-core.md` from the template**

Create `docs/modules/agent-core.md` using the module template and fill it with these exact code anchors:

```md
# Agent Core

## Metadata

- 状态：`active`
- 类型：`module`
- 对应代码范围：`src/embedagent/query_engine.py`, `src/embedagent/inprocess_adapter.py`, `src/embedagent/session_runtime.py`

## 1. Purpose And Scope

## 2. Responsibilities

- 会话级 `QueryEngine` 执行 owner
- `InProcessAdapter` host / bridge 边界
- session runtime host 状态

## 3. Code Mapping

- 目录：`src/embedagent/`
- 入口文件：`src/embedagent/query_engine.py`
- 核心对象：`QueryEngine`、`InProcessAdapter`、`ManagedSession`
- 上游依赖：frontend / core adapter / slash commands
- 下游影响：harness、tools runtime、session snapshot、transcript

## 4. Dependencies And Consumers

## 5. Data / Control Flow

## 6. Verification And Tests

## 7. Change Triggers

## 8. Related Documents
```

Include one Mermaid `flowchart` showing `Frontend -> Core Adapter -> InProcessAdapter -> Session Runtime -> QueryEngine`.

- [ ] **Step 3: Write `session-runtime.md` from the template**

Create `docs/modules/session-runtime.md` with these exact code anchors:

```md
# Session Runtime

## Metadata

- 状态：`active`
- 类型：`module`
- 对应代码范围：`src/embedagent/session.py`, `src/embedagent/session_history.py`, `src/embedagent/session_projector.py`, `src/embedagent/transcript_store.py`

## 1. Purpose And Scope

## 2. Responsibilities

- `Session` live structured state
- `transcript.jsonl` durable ledger
- `SessionHistoryAssembler` GUI history serialization
- bootstrap / projector / restore boundaries

## 3. Code Mapping

- 目录：`src/embedagent/`
- 入口文件：`src/embedagent/session.py`
- 核心对象：`Session`、`SessionHistoryAssembler`、`SessionSnapshotProjector`、`TranscriptStore`
- 上游依赖：`QueryEngine`
- 下游影响：GUI bootstrap、history rendering、resume path

## 4. Dependencies And Consumers

## 5. Data / Control Flow

## 6. Verification And Tests

## 7. Change Triggers

## 8. Related Documents
```

Include one Mermaid `sequenceDiagram` showing `QueryEngine -> TranscriptStore -> Session -> SessionHistoryAssembler -> /api/sessions/{id}/bootstrap`.

- [ ] **Step 4: Verify the new index and module docs**

Run:

```powershell
rg -n "^# |^## |```mermaid" docs/modules/README.md docs/modules/agent-core.md docs/modules/session-runtime.md
```

Expected:

- all three files contain the expected section headings
- both module docs contain Mermaid diagrams

- [ ] **Step 5: Commit the first module docs**

```bash
git add docs/modules/README.md docs/modules/agent-core.md docs/modules/session-runtime.md
git commit -m "docs: add agent core and session runtime module docs"
```

### Task 6: Create The Remaining First-Wave Core Module Docs

**Files:**
- Create: `docs/modules/harness.md`
- Create: `docs/modules/tools-and-tooling.md`
- Create: `docs/modules/permissions-and-context.md`

- [ ] **Step 1: Write `harness.md`**

Create `docs/modules/harness.md` with these code anchors:

```md
# Harness

## Metadata

- 状态：`active`
- 类型：`module`
- 对应代码范围：`src/embedagent/harness/`

## 1. Purpose And Scope

## 2. Responsibilities

- mode registry
- discipline defaults
- phase advancement
- prompt stack construction
- task graph generation

## 3. Code Mapping

- 目录：`src/embedagent/harness/`
- 入口文件：`src/embedagent/harness/runner.py`
- 核心对象：`HarnessRunner`、`TaskGraph`、`PhaseEngine`
- 上游依赖：`QueryEngine`、`modes.py`
- 下游影响：`task_status`、session snapshots、frontend runtime
```

Include one Mermaid `flowchart` showing `mode -> discipline_profile -> execution_phase -> TaskGraph -> session snapshot`.

- [ ] **Step 2: Write `tools-and-tooling.md`**

Create `docs/modules/tools-and-tooling.md` with these code anchors:

```md
# Tools And Tooling

## Metadata

- 状态：`active`
- 类型：`module`
- 对应代码范围：`src/embedagent/tools/`, `src/embedagent/tooling/`

## 1. Purpose And Scope

## 2. Responsibilities

- official tool runtime facade
- tool packs and contracts
- schema / catalog metadata
- recipe execution and quality reporting

## 3. Code Mapping

- 目录：`src/embedagent/tools/`, `src/embedagent/tooling/`
- 入口文件：`src/embedagent/tools/runtime.py`
- 核心对象：`ToolRuntime`、tool ops modules、tool packs
- 上游依赖：harness、query engine
- 下游影响：tool execution、context reduction、frontend tool catalog
```

Include one Mermaid `flowchart` showing `Harness -> ToolRuntime -> tool ops -> observations -> context / transcript / frontend`.

- [ ] **Step 3: Write `permissions-and-context.md`**

Create `docs/modules/permissions-and-context.md` with these code anchors:

```md
# Permissions And Context

## Metadata

- 状态：`active`
- 类型：`module`
- 对应代码范围：`src/embedagent/permissions.py`, `src/embedagent/context.py`, `src/embedagent/workspace_intelligence.py`

## 1. Purpose And Scope

## 2. Responsibilities

- permission rule matching and explanation rendering
- context budgeting and reducer routing
- workspace intelligence evidence assembly

## 3. Code Mapping

- 目录：`src/embedagent/`
- 入口文件：`src/embedagent/permissions.py`, `src/embedagent/context.py`
- 核心对象：`PermissionPolicy`、`ContextManager`、`WorkspaceIntelligence`
- 上游依赖：query engine、tool runtime
- 下游影响：tool approval UX、message assembly、verify context quality
```

Include one Mermaid `sequenceDiagram` showing `QueryEngine -> PermissionPolicy -> ToolRuntime -> ContextManager -> WorkspaceIntelligence -> model messages`.

- [ ] **Step 4: Verify all first-wave module docs**

Run:

```powershell
rg -n "^# |^## |```mermaid" docs/modules/*.md
```

Expected:

- six module files plus the index file are present
- the five module docs all contain Mermaid blocks

Run:

```powershell
rg -n "目录：|入口文件：|核心对象：|上游依赖：|下游影响：" docs/modules/*.md
```

Expected:

- every module doc contains the code mapping block fields

- [ ] **Step 5: Commit the remaining module docs**

```bash
git add docs/modules/harness.md docs/modules/tools-and-tooling.md docs/modules/permissions-and-context.md
git commit -m "docs: add harness tools and permissions module docs"
```

### Task 7: Run A Final Consistency Pass

**Files:**
- Verify: `README.md`
- Verify: `AGENTS.md`
- Verify: `docs/README.md`
- Verify: `docs/documentation-governance.md`
- Verify: `docs/documentation-style-guide.md`
- Verify: `docs/workflows/*.md`
- Verify: `docs/references/*.md`
- Verify: `docs/templates/*.md`
- Verify: `docs/modules/*.md`
- Verify: `docs/implementation-roadmap.md`
- Verify: `docs/development-tracker.md`
- Verify: `docs/design-change-log.md`

- [ ] **Step 1: Verify the full file set exists**

Run:

```powershell
rg --files docs | Sort-Object
```

Expected:

- all newly added governance, workflow, reference, template, and module docs appear in the output

- [ ] **Step 2: Verify key cross-links and vocabulary**

Run:

```powershell
rg -n "docs/superpowers|docs/archive|模块文档|术语表|code-doc matrix|Mermaid|Documentation Governance Baseline" README.md AGENTS.md docs
```

Expected:

- the new governance vocabulary appears in the updated source-of-truth docs

Run:

```powershell
rg -n "manage_todos|tasks, not todos|build, not code" AGENTS.md docs README.md
```

Expected:

- existing official vocabulary remains intact
- no new activity doc reintroduces `manage_todos` as an active workflow term except historical / glossary context

- [ ] **Step 3: Inspect the final diff**

Run:

```bash
git diff --stat HEAD~6..HEAD
```

Expected:

- the diff covers the new governance scaffold, references, templates, root updates, tracker/log updates, and module docs

- [ ] **Step 4: Commit any final consistency fixes**

```bash
git add README.md AGENTS.md docs
git commit -m "docs: finalize documentation governance baseline"
```

## Self-Review

- Spec coverage: this plan implements Batch 1 and Batch 2 from `docs/superpowers/specs/2026-04-08-documentation-governance-baseline-design.md`; later batches for frontend/packaging modules and archive migration remain intentionally out of scope.
- Placeholder scan: every file path, directory, command, section skeleton, commit message, risk number, and change-log number is explicit; there are no unresolved markers.
- Type consistency: the plan consistently uses `superpowers process docs`, `global project docs`, `archive docs`, `TaskGraph`, `task_status`, `discipline_profile`, and `execution_phase`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-08-documentation-governance-baseline.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
