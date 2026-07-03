"""Tests for tool result caching."""

import time
import unittest

from embedagent.strategies.tool_cache import CacheEntry, CacheTier, ToolResultCache
from embedagent_core.session import Action, Observation


class TestToolResultCache(unittest.TestCase):
    def setUp(self):
        self.cache = ToolResultCache(max_memory_entries=100, default_ttl_seconds=300)

    def test_l1_memory_hit(self):
        action = Action(
            name="read_file", arguments={"path": "test.txt"}, call_id="1", raw_arguments={}
        )
        obs = Observation(
            tool_name="read_file", success=True, error=None, data={"content": "hello"}
        )

        self.cache.put(action, obs)
        result = self.cache.get(action)

        self.assertIsNotNone(result)
        self.assertEqual(result.data["content"], "hello")
        stats = self.cache.stats()
        self.assertEqual(stats["l1_size"], 1)
        self.assertEqual(stats["total_hits"], 1)

    def test_ttl_expiration(self):
        action = Action(
            name="read_file", arguments={"path": "test.txt"}, call_id="1", raw_arguments={}
        )
        obs = Observation(tool_name="read_file", success=True, error=None, data={})

        self.cache.put(action, obs, ttl_seconds=0)
        time.sleep(0.1)
        result = self.cache.get(action)

        self.assertIsNone(result)

    def test_invalidate_by_action_name(self):
        action1 = Action(
            name="read_file", arguments={"path": "a.txt"}, call_id="1", raw_arguments={}
        )
        action2 = Action(
            name="write_file", arguments={"path": "b.txt"}, call_id="2", raw_arguments={}
        )

        self.cache.put(
            action1, Observation(tool_name="read_file", success=True, error=None, data={})
        )
        self.cache.put(
            action2, Observation(tool_name="write_file", success=True, error=None, data={})
        )

        removed = self.cache.invalidate(action_name="read_file")
        self.assertEqual(removed, 1)
        self.assertIsNone(self.cache.get(action1))
        self.assertIsNotNone(self.cache.get(action2))

    def test_invalidate_expired(self):
        action = Action(
            name="read_file", arguments={"path": "test.txt"}, call_id="1", raw_arguments={}
        )
        self.cache.put(
            action,
            Observation(tool_name="read_file", success=True, error=None, data={}),
            ttl_seconds=0,
        )
        time.sleep(0.1)

        removed = self.cache.invalidate_expired()
        self.assertEqual(removed, 1)

    def test_lru_eviction(self):
        cache = ToolResultCache(max_memory_entries=2)
        action1 = Action(
            name="read_file", arguments={"path": "1.txt"}, call_id="1", raw_arguments={}
        )
        action2 = Action(
            name="read_file", arguments={"path": "2.txt"}, call_id="2", raw_arguments={}
        )
        action3 = Action(
            name="read_file", arguments={"path": "3.txt"}, call_id="3", raw_arguments={}
        )

        cache.put(
            action1, Observation(tool_name="read_file", success=True, error=None, data={"n": 1})
        )
        cache.put(
            action2, Observation(tool_name="read_file", success=True, error=None, data={"n": 2})
        )
        cache.put(
            action3, Observation(tool_name="read_file", success=True, error=None, data={"n": 3})
        )

        self.assertIsNone(cache.get(action1))  # Evicted
        self.assertIsNotNone(cache.get(action2))
        self.assertIsNotNone(cache.get(action3))

    def test_stats(self):
        action = Action(
            name="read_file", arguments={"path": "test.txt"}, call_id="1", raw_arguments={}
        )
        self.cache.put(
            action, Observation(tool_name="read_file", success=True, error=None, data={})
        )
        self.cache.get(action)

        stats = self.cache.stats()
        self.assertEqual(stats["l1_size"], 1)
        self.assertEqual(stats["total_hits"], 1)

    def test_stats_only_reports_implemented_tiers(self):
        stats = self.cache.stats()
        self.assertEqual(set(stats.keys()), {"l1_size", "l2_size", "total_hits"})
        self.assertFalse(hasattr(CacheTier, "L3_PROJECTION"))


class TestCacheEntry(unittest.TestCase):
    def test_expiration(self):
        entry = CacheEntry(
            value=Observation(tool_name="test", success=True, error=None, data={}),
            ttl_seconds=0,
            tier=CacheTier.L1_MEMORY,
        )
        time.sleep(0.1)
        self.assertTrue(entry.is_expired())

    def test_not_expired(self):
        entry = CacheEntry(
            value=Observation(tool_name="test", success=True, error=None, data={}),
            ttl_seconds=3600,
            tier=CacheTier.L1_MEMORY,
        )
        self.assertFalse(entry.is_expired())


if __name__ == "__main__":
    unittest.main()
