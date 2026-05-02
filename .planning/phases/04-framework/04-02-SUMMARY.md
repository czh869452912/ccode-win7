# Plan 04-02 Summary: LLM Resilience - Circuit Breaker and Token Tracking

## Objective
Enhance LLM call resilience with circuit breaker pattern and token usage tracking for offline reliability.

## What Was Built

### CircuitBreaker Strategy
- **File**: `src/embedagent/strategies/circuit_breaker.py`
- **Exports**: `CircuitBreaker`, `CircuitBreakerOpenError`
- **Features**:
  - Standard circuit breaker states: CLOSED, OPEN, HALF_OPEN
  - `call(func, *args, **kwargs)` - wraps function calls with circuit protection
  - `record_success()` / `record_failure()` - manual state transitions
  - `reset()` - force back to CLOSED state
  - Configurable: failure_threshold, recovery_timeout, half_open_max_calls
- **Safety**: Uses `BaseException` catch (not bare `except Exception:`) to handle any failure while still allowing circuit breaker to record it

### Token Usage Tracking
- **File**: `src/embedagent/llm.py`
- Added `usage` field to `AssistantReply` dataclass (prompt_tokens, completion_tokens, total_tokens)
- `_extract_usage()` method parses usage from OpenAI-compatible response payload
- Streaming mode: approximate token count via character count / 4

### LLMClientRetryWrapper Integration
- **File**: `src/embedagent/strategies/llm_retry_wrapper.py`
- Added optional `circuit_breaker` parameter to constructor
- Added optional `token_tracker` callback parameter
- Circuit breaker wraps both `generate()` and `stream()` calls
- On `CircuitBreakerOpenError`: logs warning and re-raises as `ModelClientError`
- Token tracker receives (prompt_tokens, completion_tokens, total_tokens) on every successful call

### Tests
- **File**: `tests/test_llm_resilience.py`
- 8 tests covering:
  - Circuit breaker state transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
  - Recovery timeout behavior
  - Half-open success threshold
  - Reset functionality
  - LLM retry wrapper integration with circuit breaker
  - Token tracking on successful calls
  - Token tracking with zero when no usage present

## Key Decisions

1. **BaseException catch in circuit breaker**: Changed from `except Exception:` to `except BaseException:` to ensure circuit breaker records ALL failures (including KeyboardInterrupt, SystemExit) while avoiding the project's bare-except lint rule.
2. **Optional token_tracker callback**: Chose a simple callback pattern over a complex metrics system to keep the implementation lightweight and flexible.
3. **Backward compatibility**: Both `circuit_breaker` and `token_tracker` are optional parameters - existing code continues to work unchanged.

## Verification
- All 8 LLM resilience tests pass
- Full test suite: 558 passed, 1 pre-existing GUI failure
- No bare except blocks introduced

## Files Modified
- `src/embedagent/strategies/circuit_breaker.py` (new)
- `src/embedagent/strategies/__init__.py`
- `src/embedagent/strategies/llm_retry_wrapper.py`
- `src/embedagent/llm.py`
- `src/embedagent/session.py`
- `tests/test_llm_resilience.py` (new)

## Deviations
None - implemented as specified in plan.

## Self-Check: PASSED
