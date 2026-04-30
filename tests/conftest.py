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
