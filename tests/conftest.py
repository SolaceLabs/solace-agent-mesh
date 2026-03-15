import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--db-type",
        action="store",
        default=None,
        help="Restrict integration tests to a single database type: sqlite, postgresql, or mysql",
    )