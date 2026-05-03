from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root():
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def fixtures_dir(project_root):
    return project_root / "tests" / "fixtures"


@pytest.fixture(scope="session")
def src_dir(project_root):
    return project_root / "src" / "embedagent"


@pytest.fixture
def fresh_container(monkeypatch):
    """Provide an isolated DI container for a single test.

    Automatically clears singletons before and after the test.
    """
    from embedagent.di_container import DIContainer, get_default_container

    container = DIContainer()
    # Re-register all factories from default container
    default = get_default_container()
    for key, factory in default._factories.items():
        container.register_factory(key, factory)

    # Patch get_default_container to return our isolated container
    monkeypatch.setattr(
        "embedagent.di_container._default_container",
        container,
    )
    container.clear()
    yield container
    container.clear()


@pytest.fixture
def mock_session_store():
    """Mock SessionSummaryStore for tests."""
    from unittest.mock import MagicMock

    return MagicMock()


@pytest.fixture
def mock_timeline_store():
    from unittest.mock import MagicMock

    return MagicMock()


@pytest.fixture
def mock_transcript_store():
    from unittest.mock import MagicMock

    return MagicMock()
