"""Tests verifying elimination of global mutable state.

These tests ensure that refactored modules use factory functions
instead of module-level mutable globals, enabling test isolation.
"""
from __future__ import annotations

import pytest

from embedagent.di_container import DIContainer, get_default_container


class TestModeRegistryIsolation(object):
    """Tests for modes.py global state elimination."""

    def test_mode_registry_isolated(self):
        """get_mode_registry(fresh=True) returns empty dict."""
        from embedagent.modes import get_mode_registry

        registry = get_mode_registry(fresh=True)
        assert registry == {}
        assert isinstance(registry, dict)

    def test_initialize_modes_does_not_mutate_global(self):
        """initialize_modes with explicit registry does not affect global."""
        from embedagent.modes import initialize_modes, get_mode_registry

        # Ensure global has built-in modes
        global_registry = get_mode_registry()
        original_count = len(global_registry)
        assert original_count > 0

        # Call with explicit empty registry
        local_registry = initialize_modes(registry={})
        # initialize_modes populates the passed registry with built-ins
        assert "explore" in local_registry
        assert "build" in local_registry

        # Global unchanged
        global_after = get_mode_registry()
        assert len(global_after) == original_count

    def test_mode_names_uses_registry(self):
        """mode_names() reads from container/registry."""
        from embedagent.modes import mode_names

        names = mode_names()
        assert isinstance(names, list)
        assert "explore" in names
        assert "build" in names
        assert "spec" in names

    def test_require_mode_reads_from_registry(self):
        """require_mode() reads from container/registry."""
        from embedagent.modes import require_mode

        mode = require_mode("explore")
        assert mode["slug"] == "explore"
        assert "allowed_tools" in mode


class TestCommandSanitizerIsolation(object):
    """Tests for command_sanitizer.py global state elimination."""

    def test_sanitizer_singleton_by_default(self):
        """get_command_sanitizer() returns same instance by default."""
        from embedagent.command_sanitizer import get_command_sanitizer

        s1 = get_command_sanitizer()
        s2 = get_command_sanitizer()
        assert s1 is s2

    def test_sanitizer_fresh_returns_new(self):
        """get_command_sanitizer(fresh=True) returns different instance."""
        from embedagent.command_sanitizer import get_command_sanitizer

        s1 = get_command_sanitizer(fresh=True)
        s2 = get_command_sanitizer(fresh=True)
        assert s1 is not s2

    def test_sanitizer_functional(self):
        """Sanitizer still blocks denied commands via factory."""
        from embedagent.command_sanitizer import get_command_sanitizer

        sanitizer = get_command_sanitizer(fresh=True)
        blocked, reason = sanitizer.is_blocked("rm -rf /")
        assert blocked is True
        assert "rm" in reason


class TestInProcessAdapterIsolation(object):
    """Tests for core/adapter.py global state elimination."""

    def test_adapter_singleton_by_default(self):
        """get_inprocess_adapter() returns same instance by default."""
        from embedagent.core.adapter import get_inprocess_adapter

        # This returns the class, not an instance
        a1 = get_inprocess_adapter()
        a2 = get_inprocess_adapter()
        assert a1 is a2

    def test_adapter_fresh_returns_class(self):
        """get_inprocess_adapter(fresh=True) returns the InProcessAdapter class."""
        from embedagent.core.adapter import get_inprocess_adapter
        from embedagent.inprocess_adapter import InProcessAdapter

        a1 = get_inprocess_adapter(fresh=True)
        a2 = get_inprocess_adapter(fresh=True)
        # Both return the class itself (classes are singletons in Python)
        assert a1 is InProcessAdapter
        assert a2 is InProcessAdapter
        assert a1 is a2


class TestContainerIntegration(object):
    """Integration tests for container wiring."""

    def test_container_isolated_registries(self):
        """Fresh container can have custom registry without affecting default."""
        container = DIContainer()
        container.register_factory("mode_registry", lambda: {"custom": {}})

        custom_registry = container.resolve("mode_registry")
        assert "custom" in custom_registry

        # Default container unaffected
        default = get_default_container()
        default_registry = default.resolve("mode_registry")
        assert "explore" in default_registry
        assert "custom" not in default_registry
