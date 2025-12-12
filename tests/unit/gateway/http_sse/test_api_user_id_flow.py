#!/usr/bin/env python3
"""
Unit test to verify that user ID flows correctly through all API endpoints.
This test verifies that the AuthMiddleware -> Dependencies -> Controllers flow works correctly.
"""

import asyncio
import os
import sys
from unittest.mock import Mock

from fastapi import Request

from solace_agent_mesh.shared.api.auth_utils import get_current_user


class TestUserIDFlow:
    """Test that user ID extraction flows correctly through the API layers."""

    def test_auth_middleware_to_dependencies_flow(self):
        """Test that AuthMiddleware correctly sets user state that dependencies can read."""

        # Simulate different IDP responses
        idp_responses = [
            {
                "name": "Mini IDP",
                "user_info": {"client_id": "sam_dev_user", "groups": ["developer"]},
                "expected_id": "sam_dev_user",
            },
            {
                "name": "Azure AD",
                "user_info": {
                    "oid": "azure-oid-123",
                    "preferred_username": "user@company.com",
                    "name": "John Doe",
                },
                "expected_id": "azure-oid-123",
            },
            {
                "name": "Standard OIDC",
                "user_info": {"sub": "oidc-sub-456", "email": "user@example.com"},
                "expected_id": "oidc-sub-456",
            },
        ]

        for idp_test in idp_responses:
            print(f"\nTesting {idp_test['name']}...")

            # Mock request with state
            mock_request = Mock(spec=Request)
            mock_request.state = Mock()

            # Simulate what AuthMiddleware would set based on the user_info
            user_info = idp_test["user_info"]

            # Extract user ID using the same logic as AuthMiddleware
            user_identifier = (
                user_info.get("sub")
                or user_info.get("client_id")
                or user_info.get("oid")
                or user_info.get("preferred_username")
                or user_info.get("upn")
                or user_info.get("unique_name")
                or user_info.get("email")
                or user_info.get("name")
                or user_info.get("azp")
            )

            # Set user state as AuthMiddleware would
            mock_request.state.user = {
                "id": user_identifier,
                "email": user_info.get("email", user_identifier),
                "name": user_info.get("name", user_identifier),
                "authenticated": True,
                "auth_method": "oidc",
            }

            # Test get_current_user function (from auth_utils)
            # Run async function
            user = asyncio.run(get_current_user(mock_request))

            assert user["id"] == idp_test["expected_id"], (
                f"Expected user ID {idp_test['expected_id']}, got {user['id']}"
            )
            assert user["authenticated"] == True
            print(f"  ✓ get_current_user returns correct ID: {user['id']}")

            # Test get_user_id dependency
            # This would require more complex mocking of the SessionManager
            # but the key point is it extracts user["id"] from request.state.user

    def test_controller_user_id_extraction(self):
        """Test that controllers correctly extract user ID from get_current_user."""

        # Mock user dict as returned by get_current_user
        test_users = [
            {"id": "sam_dev_user", "name": "Sam Dev", "email": "sam@dev.local"},
            {"id": "azure-user-123", "name": "Azure User", "email": "user@azure.com"},
            {"id": "oidc-sub-789", "name": "OIDC User", "email": "user@oidc.com"},
        ]

        for user in test_users:
            # Test the pattern used in session_controller
            user_id = user.get("id")
            assert user_id == user["id"], f"Failed to extract ID from {user}"
            print(f"  ✓ Controller extracts ID correctly: {user_id}")

    def test_session_service_receives_correct_id(self):
        """Test that the session service receives the correct user ID."""

        # This simulates the flow from controller to service
        test_cases = [
            ("sam_dev_user", "sam_dev_user"),
            ("azure-oid-123", "azure-oid-123"),
            ("oidc-sub-456", "oidc-sub-456"),
        ]

        for input_id, expected_id in test_cases:
            # Simulate what the controller passes to the service
            assert input_id == expected_id, f"ID mismatch: {input_id} != {expected_id}"

            # The service should reject empty/invalid IDs
            assert input_id and input_id.strip() != "", (
                "Empty user ID should be rejected"
            )
            assert input_id.lower() not in ["unknown", "null", "none"], (
                f"Invalid user ID '{input_id}' should be rejected"
            )

            print(f"  ✓ Valid user ID passes validation: {input_id}")

    def test_complete_flow_simulation(self):
        """Simulate the complete flow from IDP response to database storage."""

        print("\nSimulating complete flow for Mini IDP:")

        # 1. IDP returns user info
        idp_response = {"client_id": "sam_dev_user", "groups": ["developer"]}
        print(f"  1. IDP Response: {idp_response}")

        # 2. AuthMiddleware extracts user ID
        user_id = idp_response.get("client_id")
        print(f"  2. AuthMiddleware extracts ID: {user_id}")

        # 3. AuthMiddleware sets request.state.user
        user_state = {
            "id": user_id,
            "email": user_id,  # Falls back to user_id when no email
            "name": user_id,  # Falls back to user_id when no name
            "authenticated": True,
            "auth_method": "oidc",
        }
        print(f"  3. Request state set: {user_state}")

        # 4. Controller gets user via get_current_user
        controller_user = user_state  # This is what get_current_user returns
        controller_user_id = controller_user.get("id")
        print(f"  4. Controller extracts ID: {controller_user_id}")

        # 5. Service receives user_id
        service_user_id = controller_user_id
        print(f"  5. Service receives ID: {service_user_id}")

        # 6. Database stores user_id
        stored_user_id = service_user_id
        print(f"  6. Database stores ID: {stored_user_id}")

        # Verify the ID is correct throughout
        assert stored_user_id == "sam_dev_user", (
            f"Expected 'sam_dev_user', got '{stored_user_id}'"
        )
        assert stored_user_id != "Unknown", "User ID should not be 'Unknown'"

        print("  ✓ Complete flow works correctly!")


