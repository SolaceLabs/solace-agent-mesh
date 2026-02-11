"""Unit tests for MiddlewareRegistry post-migration hooks (without integration fixtures)."""
import pytest
from solace_agent_mesh.common.middleware.registry import MiddlewareRegistry


class TestPostMigrationHooks:
    """Test post-migration hooks in MiddlewareRegistry."""

    def setup_method(self):
        """Reset registry before each test."""
        MiddlewareRegistry.reset_bindings()

    def teardown_method(self):
        """Reset registry after each test."""
        MiddlewareRegistry.reset_bindings()

    def test_register_post_migration_hook_stores_hook(self):
        """Test that register_post_migration_hook stores the hook."""

        def sample_hook(database_url: str):
            pass

        MiddlewareRegistry.register_post_migration_hook(sample_hook)

        # Verify hook is registered (access private attribute for testing)
        assert sample_hook in MiddlewareRegistry._post_migration_hooks
        assert len(MiddlewareRegistry._post_migration_hooks) == 1

    def test_register_multiple_post_migration_hooks(self):
        """Test that multiple hooks can be registered."""

        def hook1(database_url: str):
            pass

        def hook2(database_url: str):
            pass

        def hook3(database_url: str):
            pass

        MiddlewareRegistry.register_post_migration_hook(hook1)
        MiddlewareRegistry.register_post_migration_hook(hook2)
        MiddlewareRegistry.register_post_migration_hook(hook3)

        assert len(MiddlewareRegistry._post_migration_hooks) == 3
        assert hook1 in MiddlewareRegistry._post_migration_hooks
        assert hook2 in MiddlewareRegistry._post_migration_hooks
        assert hook3 in MiddlewareRegistry._post_migration_hooks

    def test_run_post_migration_hooks_executes_hooks_with_database_url(self):
        """Test that run_post_migration_hooks executes all registered hooks."""
        executed_urls = []

        def tracking_hook(database_url: str):
            executed_urls.append(database_url)

        MiddlewareRegistry.register_post_migration_hook(tracking_hook)

        test_url = "sqlite:///test.db"
        MiddlewareRegistry.run_post_migration_hooks(test_url)

        assert len(executed_urls) == 1
        assert executed_urls[0] == test_url

    def test_run_post_migration_hooks_executes_multiple_hooks_in_order(self):
        """Test that multiple hooks are executed in registration order."""
        execution_order = []

        def hook1(database_url: str):
            execution_order.append("hook1")

        def hook2(database_url: str):
            execution_order.append("hook2")

        def hook3(database_url: str):
            execution_order.append("hook3")

        MiddlewareRegistry.register_post_migration_hook(hook1)
        MiddlewareRegistry.register_post_migration_hook(hook2)
        MiddlewareRegistry.register_post_migration_hook(hook3)

        MiddlewareRegistry.run_post_migration_hooks("sqlite:///test.db")

        assert execution_order == ["hook1", "hook2", "hook3"]

    def test_run_post_migration_hooks_raises_on_hook_failure(self):
        """Test that failing hook raises exception and stops execution."""

        def failing_hook(database_url: str):
            raise RuntimeError("Migration failed!")

        MiddlewareRegistry.register_post_migration_hook(failing_hook)

        with pytest.raises(RuntimeError, match="Migration failed!"):
            MiddlewareRegistry.run_post_migration_hooks("sqlite:///test.db")

    def test_run_post_migration_hooks_stops_on_first_failure(self):
        """Test that hook execution stops on first failure."""
        execution_order = []

        def hook1(database_url: str):
            execution_order.append("hook1")

        def failing_hook(database_url: str):
            execution_order.append("failing")
            raise RuntimeError("Hook 2 failed!")

        def hook3(database_url: str):
            execution_order.append("hook3")  # Should not execute

        MiddlewareRegistry.register_post_migration_hook(hook1)
        MiddlewareRegistry.register_post_migration_hook(failing_hook)
        MiddlewareRegistry.register_post_migration_hook(hook3)

        with pytest.raises(RuntimeError, match="Hook 2 failed!"):
            MiddlewareRegistry.run_post_migration_hooks("sqlite:///test.db")

        # Verify only first two hooks executed
        assert execution_order == ["hook1", "failing"]
        assert "hook3" not in execution_order

    def test_reset_bindings_clears_post_migration_hooks(self):
        """Test that reset_bindings clears all post-migration hooks."""

        def hook1(database_url: str):
            pass

        def hook2(database_url: str):
            pass

        MiddlewareRegistry.register_post_migration_hook(hook1)
        MiddlewareRegistry.register_post_migration_hook(hook2)
        assert len(MiddlewareRegistry._post_migration_hooks) == 2

        MiddlewareRegistry.reset_bindings()

        assert len(MiddlewareRegistry._post_migration_hooks) == 0

    def test_get_registry_status_includes_post_migration_hooks_count(self):
        """Test that get_registry_status includes post_migration_hooks count."""

        def hook1(database_url: str):
            pass

        def hook2(database_url: str):
            pass

        MiddlewareRegistry.register_post_migration_hook(hook1)
        MiddlewareRegistry.register_post_migration_hook(hook2)

        status = MiddlewareRegistry.get_registry_status()

        assert "post_migration_hooks" in status
        assert status["post_migration_hooks"] == 2

    def test_get_registry_status_shows_zero_hooks_when_none_registered(self):
        """Test that get_registry_status shows 0 when no hooks registered."""
        status = MiddlewareRegistry.get_registry_status()

        assert "post_migration_hooks" in status
        assert status["post_migration_hooks"] == 0

    def test_run_post_migration_hooks_with_no_hooks_registered(self):
        """Test that run_post_migration_hooks succeeds when no hooks registered."""
        # Should not raise any exceptions
        MiddlewareRegistry.run_post_migration_hooks("sqlite:///test.db")
