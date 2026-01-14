"""
Unit tests for SAM access token utilities.

Tests cover:
- claim_mapping.extract_token_claims
- sam_token_helpers.is_sam_token_enabled
- sam_token_helpers.prepare_and_mint_sam_token
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from solace_agent_mesh.gateway.http_sse.utils.claim_mapping import (
    SAM_TOKEN_EXCLUDED_CLAIMS,
    SAM_TOKEN_INCLUDED_CLAIMS,
    extract_token_claims,
)
from solace_agent_mesh.gateway.http_sse.utils.sam_token_helpers import (
    SamTokenResult,
    is_sam_token_enabled,
    prepare_and_mint_sam_token,
)


class TestExtractTokenClaims:
    """Tests for extract_token_claims function."""

    def test_extracts_scalar_claims(self):
        """Test that scalar claims are extracted correctly."""
        user_claims = {
            "sub": "user-id-123",
            "email": "user@example.com",
            "name": "John Doe",
            "department": "Engineering",
        }

        result = extract_token_claims(user_claims)

        assert result["sub"] == "user-id-123"
        assert result["email"] == "user@example.com"
        assert result["name"] == "John Doe"
        assert result["department"] == "Engineering"

    def test_excludes_array_claims(self):
        """Test that array claims are excluded."""
        user_claims = {
            "email": "user@example.com",
            "groups": ["group1", "group2", "group3"],
            "wids": ["role-template-1"],
            "amr": ["pwd", "mfa"],
        }

        result = extract_token_claims(user_claims)

        assert "email" in result
        assert "groups" not in result
        assert "wids" not in result
        assert "amr" not in result

    def test_excludes_object_claims(self):
        """Test that object claims are excluded."""
        user_claims = {
            "email": "user@example.com",
            "nested_object": {"key": "value"},
            "custom_data": {"foo": "bar"},
        }

        result = extract_token_claims(user_claims)

        assert "email" in result
        assert "nested_object" not in result
        assert "custom_data" not in result

    def test_excludes_blocklisted_claims(self):
        """Test that blocklisted claims are never included even if in allow list."""
        user_claims = {
            "sub": "user-id-123",
            "email": "user@example.com",
            "iss": "evil-issuer",  # Should never be copied from id_token
            "roles": ["admin"],  # Should be set by gateway, not copied
            "scopes": ["read", "write"],  # Never in token
        }

        result = extract_token_claims(user_claims)

        assert result.get("sub") == "user-id-123"
        assert result.get("email") == "user@example.com"
        assert "iss" not in result
        assert "roles" not in result
        assert "scopes" not in result

    def test_handles_missing_claims_gracefully(self):
        """Test that missing claims don't cause errors."""
        user_claims = {"sub": "user-id-123"}

        result = extract_token_claims(user_claims)

        assert result == {"sub": "user-id-123"}
        # Other claims should not be in result at all
        assert "email" not in result
        assert "name" not in result

    def test_handles_none_values(self):
        """Test that None values are excluded."""
        user_claims = {
            "sub": "user-id-123",
            "email": None,
            "name": "John Doe",
        }

        result = extract_token_claims(user_claims)

        assert result["sub"] == "user-id-123"
        assert result["name"] == "John Doe"
        assert "email" not in result

    def test_handles_empty_claims(self):
        """Test that empty claims dict returns empty result."""
        result = extract_token_claims({})
        assert result == {}

    def test_custom_included_claims(self):
        """Test using custom included claims list."""
        user_claims = {
            "sub": "user-id-123",
            "email": "user@example.com",
            "custom_claim": "custom_value",
        }

        result = extract_token_claims(user_claims, included_claims=("custom_claim",))

        assert result == {"custom_claim": "custom_value"}
        assert "sub" not in result
        assert "email" not in result

    def test_includes_boolean_and_numeric_values(self):
        """Test that boolean and numeric values are included."""
        user_claims = {
            "sub": "user-id-123",
            "email_verified": True,
            "login_count": 42,
            "score": 99.5,
        }

        # These claims need to be in the included list or we won't find them
        result = extract_token_claims(
            user_claims, included_claims=("sub", "email_verified", "login_count", "score")
        )

        assert result["sub"] == "user-id-123"
        assert result["email_verified"] is True
        assert result["login_count"] == 42
        assert result["score"] == 99.5


class TestIsSamTokenEnabled:
    """Tests for is_sam_token_enabled function.

    Update 14 architecture: sam_access_token config is at gateway level,
    accessed via component.get_config("sam_access_token") which returns dict.
    """

    def test_returns_true_when_enabled(self):
        """Test returns True when feature is enabled."""
        component = MagicMock()
        # Gateway-level sam_access_token config (Update 14) - get_config returns dict
        component.get_config = MagicMock(return_value={"enabled": True})
        # Trust manager still needed for signing
        component.trust_manager = MagicMock()

        assert is_sam_token_enabled(component) is True

    def test_returns_false_when_disabled(self):
        """Test returns False when feature is disabled."""
        component = MagicMock()
        component.get_config = MagicMock(return_value={"enabled": False})
        component.trust_manager = MagicMock()

        assert is_sam_token_enabled(component) is False

    def test_returns_false_when_no_trust_manager(self):
        """Test returns False when trust_manager is None (needed for signing)."""
        component = MagicMock()
        component.get_config = MagicMock(return_value={"enabled": True})
        component.trust_manager = None

        assert is_sam_token_enabled(component) is False

    def test_returns_false_when_no_trust_manager_attr(self):
        """Test returns False when trust_manager attribute doesn't exist."""
        component = MagicMock(spec=["get_config"])
        component.get_config = MagicMock(return_value={"enabled": True})

        assert is_sam_token_enabled(component) is False

    def test_returns_false_when_no_config_attr(self):
        """Test returns False when get_config method is missing."""
        component = MagicMock(spec=["trust_manager"])
        component.trust_manager = MagicMock()

        assert is_sam_token_enabled(component) is False

    def test_returns_false_when_no_sam_access_token_config(self):
        """Test returns False when sam_access_token config section is missing."""
        component = MagicMock()
        component.get_config = MagicMock(return_value=None)  # Returns None when not configured
        component.trust_manager = MagicMock()

        assert is_sam_token_enabled(component) is False


class TestSamTokenResult:
    """Tests for SamTokenResult dataclass."""

    def test_success_when_token_present(self):
        """Test success property returns True when token is present."""
        result = SamTokenResult(token="some_token", user_identity="user@example.com")
        assert result.success is True

    def test_not_success_when_token_none(self):
        """Test success property returns False when token is None."""
        result = SamTokenResult(token=None, reason="some_reason")
        assert result.success is False

    def test_default_roles_is_empty_list(self):
        """Test that roles defaults to empty list."""
        result = SamTokenResult()
        assert result.roles == []

    def test_roles_preserved_when_set(self):
        """Test that roles are preserved when explicitly set."""
        result = SamTokenResult(roles=["admin", "user"])
        assert result.roles == ["admin", "user"]


class TestPrepareAndMintSamToken:
    """Tests for prepare_and_mint_sam_token function.

    Update 14 architecture: sam_access_token config is at gateway level.
    Config path: component.get_config("sam_access_token") returns dict.
    Trust manager is only used for signing (sign_sam_access_token).
    """

    @pytest.fixture
    def mock_component(self):
        """Create a mock component with config, trust_manager and authorization_service."""
        component = MagicMock()
        component.gateway_id = "test-gateway"
        component.log_identifier = "[test]"

        # Gateway-level sam_access_token config (Update 14) - accessed via get_config()
        component.get_config = MagicMock(
            return_value={"enabled": True, "ttl_seconds": 3600}
        )

        # Trust manager for signing only
        component.trust_manager = MagicMock()
        component.trust_manager.sign_sam_access_token = MagicMock(
            return_value="mocked_jwt_token"
        )

        # Authorization service (passed as parameter to prepare_and_mint_sam_token)
        # Not used directly from component

        return component

    @pytest.fixture
    def user_claims(self):
        """Sample user claims from id_token."""
        return {
            "sub": "user-id-123",
            "email": "user@example.com",
            "name": "John Doe",
            "department": "Engineering",
            "groups": ["group1", "group2"],  # Should not be in token
        }

    @pytest.mark.asyncio
    async def test_returns_none_when_feature_disabled(self, user_claims):
        """Test that function returns None when feature is disabled."""
        component = MagicMock()
        # Gateway-level config with feature disabled (get_config returns dict)
        component.get_config = MagicMock(return_value={"enabled": False})
        component.trust_manager = MagicMock()

        result = await prepare_and_mint_sam_token(
            component, user_claims, "azure", "test"
        )

        assert result.success is False
        assert result.token is None
        assert result.reason == "feature_disabled"

    @pytest.mark.asyncio
    async def test_returns_none_when_user_claims_missing(self, mock_component):
        """Test graceful degradation when user_claims is None."""
        result = await prepare_and_mint_sam_token(mock_component, None, "azure", "test")

        assert result.success is False
        assert result.token is None
        assert result.reason == "missing_user_claims"

    @pytest.mark.asyncio
    async def test_returns_none_when_user_identity_missing(self, mock_component):
        """Test graceful degradation when no email or sub in claims."""
        user_claims = {"name": "Test User"}  # No email or sub

        result = await prepare_and_mint_sam_token(
            mock_component, user_claims, "azure", "test"
        )

        assert result.success is False
        assert result.token is None
        assert result.reason == "missing_user_identity"

    @pytest.mark.asyncio
    async def test_returns_none_when_role_resolution_fails(
        self, mock_component, user_claims
    ):
        """Test graceful degradation when role resolution fails."""
        # Create mock authorization service that throws error
        mock_auth_service = AsyncMock()
        mock_auth_service.get_roles_for_user.side_effect = Exception("Database error")

        result = await prepare_and_mint_sam_token(
            mock_component,
            user_claims,
            "azure",
            "test",
            authorization_service=mock_auth_service,
        )

        assert result.success is False
        assert result.token is None
        assert "role_resolution_failed" in result.reason
        assert result.user_identity == "user@example.com"

    @pytest.mark.asyncio
    async def test_returns_none_when_minting_fails(self, mock_component, user_claims):
        """Test graceful degradation when trust_manager.sign fails."""
        # Create mock authorization service
        mock_auth_service = AsyncMock()
        mock_auth_service.get_roles_for_user = AsyncMock(
            return_value=["user", "developer"]
        )

        mock_component.trust_manager.sign_sam_access_token.side_effect = Exception(
            "Signing error"
        )

        result = await prepare_and_mint_sam_token(
            mock_component,
            user_claims,
            "azure",
            "test",
            authorization_service=mock_auth_service,
        )

        assert result.success is False
        assert result.token is None
        assert "minting_failed" in result.reason
        assert result.user_identity == "user@example.com"
        assert result.roles == ["user", "developer"]  # Roles were resolved

    @pytest.mark.asyncio
    async def test_successful_minting(self, mock_component, user_claims):
        """Test successful token minting."""
        # Create mock authorization service
        mock_auth_service = AsyncMock()
        mock_auth_service.get_roles_for_user = AsyncMock(
            return_value=["user", "developer"]
        )

        result = await prepare_and_mint_sam_token(
            mock_component,
            user_claims,
            "azure",
            "test",
            authorization_service=mock_auth_service,
        )

        assert result.success is True
        assert result.token == "mocked_jwt_token"
        assert result.user_identity == "user@example.com"
        assert result.roles == ["user", "developer"]

    @pytest.mark.asyncio
    async def test_jwt_payload_structure(self, mock_component, user_claims):
        """Test that minted JWT has correct payload structure."""
        # Create mock authorization service
        mock_auth_service = AsyncMock()
        mock_auth_service.get_roles_for_user = AsyncMock(
            return_value=["user", "developer"]
        )

        await prepare_and_mint_sam_token(
            mock_component,
            user_claims,
            "azure",
            "test",
            authorization_service=mock_auth_service,
        )

        # Get the custom_claims dict that was passed to sign_sam_access_token
        call_args = mock_component.trust_manager.sign_sam_access_token.call_args
        user_identity_arg = call_args[1]["user_identity"]
        custom_claims = call_args[1]["custom_claims"]
        ttl_seconds = call_args[1]["ttl_seconds"]

        # Verify user_identity parameter
        assert user_identity_arg == "user@example.com"

        # Verify TTL
        assert ttl_seconds == 3600

        # Authorization claims
        assert custom_claims["roles"] == ["user", "developer"]
        assert "scopes" not in custom_claims  # Scopes resolved at request time

        # User claims from id_token
        assert custom_claims["sub"] == "user-id-123"
        assert custom_claims["email"] == "user@example.com"
        assert custom_claims["name"] == "John Doe"
        assert custom_claims["department"] == "Engineering"

        # Excluded claims
        assert "groups" not in custom_claims

        # Metadata
        assert custom_claims["provider"] == "azure"
        assert "jti" in custom_claims  # UUID for revocation support

        # Standard JWT claims NOT in custom_claims (set by trust manager)
        assert "iss" not in custom_claims
        assert "iat" not in custom_claims
        assert "exp" not in custom_claims

    @pytest.mark.asyncio
    async def test_uses_email_as_identity(self, mock_component, user_claims):
        """Test that email is preferred over sub for identity."""
        # Create mock authorization service
        mock_auth_service = AsyncMock()
        mock_auth_service.get_roles_for_user = AsyncMock(
            return_value=["user", "developer"]
        )

        await prepare_and_mint_sam_token(
            mock_component,
            user_claims,
            "azure",
            "test",
            authorization_service=mock_auth_service,
        )

        # Verify get_roles_for_user was called with email
        mock_auth_service.get_roles_for_user.assert_called_once()
        call_kwargs = mock_auth_service.get_roles_for_user.call_args[1]
        assert call_kwargs["user_identity"] == "user@example.com"

    @pytest.mark.asyncio
    async def test_falls_back_to_sub_when_no_email(self, mock_component):
        """Test that sub is used when email is not present."""
        user_claims = {"sub": "user-id-123", "name": "John Doe"}

        result = await prepare_and_mint_sam_token(
            mock_component, user_claims, "azure", "test"
        )

        assert result.success is True
        assert result.user_identity == "user-id-123"

    @pytest.mark.asyncio
    async def test_empty_roles_when_no_authorization_service(self, user_claims):
        """Test that empty roles are used when authorization_service is not available."""
        component = MagicMock()
        component.gateway_id = "test-gateway"
        # Gateway-level sam_access_token config (Update 14) - use get_config()
        component.get_config = MagicMock(
            return_value={"enabled": True, "ttl_seconds": 3600}
        )
        # Trust manager for signing
        component.trust_manager = MagicMock()
        component.trust_manager.sign_sam_access_token = MagicMock(
            return_value="mocked_jwt_token"
        )

        # Pass authorization_service=None
        result = await prepare_and_mint_sam_token(
            component, user_claims, "azure", "test", authorization_service=None
        )

        assert result.success is True
        assert result.roles == []

    @pytest.mark.asyncio
    async def test_passes_user_context_to_authorization_service(
        self, mock_component, user_claims
    ):
        """Test that user_context is passed when supported."""
        # Create mock authorization service
        mock_auth_service = AsyncMock()
        mock_auth_service.get_roles_for_user = AsyncMock(
            return_value=["user", "developer"]
        )

        await prepare_and_mint_sam_token(
            mock_component,
            user_claims,
            "azure",
            "test_context",
            authorization_service=mock_auth_service,
        )

        # Verify get_roles_for_user was called with correct parameters
        mock_auth_service.get_roles_for_user.assert_called_once()
        call_kwargs = mock_auth_service.get_roles_for_user.call_args[1]

        assert call_kwargs["user_identity"] == "user@example.com"
        assert "gateway_context" in call_kwargs
        assert call_kwargs["gateway_context"]["gateway_id"] == "test-gateway"
        assert call_kwargs["gateway_context"]["idp_claims"] == user_claims


class TestClaimMappingConstants:
    """Tests for claim mapping constants."""

    def test_included_claims_contains_core_identity(self):
        """Test that included claims contain core identity fields."""
        assert "sub" in SAM_TOKEN_INCLUDED_CLAIMS
        assert "email" in SAM_TOKEN_INCLUDED_CLAIMS
        assert "name" in SAM_TOKEN_INCLUDED_CLAIMS

    def test_excluded_claims_contains_arrays(self):
        """Test that excluded claims contain array fields."""
        assert "groups" in SAM_TOKEN_EXCLUDED_CLAIMS
        assert "wids" in SAM_TOKEN_EXCLUDED_CLAIMS
        assert "amr" in SAM_TOKEN_EXCLUDED_CLAIMS

    def test_excluded_claims_contains_reserved_jwt_claims(self):
        """Test that excluded claims contain reserved JWT claims."""
        assert "iss" in SAM_TOKEN_EXCLUDED_CLAIMS
        assert "iat" in SAM_TOKEN_EXCLUDED_CLAIMS
        assert "exp" in SAM_TOKEN_EXCLUDED_CLAIMS
        assert "jti" in SAM_TOKEN_EXCLUDED_CLAIMS

    def test_excluded_claims_contains_authorization_claims(self):
        """Test that excluded claims contain authorization-related claims."""
        assert "roles" in SAM_TOKEN_EXCLUDED_CLAIMS
        assert "scopes" in SAM_TOKEN_EXCLUDED_CLAIMS
