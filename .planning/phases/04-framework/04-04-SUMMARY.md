# Plan 04-04 Summary: Multi-Search-Replace Diff Engine

## Objective
Implement multi-search-replace diff tool with fuzzy matching for reliable code editing, achieving >95% success rate.

## What Was Built

### MultiSearchReplaceDiffEngine
- **File**: `src/embedagent/strategies/diff_engine.py`
- **Exports**: `MultiSearchReplaceDiffEngine`, `DiffBlock`, `DiffError`
- **Features**:
  - `apply_diff(content, blocks)` - Apply multiple search-replace blocks
  - `preview_diff(content, blocks)` - Preview results without modifying content
  - Exact matching with disambiguation via `expected_start_line`
  - Fuzzy matching using `difflib.SequenceMatcher` (default threshold 0.85)
  - Overlapping block detection and rejection
  - Partial application support (some blocks can fail while others succeed)
  - Sorts blocks by position (descending) to avoid index shifting issues

### DiffBlock Dataclass
- `old_text` - Text to search for
- `new_text` - Replacement text
- `expected_start_line` - Optional line number for disambiguation
- `fuzzy` - Enable fuzzy matching (default True)

### edit_file Tool Integration
- **File**: `src/embedagent/tools/file_ops.py`
- Backward compatible: single `old_text`/`new_text` still works
- New `blocks` parameter for multi-block operations
- Each block supports `old_text`, `new_text`, `expected_start_line`, `fuzzy`
- Failed blocks reported individually in error message

### Tests
- **File**: `tests/test_diff_engine.py`
- 10 tests covering:
  - Single exact match replacement
  - Multiple blocks applied in sequence
  - Fuzzy matching with whitespace variations
  - Expected start line disambiguation
  - Overlapping blocks rejection
  - Partial failure recording
  - Empty old_text rejection
  - Preview mode (no content modification)
  - 20 realistic code editing scenarios (100% success rate)
  - Backward compatibility verification

## Key Decisions

1. **Descending position sort**: Blocks are applied from end to start to prevent index shifting from affecting subsequent matches.
2. **Whitespace normalization for fuzzy matching**: Collapses multiple whitespace chars to single space before computing similarity ratio.
3. **Line-based fuzzy candidates**: Scans content line-by-line to find candidate regions matching the number of lines in old_text.

## Verification
- All 10 diff engine tests pass
- Realistic scenario success rate: 100% (20/20)
- Full test suite: 558 passed, 1 pre-existing GUI failure

## Files Modified
- `src/embedagent/strategies/diff_engine.py` (new)
- `src/embedagent/strategies/__init__.py`
- `src/embedagent/tools/file_ops.py`
- `tests/test_diff_engine.py` (new)

## Deviations
None - implemented as specified in plan.

## Self-Check: PASSED
