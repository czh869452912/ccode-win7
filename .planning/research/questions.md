# Research Questions

## RQ-001: Reference Engineering UI/UX and Harness Pattern Deep-Dive

**Status:** In Progress  
**Created:** 2026-05-03  
**Context:** GUI & Harness design evaluation discussion

### Scope

Systematically analyze the following reference projects to understand their UI/UX patterns, conversation flow structure, tool invocation display modes, session management mechanisms, and alignment strategies for EmbedAgent:

- **claude-code** (`reference/claude-code/`): TUI-based agent coding experience
- **codex** (`reference/codex/`): App-based agent coding experience  
- **opencode** (`reference/opencode/`): CLI/TUI agent experience
- **superpowers** (`reference/superpowers/`): Workflow execution patterns
- **get-shit-done** (`reference/get-shit-done/`): Task orchestration patterns
- **OpenHands** (`reference/OpenHands/`): Multi-agent orchestration (for anti-patterns)
- **Roo-Code** (`reference/Roo-Code/`): VS Code extension agent experience

### Key Questions to Answer

1. **Conversation Flow Structure**
   - How do reference projects display user messages vs agent responses?
   - How are tool calls / tool results presented inline in the conversation?
   - Is there a concept of "step" or "turn" visible to the user? If so, how is it styled?
   - How is streaming/real-time output handled?

2. **Tool Invocation UX**
   - How are file reads displayed? (inline snippet? expandable card?)
   - How are file edits displayed? (diff view? before/after?)
   - How are shell commands / build recipes displayed? (collapsible output?)
   - How does the user approve or reject tool calls?

3. **Session & State Management**
   - How is session state persisted?
   - How is conversation history reconstructed on resume?
   - Is there a concept of "mode" or "workflow"? How is it surfaced to the user?
   - How are long-running tasks handled? (progress indicators? background execution?)

4. **Mode/Workflow Design**
   - Do reference projects have fixed mode-based workflows (like our explore/spec/build/debug/verify)?
   - Or is workflow entirely driven by user intent?
   - How do they handle "the user just said hi but we're in build mode"?

5. **Termination Strategy**
   - Do reference projects have a fixed step/turn limit?
   - How do they know when to stop vs continue?
   - How do they handle "the agent is going in circles"?

6. **Layout & Information Architecture**
   - What is the primary layout? (sidebar + chat? full-screen chat? panels?)
   - What lives in the sidebar vs the main chat area?
   - How is file tree / workspace status presented?
   - How are tasks/goals tracked and displayed?

### Deliverables

- `RESEARCH.md` with structured findings per project
- Comparative analysis matrix
- Recommended alignment strategy for EmbedAgent
- Specific UI component patterns to adopt

### Anti-Patterns to Identify

- Things reference projects do that we should **not** copy
- Over-engineering or unnecessary complexity
- Patterns that violate our constraints (Win7 compatibility, offline-only)
