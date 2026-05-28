# Workflow Extension Boundary Slice 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development and superpowers:verification-before-completion.

**Goal:** Move QueryEngine tool activation away from ToolRuntime-owned harness pack selection.

**Architecture:** Keep `ToolRuntime.schemas_for_mode()` and `ToolRuntime.allowed_tool_names()` as compatibility APIs for existing callers. QueryEngine should instead ask workflow extensions for active workflow tools, merge them with the mode permission contract, and request schemas for that explicit tool-name set. This keeps the default C harness pack behind `CHarnessWorkflowExtension`.

**Tech Stack:** Python 3.8, existing pytest suite, current in-process workflow extension manager.

---

## Tasks

- [x] Add regression tests proving QueryEngine does not call `ToolRuntime.schemas_for_mode()` or `ToolRuntime.allowed_tool_names()` for its active turn schema/allowed-tool calculation.
- [x] Remove harness workflow tools from `CORE_PACK`, keeping build/debug/verify packs behavior-compatible by listing harness tools explicitly in those packs.
- [x] Update `QueryEngine._allowed_tools_for_mode()` to use the mode permission contract as fallback and the extension manager for workflow tools.
- [x] Update `QueryEngine._schemas_for_mode()` to call `ToolRuntime.schemas_for(..., tool_names=...)` with the explicit active tool set.
- [x] Update docs and change log for Slice 3.
- [x] Run focused tests, ruff, and fast non-GUI regression.
