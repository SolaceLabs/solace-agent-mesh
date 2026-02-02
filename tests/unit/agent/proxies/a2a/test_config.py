"""Unit tests for A2A proxy configuration models."""

from solace_agent_mesh.agent.proxies.a2a.config import (
    A2AProxiedAgentConfig,
    A2AProxyAppConfig,
)


class TestA2AProxiedAgentConfigSSLVerify:
    """Tests for the ssl_verify configuration option."""

    def test_ssl_verify_defaults_to_true(self):
        """ssl_verify should default to True when not specified."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com/agent",
        )
        assert config.ssl_verify is True

    def test_ssl_verify_can_be_set_to_false(self):
        """ssl_verify can be explicitly set to False."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com/agent",
            ssl_verify=False,
        )
        assert config.ssl_verify is False

    def test_ssl_verify_can_be_set_to_true(self):
        """ssl_verify can be explicitly set to True."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com/agent",
            ssl_verify=True,
        )
        assert config.ssl_verify is True

    def test_ssl_verify_with_http_url(self):
        """ssl_verify setting is accepted even with HTTP URLs."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="http://localhost:8080/agent",
            ssl_verify=False,
        )
        assert config.ssl_verify is False

    def test_ssl_verify_in_full_config(self):
        """ssl_verify works alongside other configuration options."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com/agent",
            ssl_verify=False,
            request_timeout_seconds=120,
            use_auth_for_agent_card=True,
        )
        assert config.ssl_verify is False
        assert config.request_timeout_seconds == 120
        assert config.use_auth_for_agent_card is True


class TestA2AProxyAppConfigSSLVerify:
    """Tests for ssl_verify in the full app configuration."""

    def test_proxied_agent_with_ssl_verify_false(self):
        """Full app config can include agents with ssl_verify=False."""
        config = A2AProxyAppConfig(
            namespace="test/namespace",
            proxied_agents=[
                {
                    "name": "secure-agent",
                    "url": "https://secure.example.com/agent",
                    "ssl_verify": True,
                },
                {
                    "name": "self-signed-agent",
                    "url": "https://self-signed.example.com/agent",
                    "ssl_verify": False,
                },
            ],
        )
        assert len(config.proxied_agents) == 2
        assert config.proxied_agents[0].ssl_verify is True
        assert config.proxied_agents[1].ssl_verify is False

    def test_proxied_agent_ssl_verify_defaults(self):
        """Agents without ssl_verify specified should default to True."""
        config = A2AProxyAppConfig(
            namespace="test/namespace",
            proxied_agents=[
                {
                    "name": "default-agent",
                    "url": "https://example.com/agent",
                },
            ],
        )
        assert config.proxied_agents[0].ssl_verify is True
