"""Tests for LLM resilience: circuit breaker and token tracking."""

import time
import unittest
from unittest.mock import Mock

from embedagent.llm import ModelClientError
from embedagent.session import AssistantReply
from embedagent.strategies.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from embedagent.strategies.llm_retry_wrapper import LLMClientRetryWrapper


class TestCircuitBreaker(unittest.TestCase):
    def test_starts_closed(self):
        cb = CircuitBreaker()
        self.assertEqual(cb.state, "CLOSED")

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        self.assertEqual(cb.state, "OPEN")
        with self.assertRaises(CircuitBreakerOpenError):
            cb.call(lambda: "ok")

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        self.assertEqual(cb.state, "OPEN")
        time.sleep(0.2)
        result = cb.call(lambda: "ok")
        self.assertEqual(result, "ok")
        self.assertEqual(cb.state, "HALF_OPEN")

    def test_closes_after_half_open_successes(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1, half_open_max_calls=2)
        cb.record_failure()
        time.sleep(0.2)
        cb.call(lambda: "ok")
        cb.call(lambda: "ok")
        self.assertEqual(cb.state, "CLOSED")

    def test_resets_to_closed(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        self.assertEqual(cb.state, "OPEN")
        cb.reset()
        self.assertEqual(cb.state, "CLOSED")
        self.assertEqual(cb.failure_count, 0)


class TestLLMResilienceIntegration(unittest.TestCase):
    def test_retry_wrapper_uses_circuit_breaker(self):
        mock_client = Mock()
        mock_client.generate.side_effect = ModelClientError("HTTP 500")
        
        cb = CircuitBreaker(failure_threshold=1)
        wrapper = LLMClientRetryWrapper(mock_client, circuit_breaker=cb)
        
        # First call should retry then fail
        with self.assertRaises(ModelClientError):
            wrapper.call_with_retry([{"role": "user", "content": "hi"}], [])
        
        # Second call should trigger circuit breaker
        with self.assertRaises(ModelClientError) as ctx:
            wrapper.call_with_retry([{"role": "user", "content": "hi"}], [])
        self.assertIn("circuit breaker open", str(ctx.exception).lower())

    def test_token_tracking_on_success(self):
        mock_client = Mock()
        mock_client.generate.return_value = AssistantReply(
            content="hello",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )
        
        tokens = []
        tracker = lambda p, c, t: tokens.append((p, c, t))
        wrapper = LLMClientRetryWrapper(mock_client, token_tracker=tracker)
        
        reply = wrapper.call_with_retry([{"role": "user", "content": "hi"}], [])
        self.assertEqual(reply.content, "hello")
        self.assertEqual(tokens, [(10, 5, 15)])

    def test_token_tracking_zero_when_no_usage(self):
        mock_client = Mock()
        mock_client.generate.return_value = AssistantReply(
            content="hello",
            usage={},
        )
        
        tokens = []
        tracker = lambda p, c, t: tokens.append((p, c, t))
        wrapper = LLMClientRetryWrapper(mock_client, token_tracker=tracker)
        
        reply = wrapper.call_with_retry([{"role": "user", "content": "hi"}], [])
        self.assertEqual(tokens, [(0, 0, 0)])


if __name__ == "__main__":
    unittest.main()
