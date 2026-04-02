"""Root pytest configuration for all SAM tests."""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def test_data_dir(project_root):
    """Return the test data directory."""
    return project_root / "tests" / "data"


@pytest.fixture(scope="session")
def default_test_timeout():
    """Default timeout for async operations in tests."""
    return 30.0
