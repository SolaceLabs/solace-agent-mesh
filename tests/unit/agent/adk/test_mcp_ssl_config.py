"""Tests for MCP SSL configuration."""

import tempfile
import os

import httpx
import pytest

from solace_agent_mesh.agent.adk.mcp_ssl_config import (
    SslConfig,
    create_ssl_httpx_client_factory,
)


class TestSslConfig:
    """Tests for SslConfig dataclass."""

    def test_default_values(self):
        """Test that default values are correct."""
        config = SslConfig()
        assert config.verify is True
        assert config.ca_bundle is None

    def test_verify_false(self):
        """Test creating config with verification disabled."""
        config = SslConfig(verify=False)
        assert config.verify is False
        assert config.ca_bundle is None

    def test_ca_bundle_with_valid_path(self):
        """Test creating config with a valid CA bundle path."""
        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as f:
            f.write(b"-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")
            temp_path = f.name

        try:
            config = SslConfig(ca_bundle=temp_path)
            assert config.verify is True
            assert config.ca_bundle == temp_path
        finally:
            os.unlink(temp_path)

    def test_ca_bundle_with_nonexistent_path_raises_error(self):
        """Test that a non-existent CA bundle path raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            SslConfig(ca_bundle="/nonexistent/path/to/cert.pem")

        assert "does not exist or is not a file" in str(exc_info.value)

    def test_ca_bundle_with_directory_path_raises_error(self):
        """Test that a directory path for CA bundle raises ValueError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError) as exc_info:
                SslConfig(ca_bundle=temp_dir)

            assert "does not exist or is not a file" in str(exc_info.value)


class TestCreateSslHttpxClientFactory:
    """Tests for create_ssl_httpx_client_factory function."""

    def test_factory_returns_callable(self):
        """Test that the factory function returns a callable."""
        config = SslConfig()
        factory = create_ssl_httpx_client_factory(config)
        assert callable(factory)

    def test_factory_creates_async_client(self):
        """Test that the factory creates an httpx.AsyncClient."""
        config = SslConfig()
        factory = create_ssl_httpx_client_factory(config)
        client = factory()

        assert isinstance(client, httpx.AsyncClient)

    def test_factory_with_verify_true(self):
        """Test that verify=True is passed to the client."""
        config = SslConfig(verify=True)
        factory = create_ssl_httpx_client_factory(config)
        client = factory()

        # httpx stores verify setting in _transport._pool._ssl_context or similar
        # We can check the _verify attribute that was passed during construction
        assert client._transport._pool._ssl_context is not None

    def test_factory_with_verify_false(self):
        """Test that verify=False creates a client successfully."""
        config = SslConfig(verify=False)
        factory = create_ssl_httpx_client_factory(config)
        client = factory()

        # Client should be created successfully with verify=False
        assert isinstance(client, httpx.AsyncClient)

    def test_factory_with_ca_bundle(self):
        """Test that CA bundle path is used for verification."""
        import certifi

        # Use the real certifi CA bundle for this test
        ca_bundle_path = certifi.where()
        config = SslConfig(ca_bundle=ca_bundle_path)
        factory = create_ssl_httpx_client_factory(config)
        client = factory()

        assert isinstance(client, httpx.AsyncClient)
        # Verify SSL context was created (meaning CA bundle was loaded)
        assert client._transport._pool._ssl_context is not None

    def test_factory_passes_headers(self):
        """Test that headers are passed to the client."""
        config = SslConfig()
        factory = create_ssl_httpx_client_factory(config)
        headers = {"Authorization": "Bearer test-token"}
        client = factory(headers=headers)

        assert client.headers["Authorization"] == "Bearer test-token"

    def test_factory_passes_timeout(self):
        """Test that custom timeout is passed to the client."""
        config = SslConfig()
        factory = create_ssl_httpx_client_factory(config)
        custom_timeout = httpx.Timeout(60.0, read=120.0)
        client = factory(timeout=custom_timeout)

        assert client.timeout.connect == 60.0
        assert client.timeout.read == 120.0

    def test_factory_uses_default_timeout_when_none(self):
        """Test that default MCP timeout is used when none provided."""
        config = SslConfig()
        factory = create_ssl_httpx_client_factory(config)
        client = factory()

        # Default MCP timeouts: 30.0 connect, 300.0 read
        assert client.timeout.connect == 30.0
        assert client.timeout.read == 300.0

    def test_factory_enables_follow_redirects(self):
        """Test that follow_redirects is enabled (MCP default)."""
        config = SslConfig()
        factory = create_ssl_httpx_client_factory(config)
        client = factory()

        assert client.follow_redirects is True
