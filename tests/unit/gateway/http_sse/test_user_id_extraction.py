#!/usr/bin/env python3
"""
Unit tests for user ID extraction from different IDP formats in AuthMiddleware.
"""


class TestUserIDExtraction:
    """Test user ID extraction logic for different IDP providers."""

    def extract_user_identifier(self, user_info):
        """
        Simulates the user identifier extraction logic from AuthMiddleware.
        This matches the logic in src/solace_agent_mesh/gateway/http_sse/main.py
        """
        # Priority order for user identifier (most specific to least specific)
        user_identifier = (
            user_info.get("sub")  # Standard OIDC subject claim
            or user_info.get("client_id")  # Mini IDP and some custom IDPs
            or user_info.get("oid")  # Azure AD object ID
            or user_info.get("preferred_username")  # Common in enterprise IDPs
            or user_info.get("upn")  # Azure AD User Principal Name
            or user_info.get("unique_name")  # Some Azure configurations
            or user_info.get("email")  # Fallback to email
            or user_info.get("name")  # Last resort
            or user_info.get("azp")  # Authorized party (rare but possible)
        )

        # Extract email separately (may be different from user identifier)
        email_from_auth = (
            user_info.get("email")
            or user_info.get("preferred_username")
            or user_info.get("upn")
            or user_identifier
        )

        # Extract display name
        given_name = user_info.get("given_name", "") if user_info else ""
        family_name = user_info.get("family_name", "") if user_info else ""
        full_name = (
            f"{given_name} {family_name}".strip() if (given_name or family_name) else ""
        )

        # Build display name with proper None handling
        name_value = None
        if user_info:
            name_value = (
                user_info.get("name")
                or full_name
                or user_info.get("preferred_username")
                or user_identifier
            )

        display_name = name_value.strip() if name_value else ""

        return user_identifier, email_from_auth, display_name

    def test_mini_idp_extraction(self):
        """Test extraction for Mini IDP that uses client_id."""
        user_info = {"client_id": "sam_dev_user", "groups": ["developer"]}

        user_id, email, name = self.extract_user_identifier(user_info)

        assert user_id == "sam_dev_user"
        assert email == "sam_dev_user"
        assert name == "sam_dev_user"

    def test_azure_ad_extraction(self):
        """Test extraction for Azure AD with typical claims."""
        user_info = {
            "oid": "00000000-0000-0000-0000-000000000000",
            "preferred_username": "user@company.com",
            "name": "John Doe",
            "email": "user@company.com",
            "upn": "user@company.com",
        }

        user_id, email, name = self.extract_user_identifier(user_info)

        # Should prefer oid for Azure AD
        assert user_id == "00000000-0000-0000-0000-000000000000"
        assert email == "user@company.com"
        assert name == "John Doe"

    def test_azure_ad_with_sub(self):
        """Test Azure AD when it includes sub claim."""
        user_info = {
            "sub": "AzureAD_SUB_12345",
            "oid": "00000000-0000-0000-0000-000000000000",
            "preferred_username": "user@company.com",
            "name": "John Doe",
        }

        user_id, email, name = self.extract_user_identifier(user_info)

        # Should prefer sub when available
        assert user_id == "AzureAD_SUB_12345"
        assert email == "user@company.com"
        assert name == "John Doe"

    def test_okta_auth0_extraction(self):
        """Test extraction for Okta/Auth0 style IDPs."""
        user_info = {
            "sub": "auth0|507f1f77bcf86cd799439011",
            "email": "user@example.com",
            "name": "Jane Smith",
            "preferred_username": "user@example.com",
        }

        user_id, email, name = self.extract_user_identifier(user_info)

        assert user_id == "auth0|507f1f77bcf86cd799439011"
        assert email == "user@example.com"
        assert name == "Jane Smith"

    def test_keycloak_extraction(self):
        """Test extraction for Keycloak with given/family names."""
        user_info = {
            "sub": "f:550e8400-e29b-41d4-a716-446655440000:johndoe",
            "preferred_username": "johndoe",
            "email": "john.doe@example.com",
            "given_name": "John",
            "family_name": "Doe",
        }

        user_id, email, name = self.extract_user_identifier(user_info)

        assert user_id == "f:550e8400-e29b-41d4-a716-446655440000:johndoe"
        assert email == "john.doe@example.com"
        assert name == "John Doe"  # Should combine given and family names

    def test_google_extraction(self):
        """Test extraction for Google OAuth."""
        user_info = {
            "sub": "110169484474386276334",
            "email": "user@gmail.com",
            "name": "User Name",
            "given_name": "User",
            "family_name": "Name",
        }

        user_id, email, name = self.extract_user_identifier(user_info)

        assert user_id == "110169484474386276334"
        assert email == "user@gmail.com"
        assert name == "User Name"

    def test_minimal_idp_only_sub(self):
        """Test extraction with minimal claims (only sub)."""
        user_info = {"sub": "user123"}

        user_id, email, name = self.extract_user_identifier(user_info)

        assert user_id == "user123"
        assert email == "user123"  # Falls back to user_id
        assert name == "user123"  # Falls back to user_id

    def test_email_only_fallback(self):
        """Test extraction when only email is provided."""
        user_info = {"email": "user@example.com"}

        user_id, email, name = self.extract_user_identifier(user_info)

        assert user_id == "user@example.com"
        assert email == "user@example.com"
        assert name == "user@example.com"

    def test_priority_order(self):
        """Test that claims are extracted in the correct priority order."""
        # Test with all fields present - should use 'sub'
        user_info = {
            "sub": "SUB_VALUE",
            "client_id": "CLIENT_ID_VALUE",
            "oid": "OID_VALUE",
            "preferred_username": "PREFERRED_USERNAME_VALUE",
            "email": "email@example.com",
            "name": "Display Name",
        }

        user_id, email, name = self.extract_user_identifier(user_info)
        assert user_id == "SUB_VALUE"

        # Remove 'sub', should fall back to 'client_id'
        del user_info["sub"]
        user_id, email, name = self.extract_user_identifier(user_info)
        assert user_id == "CLIENT_ID_VALUE"

        # Remove 'client_id', should fall back to 'oid'
        del user_info["client_id"]
        user_id, email, name = self.extract_user_identifier(user_info)
        assert user_id == "OID_VALUE"

        # Remove 'oid', should fall back to 'preferred_username'
        del user_info["oid"]
        user_id, email, name = self.extract_user_identifier(user_info)
        assert user_id == "PREFERRED_USERNAME_VALUE"

    def test_invalid_user_identifiers(self):
        """Test that invalid identifiers are handled correctly."""
        # Test various invalid cases
        test_cases = [
            ({"sub": "unknown"}, "unknown"),
            ({"sub": "Unknown"}, "Unknown"),
            ({"sub": "null"}, "null"),
            ({"sub": "none"}, "none"),
            ({"sub": ""}, None),  # Empty string is falsy, so will be None
            ({"sub": None}, None),
        ]

        for user_info, expected in test_cases:
            user_id, _, _ = self.extract_user_identifier(user_info)
            # The extraction will return these values, but the middleware
            # should reject them. We're just testing extraction here.
            assert user_id == expected, f"Expected {expected}, got {user_id}"

    def test_empty_user_info(self):
        """Test extraction with empty user info."""
        user_info = {}

        user_id, email, name = self.extract_user_identifier(user_info)

        assert user_id is None
        assert email is None
        assert name == ""

    def test_azure_unique_name(self):
        """Test Azure AD with unique_name claim."""
        user_info = {
            "unique_name": "user@company.onmicrosoft.com",
            "name": "Azure User",
        }

        user_id, email, name = self.extract_user_identifier(user_info)

        assert user_id == "user@company.onmicrosoft.com"
        assert email == "user@company.onmicrosoft.com"
        assert name == "Azure User"

    def test_azp_fallback(self):
        """Test extraction with azp (authorized party) as last resort."""
        user_info = {"azp": "client-application-id"}

        user_id, email, name = self.extract_user_identifier(user_info)

        assert user_id == "client-application-id"
        assert email == "client-application-id"
        assert name == "client-application-id"

    def test_name_construction_from_parts(self):
        """Test display name construction from given/family names."""
        test_cases = [
            ({"given_name": "John", "family_name": "Doe"}, "John Doe"),
            ({"given_name": "John"}, "John"),
            ({"family_name": "Doe"}, "Doe"),
            ({"given_name": "", "family_name": "Doe"}, "Doe"),
            ({"given_name": "John", "family_name": ""}, "John"),
            ({"given_name": "", "family_name": ""}, ""),
        ]

        for user_info, expected_name in test_cases:
            user_info["sub"] = "test_user"
            _, _, name = self.extract_user_identifier(user_info)
            assert (
                name == expected_name or name == "test_user"
            )  # Falls back to ID if no name


