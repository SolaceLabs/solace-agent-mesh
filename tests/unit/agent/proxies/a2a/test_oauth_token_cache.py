"""
Unit tests for OAuth 2.0 token caching with context support.

Tests the OAuth2TokenCache class to ensure that tokens are properly
cached per agent and context (agent_card vs task), with separate
cache entries for different contexts.
"""

import pytest
import time
from unittest.mock import AsyncMock, patch
from solace_agent_mesh.agent.proxies.a2a.oauth_token_cache import OAuth2TokenCache


@pytest.mark.asyncio
class TestOAuth2TokenCacheWithContext:
    """Tests for context-aware OAuth token caching."""

    async def test_separate_caches_for_different_contexts(self):
        """
        Tokens should be cached separately for different contexts.
        Agent 'foo' with context 'agent_card' should not share cache
        with agent 'foo' with context 'task'.
        """
        cache = OAuth2TokenCache()

        await cache.set("foo", "token-for-agent-card", 3600, context="agent_card")
        await cache.set("foo", "token-for-task", 3600, context="task")

        # Each context should have its own cached token
        agent_card_token = await cache.get("foo", context="agent_card")
        task_token = await cache.get("foo", context="task")

        assert agent_card_token == "token-for-agent-card"
        assert task_token == "token-for-task"
        assert agent_card_token != task_token

    async def test_default_context_is_task(self):
        """
        The default context should be 'task' for backward compatibility.
        """
        cache = OAuth2TokenCache()

        # Set token without specifying context (should default to "task")
        await cache.set("foo", "default-token", 3600)

        # Get token without specifying context (should default to "task")
        token = await cache.get("foo")

        assert token == "default-token"

        # Explicitly getting with context="task" should return the same token
        task_token = await cache.get("foo", context="task")
        assert task_token == "default-token"

    async def test_agent_card_context_separate_from_default(self):
        """
        Agent card context should be separate from the default task context.
        """
        cache = OAuth2TokenCache()

        # Set token for default context (task)
        await cache.set("foo", "task-token", 3600)

        # Set token for agent_card context
        await cache.set("foo", "card-token", 3600, context="agent_card")

        # Default get should return task token
        default_token = await cache.get("foo")
        assert default_token == "task-token"

        # Explicit agent_card get should return card token
        card_token = await cache.get("foo", context="agent_card")
        assert card_token == "card-token"

    async def test_expiration_separate_by_context(self):
        """
        Token expiration should be independent for different contexts.
        """
        cache = OAuth2TokenCache()

        # Set token for agent_card with short expiration
        await cache.set("foo", "card-token-short", 1, context="agent_card")

        # Set token for task with longer expiration
        await cache.set("foo", "task-token-long", 3600, context="task")

        # Initially both tokens should be present
        assert await cache.get("foo", context="agent_card") == "card-token-short"
        assert await cache.get("foo", context="task") == "task-token-long"

        # Wait for agent_card token to expire
        time.sleep(1.1)

        # Agent card token should be expired and removed
        assert await cache.get("foo", context="agent_card") is None

        # Task token should still be present
        assert await cache.get("foo", context="task") == "task-token-long"

    async def test_invalidate_specific_context(self):
        """
        Invalidating a token should only affect the specified context.
        """
        cache = OAuth2TokenCache()

        await cache.set("foo", "card-token", 3600, context="agent_card")
        await cache.set("foo", "task-token", 3600, context="task")

        # Invalidate only the agent_card context
        await cache.invalidate("foo", context="agent_card")

        # Agent card token should be gone
        assert await cache.get("foo", context="agent_card") is None

        # Task token should still be present
        assert await cache.get("foo", context="task") == "task-token"

    async def test_invalidate_default_context(self):
        """
        Invalidating without context should invalidate the default (task) context.
        """
        cache = OAuth2TokenCache()

        await cache.set("foo", "task-token", 3600, context="task")
        await cache.set("foo", "card-token", 3600, context="agent_card")

        # Invalidate default context (task)
        await cache.invalidate("foo")

        # Task token should be gone
        assert await cache.get("foo", context="task") is None

        # Agent card token should still be present
        assert await cache.get("foo", context="agent_card") == "card-token"

    async def test_multiple_agents_multiple_contexts(self):
        """
        Multiple agents with multiple contexts should all have separate caches.
        """
        cache = OAuth2TokenCache()

        # Set tokens for agent1 in both contexts
        await cache.set("agent1", "agent1-card", 3600, context="agent_card")
        await cache.set("agent1", "agent1-task", 3600, context="task")

        # Set tokens for agent2 in both contexts
        await cache.set("agent2", "agent2-card", 3600, context="agent_card")
        await cache.set("agent2", "agent2-task", 3600, context="task")

        # Each agent+context combination should have its own token
        assert await cache.get("agent1", context="agent_card") == "agent1-card"
        assert await cache.get("agent1", context="task") == "agent1-task"
        assert await cache.get("agent2", context="agent_card") == "agent2-card"
        assert await cache.get("agent2", context="task") == "agent2-task"

    async def test_cache_key_format(self):
        """
        Verify the cache key format is correct.
        """
        assert OAuth2TokenCache._make_cache_key("foo", "task") == "foo:task"
        assert OAuth2TokenCache._make_cache_key("foo", "agent_card") == "foo:agent_card"
        assert OAuth2TokenCache._make_cache_key("bar", "task") == "bar:task"

    async def test_get_nonexistent_context(self):
        """
        Getting a token for a context that was never set should return None.
        """
        cache = OAuth2TokenCache()

        # Set token for task context only
        await cache.set("foo", "task-token", 3600, context="task")

        # Getting for agent_card context should return None
        assert await cache.get("foo", context="agent_card") is None

    async def test_overwrite_token_in_same_context(self):
        """
        Setting a token twice for the same context should overwrite the first.
        """
        cache = OAuth2TokenCache()

        # Set initial token
        await cache.set("foo", "token-v1", 3600, context="task")
        assert await cache.get("foo", context="task") == "token-v1"

        # Overwrite with new token
        await cache.set("foo", "token-v2", 3600, context="task")
        assert await cache.get("foo", context="task") == "token-v2"
