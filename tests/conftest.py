"""
Root conftest.py - Global pytest hooks and configuration.

This file contains hooks that run for ALL tests across the entire test suite.
"""

import os
import sys

import pytest


_pytest_exit_status = 0


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    """Capture exit status for use in pytest_unconfigure.

    Uses trylast=True so this runs AFTER the terminal reporter prints the
    test summary line.
    """
    global _pytest_exit_status
    _pytest_exit_status = exitstatus


def pytest_unconfigure(config):
    """Force-exit after pytest completes to prevent hanging.

    Integration test fixtures (SolaceAiConnector, TestLLMServer) can leave
    background threads or atexit handlers that prevent the process from exiting.
    Since pytest_unconfigure is the last hook, everything important (test
    results, summary, coverage) has already been written — safe to force-exit.
    """
    sys.stdout.flush()
    sys.stderr.flush()
    _emergency_cleanup_postgresql()
    os._exit(_pytest_exit_status)


def _emergency_cleanup_postgresql():
    """Stop PostgreSQL testcontainers before os._exit() bypasses normal teardown."""
    import importlib

    for module_path in [
        "tests.integration.apis.platform.conftest",
        "tests.integration.apis.conftest",
    ]:
        try:
            mod = importlib.import_module(module_path)
            container = getattr(mod, "_postgres_container", None)
            if container:
                container.stop()
        except Exception:
            pass
