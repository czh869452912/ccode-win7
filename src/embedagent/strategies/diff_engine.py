"""Multi-search-replace diff engine with fuzzy matching."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


class DiffError(Exception):
    """Raised for unrecoverable diff errors."""
    pass


@dataclass
class DiffBlock:
    old_text: str
    new_text: str
    expected_start_line: Optional[int] = None
    fuzzy: bool = True


class MultiSearchReplaceDiffEngine(object):
    """Applies multiple search-replace blocks with fuzzy matching support."""

    def __init__(self, fuzzy_threshold: float = 0.85) -> None:
        self.fuzzy_threshold = fuzzy_threshold

    def apply_diff(
        self, content: str, blocks: List[DiffBlock]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Apply diff blocks to content.

        Returns (updated_content, results) where results is a list of dicts
        with block_index, status, line_number, message.
        """
        results = []
        working_content = content

        # Validate no overlap
        overlap_errors = self._validate_no_overlap(blocks, content)
        if overlap_errors:
            # Add overlap errors for affected blocks
            for error in overlap_errors:
                results.append({
                    "block_index": 0,
                    "status": "failed",
                    "line_number": 0,
                    "message": error,
                })
            return working_content, results

        # Sort blocks by expected_start_line if provided, otherwise by first occurrence
        sorted_blocks = self._sort_blocks(blocks, working_content)

        for block_index, block in sorted_blocks:
            match = self._find_match(working_content, block)
            if match is not None:
                start_pos, end_pos = match
                line_number = self._line_number(working_content, start_pos)
                working_content = (
                    working_content[:start_pos]
                    + block.new_text
                    + working_content[end_pos:]
                )
                results.append({
                    "block_index": block_index,
                    "status": "applied",
                    "line_number": line_number,
                    "message": "",
                })
            else:
                results.append({
                    "block_index": block_index,
                    "status": "failed",
                    "line_number": 0,
                    "message": "未找到匹配文本",
                })

        return working_content, results

    def preview_diff(
        self, content: str, blocks: List[DiffBlock]
    ) -> List[Dict[str, Any]]:
        """Preview diff results without modifying content."""
        _, results = self.apply_diff(content, blocks)
        return results

    def _find_match(
        self, content: str, block: DiffBlock
    ) -> Optional[Tuple[int, int]]:
        if not block.old_text:
            return None

        # Exact match
        exact_pos = content.find(block.old_text)
        if exact_pos != -1:
            # Check if unique or use expected_start_line
            occurrences = []
            start = 0
            while True:
                pos = content.find(block.old_text, start)
                if pos == -1:
                    break
                occurrences.append(pos)
                start = pos + 1

            if len(occurrences) == 1:
                return (occurrences[0], occurrences[0] + len(block.old_text))

            # Multiple occurrences - use expected_start_line to disambiguate
            if block.expected_start_line is not None:
                for pos in occurrences:
                    line_num = self._line_number(content, pos)
                    if line_num == block.expected_start_line:
                        return (pos, pos + len(block.old_text))

            # Default to first occurrence
            return (occurrences[0], occurrences[0] + len(block.old_text))

        # Fuzzy match
        if block.fuzzy:
            normalized_old = self._normalize_whitespace(block.old_text)
            if not normalized_old:
                return None

            # Find candidate regions using line-based matching
            best_match = None
            best_ratio = 0.0

            content_lines = content.split("\n")
            old_lines = block.old_text.split("\n")
            num_old_lines = len(old_lines)

            for i in range(len(content_lines)):
                candidate_lines = content_lines[i : i + num_old_lines]
                candidate_text = "\n".join(candidate_lines)
                normalized_candidate = self._normalize_whitespace(candidate_text)

                if normalized_candidate and normalized_old:
                    ratio = difflib.SequenceMatcher(
                        None, normalized_candidate, normalized_old
                    ).ratio()
                    if ratio > best_ratio and ratio >= self.fuzzy_threshold:
                        best_ratio = ratio
                        start_pos = sum(len(line) + 1 for line in content_lines[:i])
                        end_pos = start_pos + len(candidate_text)
                        best_match = (start_pos, end_pos)

            return best_match

        return None

    def _validate_no_overlap(
        self, blocks: List[DiffBlock], content: str
    ) -> List[str]:
        """Check that replacement regions don't overlap."""
        regions = []
        for i, block in enumerate(blocks):
            match = self._find_match(content, block)
            if match is not None:
                regions.append((match[0], match[1], i))

        errors = []
        for i in range(len(regions)):
            for j in range(i + 1, len(regions)):
                start1, end1, idx1 = regions[i]
                start2, end2, idx2 = regions[j]
                # Check overlap
                if start1 < end2 and start2 < end1:
                    errors.append(
                        "Block {} 和 Block {} 的替换区域重叠".format(idx1, idx2)
                    )

        return errors

    def _sort_blocks(
        self, blocks: List[DiffBlock], content: str
    ) -> List[Tuple[int, DiffBlock]]:
        """Sort blocks by position in content (descending to avoid index shifts)."""
        indexed = []
        for i, block in enumerate(blocks):
            match = self._find_match(content, block)
            if match is not None:
                indexed.append((i, block, match[0]))
            else:
                # Put non-matching blocks at the end
                indexed.append((i, block, -1))

        # Sort by position descending (apply from end to start)
        indexed.sort(key=lambda x: x[2], reverse=True)
        return [(i, block) for i, block, _ in indexed]

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """Collapse multiple whitespace chars to single space, strip."""
        import re
        return re.sub(r"\s+", " ", text.strip())

    @staticmethod
    def _line_number(content: str, position: int) -> int:
        """Compute 0-indexed line number from character position."""
        return content[:position].count("\n")
