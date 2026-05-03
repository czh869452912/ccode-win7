# Roadmap: EmbedAgent

## Milestones

- **v0.1 Compile Environment + Framework** — Phases 1-4 (shipped 2026-05-02) — [Details](milestones/v0.1-ROADMAP.md)
- **v0.2 GUI & Harness Experience Refactor** — Phases 5-7 (active 2026-05-03)

## Phases

### v0.1 — SHIPPED 2026-05-02

<details>
<summary>v0.1 Compile Environment + Framework (Phases 1-4) — SHIPPED 2026-05-02</summary>

- [x] Phase 1: Foundation (3/3 plans) — completed 2026-05-02
- [x] Phase 2: Compile Environment (4/4 plans) — completed 2026-05-02
- [x] Phase 3: Architecture (4/4 plans) — completed 2026-05-02
- [x] Phase 4: Framework (5/5 plans) — completed 2026-05-02

</details>

### v0.2 — ACTIVE 2026-05-03

**Goal:** Transform user experience to match industry-leading agent coding tools by refactoring session persistence, conversation flow, and mode execution.

- [ ] Phase 5: Session Infrastructure (4 tasks)
- [ ] Phase 6: GUI Experience (3 tasks)
- [ ] Phase 7: Harness Refactor (3 tasks)

---

## Phase Details

### Phase 5: Session Infrastructure

**Goal:** Establish reliable, inspectable, and recoverable session persistence with modern transcript format and flat conversation model.

**Requirements:** SESS-01, SESS-02, SESS-03, SESS-04, SESS-05

**Success Criteria:**
1. New sessions write schema_version=2 JSONL transcript with typed messages
2. Session restore skips corrupted records and continues (best_effort mode)
3. History assembler produces flat items[] array consumable by frontend
4. All existing tests pass; new integration tests cover end-to-end persistence
5. Old schema_version=1 transcripts remain readable

**Plans:**
- [x] Plan 05-01: Transcript format upgrade (schema_version=2, typed messages, parentUuid chain) → `05-01-PLAN.md`
- [x] Plan 05-02: Session restore fault tolerance (best_effort mode, skip corrupted records) → `05-02-PLAN.md` ✅ **COMPLETE** — `05-02-SUMMARY.md`
- [ ] Plan 05-03: History assembler flat timeline (items[] output, backward compatibility) → `05-03-PLAN.md`
- [ ] Plan 05-04: Integration validation (end-to-end tests, performance tests, fault injection) → `05-04-PLAN.md`

### Phase 6: GUI Experience

**Goal:** Redesign conversation UI for inline tool display, inline diff preview, real-time streaming, and conversation-first layout.

**Requirements:** GUI-01, GUI-02, GUI-03, GUI-04

**Success Criteria:**
1. Tool calls display as inline cards with lifecycle status indicators
2. File edits show inline diff with line numbers, gutter markers, and syntax highlighting
3. Long-running commands stream output in real-time
4. Main chat area dominates layout; auxiliary panels minimized
5. Dark/light theme adaptive for diff and code blocks

**Plans:**
- Plan 06-01: Timeline flat rendering (remove nested step panels, inline tool cards)
- Plan 06-02: DiffView upgrade (line numbers, gutter markers, syntax highlighting, theme adaptive)
- Plan 06-03: Real-time streaming updates (item.updated events, command output streaming)

### Phase 7: Harness Refactor

**Goal:** Refactor mode and execution model to be permission-contract-based, intent-driven, and free of arbitrary step limits.

**Requirements:** HARN-01, HARN-02, HARN-03, HARN-04

**Success Criteria:**
1. Entering build/debug mode and saying "hi" produces normal chat, no workflow trigger
2. Task graph generated only on explicit work requests
3. Agent outputs completion signal; no fixed max_turns enforced
4. Guard detects runaway loops (repeated tool calls, consecutive failures)
5. All mode tests updated; harness tests cover new behavior

**Plans:**
- Plan 07-01: Mode permission contract (remove fixed tracks, intent-driven workflow)
- Plan 07-02: Completion signal mechanism (agent self-assessment, system recognition)
- Plan 07-03: Guard-based safety (consecutive mistake limit, loop detection, user override)

---

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v0.1 | 3/3 | Complete | 2026-05-02 |
| 2. Compile Environment | v0.1 | 4/4 | Complete | 2026-05-02 |
| 3. Architecture | v0.1 | 4/4 | Complete | 2026-05-02 |
| 4. Framework | v0.1 | 5/5 | Complete | 2026-05-02 |
| 5. Session Infrastructure | v0.2 | 1/4 complete | In Progress | 2026-05-03 |
| 6. GUI Experience | v0.2 | 0/3 | Pending | — |
| 7. Harness Refactor | v0.2 | 0/3 | Pending | — |

---

*Roadmap last updated: 2026-05-03 after v0.2 milestone initialization*
