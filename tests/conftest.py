"""Root pytest configuration for all SAM tests."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


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

