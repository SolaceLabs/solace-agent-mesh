"""Test utilities for SAM feature flag overrides."""

import os
from contextlib import contextmanager


@contextmanager
def mock_flags(**flags: bool):
    """Temporarily override specific feature flags for test isolation.

    Sets ``SAM_FEATURE_<KEY>`` env vars for the duration of the context so
    that ``FeatureChecker`` returns the overridden values at the highest
    evaluation priority.  All flags not listed keep their normal values.

    The feature system must be initialised before entering the context so
    that flags are registered and env-var overrides are picked up correctly.

    Usage::

        from sam_test_infrastructure.feature_flags import mock_flags

        with mock_flags(mentions=True, project_sharing=False):
            response = api_client.get("/api/v1/config/features")
    """
    env_overrides = {
        f"SAM_FEATURE_{k.upper()}": "true" if v else "false"
        for k, v in flags.items()
    }
    previous = {key: os.environ.get(key) for key in env_overrides}
    try:
        os.environ.update(env_overrides)
        yield
    finally:
        for key, prev_val in previous.items():
            if prev_val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev_val
