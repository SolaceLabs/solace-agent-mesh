"""
Registry for dynamically binding middleware implementations.

This module provides a registry system that allows middleware implementations
to be bound at runtime, enabling pluggable behavior for configuration resolution
and other middleware functions.
"""

import logging
from typing import Optional, Type, Dict, Any, List, Callable

log = logging.getLogger(__name__)

LOG_IDENTIFIER = "[MiddlewareRegistry]"


class MiddlewareRegistry:
    """
    Registry for middleware implementations that can be overridden at runtime.

    This registry allows different implementations of middleware to be bound
    dynamically, enabling extensibility and customization of system behavior.
    """

    _config_resolver: Optional[Type] = None
    _resource_sharing_service: Optional[Type] = None
    _initialization_callbacks: List[callable] = []
    _post_migration_hooks: List[Callable[[str], None]] = []

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
    def bind_resource_sharing_service(cls, service_class: Type):
        """
        Bind a custom resource sharing service implementation.

        Args:
            service_class: Class that implements the ResourceSharingService interface
        """
        cls._resource_sharing_service = service_class
        log.info(
            "%s Bound custom resource sharing service: %s",
            LOG_IDENTIFIER,
            service_class.__name__,
        )

    @classmethod
    def get_resource_sharing_service(cls) -> Type:
        """
        Get the current resource sharing service implementation.

        Returns:
            The bound resource sharing service class, or the default DefaultResourceSharingService if none bound.
        """
        if cls._resource_sharing_service:
            return cls._resource_sharing_service

        from ..services.default_resource_sharing_service import DefaultResourceSharingService

        return DefaultResourceSharingService

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
    def initialize_middleware(cls, app_config: Optional[Dict[str, Any]] = None):
        """
        Initialize all registered middleware components.

        This should be called during system startup to initialize any
        bound middleware implementations.

        Args:
            app_config: Optional application configuration to pass to callbacks
        """
        log.info("%s Initializing middleware components...", LOG_IDENTIFIER)

        for callback in cls._initialization_callbacks:
            try:
                # Try calling with app_config, fall back to no args for backwards compatibility
                try:
                    callback(app_config)
                except TypeError:
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
    def register_post_migration_hook(cls, hook: Callable[[str], None]):
        """
        Register a hook to be called after community database migrations complete.

        This allows enterprise/plugin packages to run their own migrations without
        the community code being aware of them. Hooks receive the database URL
        as a parameter.

        Args:
            hook: Callable that takes database_url (str) and runs migrations
        """
        cls._post_migration_hooks.append(hook)
        log.info(
            "%s Registered post-migration hook: %s",
            LOG_IDENTIFIER,
            getattr(hook, '__name__', repr(hook)),
        )

    @classmethod
    def run_post_migration_hooks(cls, database_url: str):
        """
        Execute all registered post-migration hooks.

        Called by community code after its migrations complete. Enterprise/plugin
        packages can register hooks to run their own migrations.

        Args:
            database_url: Database URL to pass to hooks
        """
        if not cls._post_migration_hooks:
            log.debug("%s No post-migration hooks registered", LOG_IDENTIFIER)
            return

        log.info(
            "%s Running %d post-migration hook(s)...",
            LOG_IDENTIFIER,
            len(cls._post_migration_hooks),
        )

        for hook in cls._post_migration_hooks:
            hook_name = getattr(hook, '__name__', repr(hook))
            try:
                log.info("%s Executing post-migration hook: %s", LOG_IDENTIFIER, hook_name)
                hook(database_url)
                log.info("%s Post-migration hook completed: %s", LOG_IDENTIFIER, hook_name)
            except Exception as e:
                log.error(
                    "%s Error executing post-migration hook %s: %s",
                    LOG_IDENTIFIER,
                    hook_name,
                    e,
                )
                log.exception("%s Full traceback:", LOG_IDENTIFIER)
                raise

    @classmethod
    def reset_bindings(cls):
        """
        Reset all bindings to defaults.

        This is useful for testing or when switching between different
        middleware configurations.
        """
        cls._config_resolver = None
        cls._resource_sharing_service = None
        cls._initialization_callbacks = []
        cls._post_migration_hooks = []
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
            "resource_sharing_service": (
                cls._resource_sharing_service.__name__ if cls._resource_sharing_service else "default"
            ),
            "initialization_callbacks": len(cls._initialization_callbacks),
            "post_migration_hooks": len(cls._post_migration_hooks),
            "has_custom_bindings": cls._config_resolver is not None or cls._resource_sharing_service is not None,
        }
