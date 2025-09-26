"""
Registry for dynamically binding middleware implementations.

This module provides a registry system that allows middleware implementations
to be bound at runtime, enabling pluggable behavior for configuration resolution
and other middleware functions.
"""

import logging
from typing import Optional, Type, Dict, Any, List

log = logging.getLogger(__name__)

LOG_IDENTIFIER = "[MiddlewareRegistry]"


class MiddlewareRegistry:
    """
    Registry for middleware implementations that can be overridden at runtime.

    This registry allows different implementations of middleware to be bound
    dynamically, enabling extensibility and customization of system behavior.
    """

    _config_resolver: Optional[Type] = None
    _initialization_callbacks: List[callable] = []

    @classmethod
    def bind_config_resolver(cls, resolver_class: Type):
        """
        Bind a custom config resolver implementation.

        Args:
            resolver_class: Class that implements the ConfigResolver interface
        """
        cls._config_resolver = resolver_class
        log.info(
            "%s Bound custom config resolver: %s",
            LOG_IDENTIFIER,
            resolver_class.__name__,
        )

    @classmethod
    def get_config_resolver(cls) -> Type:
        """
        Get the current config resolver implementation.

        Returns:
            The bound config resolver class, or the default ConfigResolver if none bound.
        """
        if cls._config_resolver:
            return cls._config_resolver

        from .config_resolver import ConfigResolver

        return ConfigResolver

    @classmethod
    def register_initialization_callback(cls, callback: callable):
        """
        Register a callback to be called during system initialization.

        Args:
            callback: Function to call during initialization
        """
        cls._initialization_callbacks.append(callback)
        log.debug(
            "%s Registered initialization callback: %s",
            LOG_IDENTIFIER,
            callback.__name__,
        )

    @classmethod
    def initialize_middleware(cls):
        """
        Initialize all registered middleware components.

        This should be called during system startup to initialize any
        bound middleware implementations.
        """
        log.info("%s Initializing middleware components...", LOG_IDENTIFIER)

        for callback in cls._initialization_callbacks:
            try:
                callback()
                log.debug(
                    "%s Executed initialization callback: %s",
                    LOG_IDENTIFIER,
                    callback.__name__,
                )
            except Exception as e:
                log.error(
                    "%s Error executing initialization callback %s: %s",
                    LOG_IDENTIFIER,
                    callback.__name__,
                    e,
                )

        log.info("%s Middleware initialization complete.", LOG_IDENTIFIER)

    @classmethod
    def reset_bindings(cls):
        """
        Reset all bindings to defaults.

        This is useful for testing or when switching between different
        middleware configurations.
        """
        cls._config_resolver = None
        cls._initialization_callbacks = []
        log.info("%s Reset all middleware bindings", LOG_IDENTIFIER)

    @classmethod
    def get_registry_status(cls) -> Dict[str, Any]:
        """
        Get the current status of the middleware registry.

        Returns:
            Dict containing information about bound middleware implementations.
        """
        return {
            "config_resolver": (
                cls._config_resolver.__name__ if cls._config_resolver else "default"
            ),
            "initialization_callbacks": len(cls._initialization_callbacks),
            "has_custom_bindings": cls._config_resolver is not None,
        }
