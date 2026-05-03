"""3-tier tool result caching with TTL invalidation."""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from enum import Enum
from typing import Any, Dict, Optional

from embedagent.session import Action, Observation


class CacheTier(Enum):
    L1_MEMORY = "l1_memory"
    L2_DISK = "l2_disk"
    L3_PROJECTION = "l3_projection"


class CacheEntry(object):
    def __init__(
        self,
        value: Observation,
        ttl_seconds: int,
        tier: CacheTier,
    ) -> None:
        self.value = value
        self.created_at = time.time()
        self.ttl_seconds = ttl_seconds
        self.tier = tier
        self.hit_count = 0

    def is_expired(self) -> bool:
        return time.time() > self.created_at + self.ttl_seconds


class ToolResultCache(object):
    """3-tier cache: L1 memory (fast), L2 disk (persistent), L3 projection (DB)."""

    def __init__(
        self,
        tool_result_store: Optional[Any] = None,
        max_memory_entries: int = 100,
        default_ttl_seconds: int = 300,
    ) -> None:
        self.tool_result_store = tool_result_store
        self.max_memory_entries = max_memory_entries
        self.default_ttl_seconds = default_ttl_seconds
        self._l1: Dict[str, CacheEntry] = OrderedDict()
        self._total_hits = 0

    def _hash_arguments(self, arguments: Dict[str, Any]) -> str:
        canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]

    def _cache_key(self, action: Action, session_id: str = "") -> str:
        arg_hash = self._hash_arguments(action.arguments)
        return "{}:{}:{}".format(action.name, arg_hash, session_id)

    def get(self, action: Action, session_id: str = "") -> Optional[Observation]:
        key = self._cache_key(action, session_id)

        # L1 Lookup
        entry = self._l1.get(key)
        if entry is not None:
            if not entry.is_expired():
                entry.hit_count += 1
                self._total_hits += 1
                # Move to end (most recently used)
                self._l1.move_to_end(key)
                return entry.value
            else:
                del self._l1[key]

        # L2 Lookup
        if self.tool_result_store is not None:
            l2_value = self._get_l2(key)
            if l2_value is not None:
                entry = CacheEntry(
                    value=l2_value,
                    ttl_seconds=self.default_ttl_seconds,
                    tier=CacheTier.L1_MEMORY,
                )
                self._put_l1(key, entry)
                return l2_value

        # L3 Lookup (placeholder - projection DB integration)
        # For now, L3 is not implemented as it requires projection_db integration
        return None

    def put(
        self,
        action: Action,
        observation: Observation,
        session_id: str = "",
        ttl_seconds: Optional[int] = None,
    ) -> None:
        key = self._cache_key(action, session_id)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds

        entry = CacheEntry(
            value=observation,
            ttl_seconds=ttl,
            tier=CacheTier.L1_MEMORY,
        )
        self._put_l1(key, entry)

        # L2 Store
        if self.tool_result_store is not None:
            self._put_l2(key, observation)

    def _put_l1(self, key: str, entry: CacheEntry) -> None:
        self._l1[key] = entry
        self._l1.move_to_end(key)
        # Evict oldest if over capacity
        while len(self._l1) > self.max_memory_entries:
            self._l1.popitem(last=False)

    def _get_l2(self, key: str) -> Optional[Observation]:
        if self.tool_result_store is None:
            return None
        try:
            # Use a synthetic session_id and tool_call_id for L2 storage
            field = self.tool_result_store.resolve_existing_path(
                ".embedagent/cache/{}.json".format(key)
            )
            if field:
                with open(field, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return Observation(
                    tool_name=data.get("tool_name", ""),
                    success=data.get("success", False),
                    error=data.get("error"),
                    data=data.get("data", {}),
                )
        except (ValueError, OSError, IOError):
            pass
        return None

    def _put_l2(self, key: str, observation: Observation) -> None:
        if self.tool_result_store is None:
            return
        try:
            value = {
                "tool_name": observation.tool_name,
                "success": observation.success,
                "error": observation.error,
                "data": observation.data,
            }
            self.tool_result_store.write_json(
                session_id="cache",
                tool_call_id=key,
                field_name="entry",
                value=value,
            )
        except (OSError, IOError):
            pass

    def invalidate(
        self,
        action_name: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> int:
        removed = 0
        keys_to_remove = []

        for key in list(self._l1.keys()):
            parts = key.split(":")
            if len(parts) >= 3:
                key_action = parts[0]
                key_session = parts[2]
                if action_name is not None and key_action != action_name:
                    continue
                if session_id is not None and key_session != session_id:
                    continue
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._l1[key]
            removed += 1

        return removed

    def invalidate_expired(self) -> int:
        removed = 0
        keys_to_remove = []

        for key, entry in self._l1.items():
            if entry.is_expired():
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._l1[key]
            removed += 1

        return removed

    def stats(self) -> Dict[str, int]:
        return {
            "l1_size": len(self._l1),
            "l2_size": 0,  # Would need filesystem scan
            "l3_size": 0,  # Not implemented
            "total_hits": self._total_hits,
        }
