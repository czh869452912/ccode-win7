"""Tests for the manual dependency injection container."""
from __future__ import annotations

import pytest

from embedagent.di_container import DIContainer, get_default_container


class TestDIContainer(object):
    """Characterization tests for DIContainer behavior."""

    def test_register_and_resolve(self):
        """register_factory stores factory; resolve returns correct value."""
        container = DIContainer()
        container.register_factory("test_key", lambda: 42)
        result = container.resolve("test_key")
        assert result == 42

    def test_singleton_caching(self):
        """resolve twice without fresh=True returns same object."""
        container = DIContainer()
        container.register_factory("obj", lambda: {"count": 0})
        first = container.resolve("obj")
        second = container.resolve("obj")
        assert first is second
        first["count"] = 1
        assert second["count"] == 1

    def test_fresh_bypasses_cache(self):
        """resolve with fresh=True returns new object each time."""
        container = DIContainer()
        container.register_factory("obj", lambda: {"count": 0})
        first = container.resolve("obj", fresh=True)
        second = container.resolve("obj", fresh=True)
        assert first is not second
        first["count"] = 1
        assert second["count"] == 0

    def test_clear_removes_singletons(self):
        """clear removes cached singletons; next resolve gets fresh instance."""
        container = DIContainer()
        container.register_factory("obj", lambda: {"count": 0})
        first = container.resolve("obj")
        first["count"] = 1
        container.clear()
        second = container.resolve("obj")
        assert second is not first
        assert second["count"] == 0

    def test_missing_factory_raises_keyerror(self):
        """resolve on unregistered key raises KeyError."""
        container = DIContainer()
        with pytest.raises(KeyError) as exc_info:
            container.resolve("missing")
        assert "missing" in str(exc_info.value)


class TestDefaultContainer(object):
    """Tests for the global default container instance."""

    def test_default_container_is_singleton(self):
        """get_default_container returns same instance on repeated calls."""
        c1 = get_default_container()
        c2 = get_default_container()
        assert c1 is c2

    def test_default_container_is_di_container(self):
        """get_default_container returns a DIContainer instance."""
        container = get_default_container()
        assert isinstance(container, DIContainer)
