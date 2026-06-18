# Pi-Style Agent Loop Continuation Design

## Goal

Replace the current product-facing `max_turns=8` loop ceiling with a Pi-style continuation model while keeping Agent Core minimal.

The low-level `AgentLoop` should behave like Pi's loop: it repeatedly runs provider sampling, assistant message recording, tool execution, turn-end handling, and next-turn decision until an explicit stop condition is reached. A fixed numeric turn ceiling remains only as a fallback safety fuse, not as the main product behavior.

This design also absorbs a narrow set of Codex ideas that already fit EmbedAgent's architecture: token/context-driven compaction checks, explicit interrupt and pending-input semantics, and output/context budgeting at the tool/context boundary.

## Current Baseline

EmbedAgent currently has a hard loop ceiling in the core path:

- `src/embedagent/agent_loop.py` defaults `max_turns` to `8`.
- `AgentLoop.run()` uses `for turn_index in range(self.max_turns)`.
- When the loop reaches the ceiling, it records a `LoopTransition` with reason `max_turns`.
- `QueryEngine` and `InProcessAdapter` also default to `max_turns=8` and project that value into session/frontend metadata.

This is useful as a dead-loop guard, but it is too blunt as the default continuation contract. It can stop legitimate long-running C/C++ work after eight model/tool cycles even when the model is making progress, compaction is available, and the workflow has not reached a natural stop point.

The current architecture already has the right supporting pieces:

- `AgentLoop` owns turn-loop orchestration.
- `AgentLifecycleJournal` records transitions and operation lifecycle events.
- `ContextManager` can perform pre-provider compaction when context approaches the threshold.
- Reactive compact retry is already supported after provider context-limit errors.
- `LoopGuard` already handles repeated tool calls and repeated failures.
- Pending permission and user-input interactions already suspend and resume through the core action pipeline.

The design should reuse these boundaries rather than add a new orchestration layer.

## Reference Findings

### Pi

Pi's low-level `agent-loop.ts` does not use a fixed default max-turn product limit. It runs an open loop and delegates continuation decisions to narrow callbacks:

- `shouldStopAfterTurn`
- `prepareNextTurn`
- `getSteeringMessages`
- `getFollowUpMessages`
- tool result `terminate`
- `transformContext`

The core loop stays small. It knows the order of execution, but not the product policy for how long a task should continue. Context transforms, queued user input, follow-up delivery, graceful stop, and next-turn model/context replacement are configuration hooks.

This is the primary design to mirror.

### Codex

Codex does not use a simple fixed eight-step loop either. Its turn loop continues while the model needs follow-up, pending input exists, or compaction starts a new context window. It checks token status before sampling and after sampling, and it runs auto-compaction when context limits are reached.

The Codex ideas worth absorbing are structural, not broad product features:

- pre-turn and mid-turn context budget checks;
- compaction as a continuation action rather than a terminal failure;
- explicit pending input and interruption semantics;
- output truncation as a tool/context responsibility;
- token-budget diagnostics that explain why continuation stopped or compacted.

The design must not import Codex's heavier control-plane concepts into Agent Core.

## Product Principles

1. Match Pi's continuation architecture first.
2. Keep `AgentLoop` as a small execution loop, not a workflow policy engine.
3. Treat fixed turn limits as fallback safety fuses, not primary task budgets.
4. Keep C/C++ workflow behavior behind the workflow extension boundary.
5. Keep compaction and context budgeting in the context layer.
6. Keep tool output budgeting in the tool/result projection layer.
7. Keep permission, user-input, abort, guard-stop, and operation lifecycle ownership in the existing core services.
8. Preserve Windows 7, offline deployment, Python 3.8 syntax, and the current dependency surface.
9. Do not introduce remote services, online control planes, public plugin marketplaces, or general multi-agent orchestration.

## Scope

### In Scope

- Replace the `for range(max_turns)` loop shape with a Pi-style open continuation loop.
- Introduce a narrow continuation policy interface owned by Agent Core.
- Add default continuation behavior equivalent to the current successful product path.
- Preserve `LoopGuard` as the repeated-action and repeated-failure safety mechanism.
- Preserve `max_turns` as a legacy/configurable fallback safety limit.
- Record explicit transition metadata when the fallback safety limit stops a run.
- Allow next-turn preparation to request context compaction or context rebuild without adding workflow-specific policy to `AgentLoop`.
- Keep existing pending interaction suspend/resume behavior.
- Update focused tests for completion, tool continuation, guard stop, fallback safety limit, compaction continuation, and pending interaction behavior.
- Update active architecture docs after implementation.

### Out Of Scope

- Removing `max_turns` configuration in the first slice.
- Replacing `ContextManager`.
- Replacing `LoopGuard`.
- Moving C/C++ workflow state out of `CHarnessWorkflowExtension`.
- Changing permission policy semantics.
- Changing the frontend protocol except for optional diagnostic naming after implementation.
- Adding Pi's full runtime, Codex's remote thread control plane, or any online dependency.
- Adding multi-agent orchestration to Agent Core.
- Adding new runtime dependencies.

## Recommended Approach

Use a minimal `AgentLoopContinuationPolicy` that mirrors Pi's callbacks but fits EmbedAgent's Python core.

The loop should ask the policy at turn boundaries what to do next. The policy can return one of a small set of decisions:

- `continue`: start another provider request with the current context path.
- `stop`: record a terminal transition and return.
- `compact_then_continue`: run the existing compaction/context rebuild path, then continue.
- `wait`: return an existing pending interaction result.
- `abort`: record an interrupted transition and return.

The default policy should be intentionally thin:

- Stop when the model has no tool calls and completion detection says the turn is complete.
- Continue after tool results when the model still needs a follow-up provider request.
- Defer repeated-tool and repeated-failure safety to `LoopGuard`.
- Defer context threshold handling to `ContextManager` and existing compact-boundary recording.
- Use the fallback safety limit only after natural continuation logic fails to stop.

This mirrors Pi's shape without forcing Pi's TypeScript API names directly into Python public API.

## Design Options

### Option A: Increase `max_turns`

Raise the default from `8` to a larger number.

Pros:

- Smallest code change.
- Keeps current tests mostly unchanged.

Cons:

- Does not match Pi.
- Still treats a numeric ceiling as product behavior.
- Merely delays premature cutoff.
- Does not clarify why the loop continues or stops.

This option is rejected.

### Option B: Pi-Style Continuation Policy

Add a small policy interface and convert `AgentLoop.run()` to an open loop with explicit continuation decisions.

Pros:

- Closest match to Pi.
- Keeps Agent Core small.
- Converts `max_turns` into a real safety fuse.
- Makes compaction and pending-input continuation explicit.
- Preserves current extension, permission, context, and lifecycle boundaries.

Cons:

- Requires focused migration tests.
- Requires compatibility mapping for existing `max_turns` transition projections.

This is the recommended option.

### Option C: Codex-Style Turn Context Runtime

Introduce a richer turn runtime object with token status, compaction phase, pending input, model session, environment state, and continuation logic in one large structure.

Pros:

- Codex's model is powerful and battle-tested for large hosted workflows.
- Token and compaction state become very explicit.

Cons:

- Too heavy for the current EmbedAgent core.
- Risks duplicating existing `TurnSnapshot`, `RuntimeConfigReducer`, `CompactionStateReducer`, and `AgentLifecycleJournal` responsibilities.
- Would thicken Agent Core instead of making it more Pi-like.

This option is rejected for the current product direction.

## Architecture

### AgentLoop

`AgentLoop` remains the loop owner. Its job is to:

1. start an agent step;
2. build context;
3. call the provider;
4. record assistant messages and tool calls;
5. execute tools;
6. record observations and transitions;
7. ask the continuation policy what happens next.

It should not decide workflow-specific budgets, C/C++ phase progress, or frontend behavior.

### Continuation Policy

The continuation policy is an internal Agent Core boundary. It receives safe, already-available loop facts:

- current mode;
- workflow state name;
- step index;
- latest assistant reply;
- tool observations summary;
- whether a pending interaction was created;
- whether context was compacted;
- whether the fallback safety limit has been reached;
- stop event state.

It returns a decision object with:

- `kind`;
- `reason`;
- `message`;
- optional transition metadata;
- optional next-mode hint if an existing path already supports it.

The first implementation can live close to `AgentLoop` to avoid over-abstracting. If it grows, it can move to a small `agent_loop_continuation.py` module.

### QueryEngine

`QueryEngine` constructs the default continuation policy and passes it to `AgentLoop`. It does not regain ownership of the loop body.

Existing callbacks for context building, provider calls, compaction retry, compact-boundary recording, action execution, and transition recording remain where they are.

### Context And Compaction

Context selection remains owned by `ContextManager`.

The continuation policy may request `compact_then_continue`, but the actual summary generation, compact-boundary persistence, token diagnostics, and context rebuild continue to flow through existing context and lifecycle services.

Codex-inspired pre-turn and mid-turn token checks should be expressed through the current context pipeline and compact-boundary metadata, not by adding a second context truth source.

### Fallback Safety Limit

The old `max_turns` value becomes a safety limit. For compatibility:

- configuration may still accept `max_turns`;
- frontend/session metadata may still expose `max_turns` during the transition;
- existing `max_turns` terminal reason can remain as a compatibility alias;
- new code should prefer a clearer internal name such as `loop_safety_limit`.

The safety limit should stop only when the loop has not naturally stopped by policy, guard, abort, pending interaction, or completion.

## Data Flow

1. User turn enters `QueryEngine`.
2. `AgentKernel` opens the turn frame.
3. `AgentLoop` starts step 1.
4. `ContextManager` assembles context and may compact before the provider call.
5. `TurnSnapshot` freezes the provider request input.
6. Provider returns an assistant reply.
7. `AgentLoop` records assistant message and tool calls.
8. `AgentToolActionService` executes tools through permission and extension hooks.
9. `LoopGuard` records tool behavior.
10. `AgentLoop` emits `turn_end`-equivalent internal facts to the continuation policy.
11. The policy returns `stop`, `continue`, `compact_then_continue`, `wait`, or `abort`.
12. `AgentLifecycleJournal` records the resulting transition or save point.

## Error Handling

- Provider context-limit errors continue to use reactive compact retry.
- Failed compaction records the existing error/interrupted path and does not loop indefinitely.
- Repeated failed tools continue to stop through `LoopGuard`.
- Stop events abort at the next safe boundary.
- Pending permission and user input return the existing pending interaction result.
- The fallback safety limit records a diagnostic transition with step count and active policy metadata.

## Testing

Focused tests should cover:

- a no-tool assistant response stops normally;
- assistant tool calls continue into a follow-up provider request;
- repeated tool calls still guard-stop;
- repeated failures still guard-stop;
- fallback safety limit still stops a pathological loop;
- context-limit provider error still compacts once and retries;
- pre-provider threshold compaction still records a compact boundary;
- pending permission and user-input interactions still suspend and resume;
- `QueryEngine` still delegates loop ownership to `AgentLoop`;
- Python 3.8 syntax compatibility.

Existing frontend tests that assert `max_turns` projection can remain initially, but new tests should target `loop_safety_limit` semantics once the protocol wording is updated.

## Migration Plan

1. Add the internal continuation decision type and default policy.
2. Convert `AgentLoop.run()` from `for range(max_turns)` to an open loop with policy decisions.
3. Preserve the old safety-limit behavior behind the policy.
4. Add focused unit tests around policy decisions and loop behavior.
5. Update `QueryEngine` construction without moving loop orchestration back into `QueryEngine`.
6. Update diagnostics and docs to describe `max_turns` as a compatibility name for the safety limit.
7. In a later cleanup, consider renaming config and frontend labels from `max_turns` to `loop_safety_limit`.

## Documentation Updates After Implementation

The implementation slice should update:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`
- `docs/frontend-protocol.md` if projected naming changes

This design doc remains slice-local until the implementation lands and durable conclusions are synchronized into active source-of-truth docs.

## Success Criteria

- The default hosted C/C++ workflow no longer stops merely because eight model/tool cycles were used.
- Pathological loops still stop deterministically.
- The core loop is closer to Pi's open-loop plus callback-policy shape.
- Codex-inspired token and compaction behavior is used only where it fits existing context boundaries.
- Agent Core remains workflow-neutral and small.
- No new runtime dependency, online service, Docker, WSL, VS Code, runtime Node, or Windows 8+ requirement is introduced.
