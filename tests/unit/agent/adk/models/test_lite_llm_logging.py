"""
When imported, LiteLLM configures custom logging handler and formatter.
This is bad practice for libraries since logging is an application concern and libraries that set handlers/formatters is likely to conflict with the application's logging configuration.

At initialization, we remove litellm's handlers but keep propagate=True on litellm's loggers so that litellm logs still flow to the main application's log handlers/formatters.
"""

import logging

from solace_agent_mesh.agent.adk.models.lite_llm import LiteLlm


class TestLiteLlmLoggingHandlerCleanup:
    """Test that LiteLlm properly cleans up litellm's logging handlers after initialization."""

    def test_litellm_loggers_cleaned_after_init(self):
        """
        Test that after LiteLlm initialization, all litellm loggers have:
        - propagate=True (to pass logs to parent handlers)
        - No handlers (handlers list is empty)

        This prevents duplicate logs and ensures litellm uses the main application's log handlers & formatters.
        """
        # The 4 litellm loggers we expect to be cleaned
        # There is a risk that these logger names change in future litellm versions
        litellm_logger_names = [
            "LiteLLM",
            "LiteLLM Proxy",
            "LiteLLM Router",
            "litellm"
        ]

        # Initialize LiteLlm - we expect litellm handler to be cleared
        LiteLlm(model="test-model")

        # Verify each litellm logger is properly configured
        for logger_name in litellm_logger_names:
            logger = logging.getLogger(logger_name)

            assert logger.propagate is True, (
                f"{logger_name} should have propagate=True so that logs flow to parent handlers"
            )

            # Assert no handlers are set (preventing duplicate logs)
            assert len(logger.handlers) == 0, (
                f"{logger_name} should have no handlers after init, but has {len(logger.handlers)}: "
                f"{[type(h).__name__ for h in logger.handlers]}"
            )
