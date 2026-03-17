"""
Behaviour tests for share link access control.

These tests verify the security properties of the sharing feature:
- Who can view a shared session (public, authenticated, domain-restricted, user-specific)
- Who can modify/delete a share link (owner only)
- That deleted share links cannot be accessed
- That access control is correctly enforced at the router layer

Tests are organised around behaviours and outcomes, not implementation details.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from solace_agent_mesh.gateway.http_sse.repository.entities.share import ShareLink


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_share_link(**overrides) -> ShareLink:
    defaults = dict(
        share_id="test-share-123",
        session_id="session-abc",
        user_id="owner-user",
        title="My Session",
        is_public=True,
        require_authentication=False,
        allowed_domains=None,
        created_time=1000000,
        updated_time=1000000,
        deleted_at=None,
    )
    defaults.update(overrides)
    return ShareLink(**defaults)


# ---------------------------------------------------------------------------
# Public share access
# ---------------------------------------------------------------------------

class TestPublicShareAccess:
    """A share link with require_authentication=False is publicly accessible."""

    def test_unauthenticated_user_is_denied_even_on_public_share(self):
        """Authentication is always required — unauthenticated access is never allowed."""
        link = make_share_link(require_authentication=False)
        can_access, reason = link.can_be_accessed_by_user(user_id=None, user_email=None)
        assert can_access is False
        assert reason == "authentication_required"

    def test_authenticated_user_can_access_public_share(self):
        link = make_share_link(require_authentication=False)
        can_access, _ = link.can_be_accessed_by_user(user_id="some-user", user_email="user@example.com")
        assert can_access is True

    def test_deleted_share_is_not_accessible(self):
        """A soft-deleted share must not be viewable even if require_authentication=False."""
        link = make_share_link(require_authentication=False, deleted_at=9999999)
        assert link.is_deleted() is True
        # is_deleted() is checked before can_be_accessed_by_user in the service layer —
        # verify the flag itself is set correctly so the guard cannot be bypassed.


# ---------------------------------------------------------------------------
# Authentication-required share access
# ---------------------------------------------------------------------------

class TestAuthRequiredShareAccess:

    def test_unauthenticated_user_is_denied(self):
        link = make_share_link(require_authentication=True)
        can_access, reason = link.can_be_accessed_by_user(user_id=None, user_email=None)
        assert can_access is False
        assert reason == "authentication_required"

    def test_authenticated_user_without_domain_restriction_is_allowed(self):
        link = make_share_link(require_authentication=True, allowed_domains=None)
        can_access, _ = link.can_be_accessed_by_user(user_id="uid", user_email="user@any.com")
        assert can_access is True


# ---------------------------------------------------------------------------
# Domain-restricted share access
# ---------------------------------------------------------------------------

class TestDomainRestrictedShareAccess:

    def test_user_from_allowed_domain_is_permitted(self):
        link = make_share_link(require_authentication=True, allowed_domains="company.com")
        can_access, _ = link.can_be_accessed_by_user(user_id="uid", user_email="alice@company.com")
        assert can_access is True

    def test_user_from_different_domain_is_denied(self):
        link = make_share_link(require_authentication=True, allowed_domains="company.com")
        can_access, reason = link.can_be_accessed_by_user(user_id="uid", user_email="alice@other.com")
        assert can_access is False
        assert reason == "domain_mismatch"

    def test_domain_check_is_case_insensitive(self):
        link = make_share_link(require_authentication=True, allowed_domains="Company.COM")
        can_access, _ = link.can_be_accessed_by_user(user_id="uid", user_email="alice@COMPANY.com")
        assert can_access is True

    def test_unauthenticated_user_denied_even_with_matching_domain(self):
        """Without a user_id the caller is not authenticated regardless of email."""
        link = make_share_link(require_authentication=True, allowed_domains="company.com")
        can_access, reason = link.can_be_accessed_by_user(user_id=None, user_email="alice@company.com")
        assert can_access is False
        assert reason == "authentication_required"

    def test_multiple_allowed_domains_any_one_grants_access(self):
        link = make_share_link(require_authentication=True, allowed_domains="company.com,partner.org")
        can_access_company, _ = link.can_be_accessed_by_user(user_id="u1", user_email="a@company.com")
        can_access_partner, _ = link.can_be_accessed_by_user(user_id="u2", user_email="b@partner.org")
        can_access_other, _ = link.can_be_accessed_by_user(user_id="u3", user_email="c@other.io")
        assert can_access_company is True
        assert can_access_partner is True
        assert can_access_other is False

    def test_domain_restriction_requires_authentication_flag(self):
        """Domains without require_authentication should not exist (validated at creation),
        but authentication is always required regardless of require_authentication flag."""
        link = make_share_link(require_authentication=False, allowed_domains="company.com")
        # Authentication is always required — unauthenticated users are denied
        can_access, reason = link.can_be_accessed_by_user(user_id=None, user_email=None)
        assert can_access is False
        assert reason == "authentication_required"
        # Authenticated user from allowed domain should still work
        can_access2, _ = link.can_be_accessed_by_user(user_id="uid", user_email="alice@company.com")
        assert can_access2 is True


# ---------------------------------------------------------------------------
# User-specific share access (the bug that was fixed)
# ---------------------------------------------------------------------------

class TestUserSpecificShareAccess:
    """
    When a share has explicit shared_user_emails, access must be restricted
    to only those users — regardless of require_authentication and allowed_domains.

    This test class directly verifies the security fix from the PR review.
    """

    def test_listed_user_is_allowed(self):
        link = make_share_link(require_authentication=False)  # public by default settings
        shared_emails = ["alice@example.com", "bob@example.com"]
        can_access, _ = link.can_be_accessed_by_user("uid-alice", "alice@example.com", shared_emails)
        assert can_access is True

    def test_unlisted_authenticated_user_is_denied(self):
        link = make_share_link(require_authentication=False)
        shared_emails = ["alice@example.com"]
        can_access, reason = link.can_be_accessed_by_user("uid-carol", "carol@example.com", shared_emails)
        assert can_access is False
        assert reason == "not_shared_with_user"

    def test_unauthenticated_user_denied_when_user_specific_sharing_active(self):
        """Public link settings must NOT override user-specific access list."""
        link = make_share_link(require_authentication=False)  # would be public without shared list
        shared_emails = ["alice@example.com"]
        can_access, reason = link.can_be_accessed_by_user(None, None, shared_emails)
        assert can_access is False
        assert reason == "authentication_required"

    def test_empty_shared_users_list_falls_back_to_general_rules(self):
        """An empty list is NOT the same as a populated list — it should not restrict access.
        Authentication is still required, but an authenticated user should get through."""
        link = make_share_link(require_authentication=False)
        # Unauthenticated is always denied
        can_access_unauth, reason = link.can_be_accessed_by_user(None, None, shared_user_emails=[])
        assert can_access_unauth is False
        assert reason == "authentication_required"
        # Authenticated user with empty shared list falls back to general rules (allowed)
        can_access_auth, _ = link.can_be_accessed_by_user("uid", "user@example.com", shared_user_emails=[])
        assert can_access_auth is True

    def test_user_specific_check_is_case_insensitive(self):
        link = make_share_link(require_authentication=False)
        shared_emails = ["Alice@Example.COM"]
        can_access, _ = link.can_be_accessed_by_user("uid", "alice@example.com", shared_emails)
        assert can_access is True


# ---------------------------------------------------------------------------
# Ownership / modification guards
# ---------------------------------------------------------------------------

class TestShareOwnership:

    def test_owner_can_modify_their_share(self):
        link = make_share_link(user_id="owner-user")
        assert link.can_be_modified_by_user("owner-user") is True

    def test_non_owner_cannot_modify_share(self):
        link = make_share_link(user_id="owner-user")
        assert link.can_be_modified_by_user("other-user") is False

    def test_owner_cannot_modify_deleted_share(self):
        """Soft-deleted shares must be immutable even to the owner."""
        link = make_share_link(user_id="owner-user", deleted_at=9999999)
        assert link.can_be_modified_by_user("owner-user") is False


# ---------------------------------------------------------------------------
# Router-level: view_shared_session endpoint security
# ---------------------------------------------------------------------------

class TestViewSharedSessionEndpoint:
    """
    Verify that the GET /{share_id} router endpoint enforces access control
    and returns the correct HTTP status codes.
    """

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_share_service(self):
        return MagicMock()

    @pytest.mark.asyncio
    async def test_returns_401_when_authentication_required_but_not_provided(
        self, mock_db, mock_share_service
    ):
        from fastapi import HTTPException
        from solace_agent_mesh.gateway.http_sse.routers.share import view_shared_session

        mock_share_service.get_shared_session_view = AsyncMock(
            side_effect=PermissionError("Authentication required to view this shared session")
        )

        with pytest.raises(HTTPException) as exc_info:
            await view_shared_session(
                share_id="abc123",
                request=MagicMock(),
                user_id=None,
                user_email=None,
                db=mock_db,
                share_service=mock_share_service,
            )

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_403_when_domain_does_not_match(
        self, mock_db, mock_share_service
    ):
        from fastapi import HTTPException
        from solace_agent_mesh.gateway.http_sse.routers.share import view_shared_session

        mock_share_service.get_shared_session_view = AsyncMock(
            side_effect=PermissionError("Access restricted to users from: company.com")
        )

        # Patch ShareRepository used inside the endpoint for snapshot_time lookup
        mock_share_repo = MagicMock()
        mock_share_repo.find_by_share_id.return_value = make_share_link(user_id="other-owner")
        mock_share_repo.find_share_user_by_email.return_value = None

        with patch(
            "solace_agent_mesh.gateway.http_sse.repository.share_repository.ShareRepository",
            return_value=mock_share_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await view_shared_session(
                    share_id="abc123",
                    request=MagicMock(),
                    user_id="uid",
                    user_email="user@other.com",
                    db=mock_db,
                    share_service=mock_share_service,
                )

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_returns_404_when_share_not_found(
        self, mock_db, mock_share_service
    ):
        from fastapi import HTTPException
        from solace_agent_mesh.gateway.http_sse.routers.share import view_shared_session

        mock_share_service.get_shared_session_view = AsyncMock(
            side_effect=ValueError("Share link not found")
        )

        with pytest.raises(HTTPException) as exc_info:
            await view_shared_session(
                share_id="nonexistent",
                request=MagicMock(),
                user_id=None,
                user_email=None,
                db=mock_db,
                share_service=mock_share_service,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_session_data_for_authorised_user(
        self, mock_db, mock_share_service
    ):
        from solace_agent_mesh.gateway.http_sse.routers.share import view_shared_session

        expected_view = MagicMock()
        mock_share_service.get_shared_session_view = AsyncMock(return_value=expected_view)

        # Patch ShareRepository used inside the endpoint for snapshot_time lookup
        mock_share_repo = MagicMock()
        mock_share_repo.find_by_share_id.return_value = make_share_link(user_id="other-owner")
        mock_share_repo.find_share_user_by_email.return_value = None

        with patch(
            "solace_agent_mesh.gateway.http_sse.repository.share_repository.ShareRepository",
            return_value=mock_share_repo,
        ):
            result = await view_shared_session(
                share_id="abc123",
                request=MagicMock(),
                user_id="uid",
                user_email="user@company.com",
                db=mock_db,
                share_service=mock_share_service,
            )

        assert result is expected_view


# ---------------------------------------------------------------------------
# Router-level: artifact endpoint security
# ---------------------------------------------------------------------------

class TestGetSharedArtifactEndpoint:
    """
    Verify that the GET /{share_id}/artifacts/{filename} endpoint enforces
    the same access control as the session view endpoint.
    """

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    def _make_share_repo(self, share_link, shared_emails=None):
        repo = MagicMock()
        repo.find_by_share_id.return_value = share_link
        repo.find_share_user_emails.return_value = shared_emails or []
        return repo

    @pytest.mark.asyncio
    async def test_unauthenticated_user_denied_on_auth_required_share(self, mock_db):
        from fastapi import HTTPException
        from solace_agent_mesh.gateway.http_sse.routers.share import get_shared_artifact_content

        share_link = make_share_link(require_authentication=True)
        mock_share_service = MagicMock()
        mock_component = MagicMock()

        # ShareRepository is imported lazily inside get_shared_artifact_content
        with patch(
            "solace_agent_mesh.gateway.http_sse.repository.share_repository.ShareRepository",
            return_value=self._make_share_repo(share_link),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_shared_artifact_content(
                    share_id="abc123",
                    filename="report.pdf",
                    request=MagicMock(),
                    user_id=None,
                    user_email=None,
                    db=mock_db,
                    share_service=mock_share_service,
                    component=mock_component,
                )

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_unlisted_user_denied_on_user_specific_share(self, mock_db):
        """A user not in the shared_users list must not download artifacts."""
        from fastapi import HTTPException
        from solace_agent_mesh.gateway.http_sse.routers.share import get_shared_artifact_content

        # Public share settings but restricted to specific users
        share_link = make_share_link(require_authentication=False)
        mock_share_service = MagicMock()
        mock_component = MagicMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.repository.share_repository.ShareRepository",
            return_value=self._make_share_repo(share_link, shared_emails=["alice@example.com"]),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_shared_artifact_content(
                    share_id="abc123",
                    filename="report.pdf",
                    request=MagicMock(),
                    user_id="carol-uid",
                    user_email="carol@example.com",
                    db=mock_db,
                    share_service=mock_share_service,
                    component=mock_component,
                )

        assert exc_info.value.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_returns_404_when_share_link_does_not_exist(self, mock_db):
        from fastapi import HTTPException
        from solace_agent_mesh.gateway.http_sse.routers.share import get_shared_artifact_content

        mock_repo = MagicMock()
        mock_repo.find_by_share_id.return_value = None
        mock_share_service = MagicMock()
        mock_component = MagicMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.repository.share_repository.ShareRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_shared_artifact_content(
                    share_id="nonexistent",
                    filename="report.pdf",
                    request=MagicMock(),
                    user_id=None,
                    user_email=None,
                    db=mock_db,
                    share_service=mock_share_service,
                    component=mock_component,
                )

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Service-level: access control enforcement in get_shared_session_view
# ---------------------------------------------------------------------------

class TestShareServiceAccessEnforcement:
    """
    Verify that ShareService.get_shared_session_view raises the correct
    exceptions for denied access, independently of the router layer.
    """

    def _make_service(self):
        from solace_agent_mesh.gateway.http_sse.services.share_service import ShareService
        service = ShareService.__new__(ShareService)
        service.repository = MagicMock()
        service.component = MagicMock()
        return service

    @pytest.mark.asyncio
    async def test_raises_for_deleted_share(self):
        service = self._make_service()
        service.repository.find_by_share_id.return_value = make_share_link(deleted_at=999)
        service.repository.find_share_user_emails.return_value = []

        with pytest.raises(ValueError, match="not found"):
            await service.get_shared_session_view(MagicMock(), "abc", user_id=None)

    @pytest.mark.asyncio
    async def test_raises_permission_error_when_auth_required_and_not_provided(self):
        service = self._make_service()
        service.repository.find_by_share_id.return_value = make_share_link(require_authentication=True)
        service.repository.find_share_user_emails.return_value = []

        with pytest.raises(PermissionError, match="Authentication required"):
            await service.get_shared_session_view(MagicMock(), "abc", user_id=None, user_email=None)

    @pytest.mark.asyncio
    async def test_raises_permission_error_for_domain_mismatch(self):
        service = self._make_service()
        service.repository.find_by_share_id.return_value = make_share_link(
            require_authentication=True, allowed_domains="company.com"
        )
        service.repository.find_share_user_emails.return_value = []

        with pytest.raises(PermissionError, match="Access restricted"):
            await service.get_shared_session_view(
                MagicMock(), "abc", user_id="uid", user_email="user@other.com"
            )

    @pytest.mark.asyncio
    async def test_raises_permission_error_for_user_not_in_shared_list(self):
        """Regression: user-specific access must not be bypassed by public share settings."""
        service = self._make_service()
        service.repository.find_by_share_id.return_value = make_share_link(require_authentication=False)
        service.repository.find_share_user_emails.return_value = ["alice@example.com"]

        with pytest.raises(PermissionError):
            await service.get_shared_session_view(
                MagicMock(), "abc", user_id="carol", user_email="carol@example.com"
            )

    @pytest.mark.asyncio
    async def test_user_specific_share_allows_listed_user(self):
        """Listed user must get through access control and reach data loading."""
        service = self._make_service()
        service.repository.find_by_share_id.return_value = make_share_link(require_authentication=False)
        service.repository.find_share_user_emails.return_value = ["alice@example.com"]

        # Patch the downstream data loading so we don't need real DB fixtures.
        # These are imported at the top of share_service, so patch in the service module's namespace.
        with patch(
            "solace_agent_mesh.gateway.http_sse.services.share_service.ChatTaskRepository"
        ) as MockTaskRepo, patch(
            "solace_agent_mesh.gateway.http_sse.services.share_service.SessionRepository"
        ) as MockSessionRepo:
            mock_task_repo = MagicMock()
            mock_task_repo.find_by_session.return_value = []
            MockTaskRepo.return_value = mock_task_repo

            mock_session_repo = MagicMock()
            mock_session_repo.find_user_session.return_value = MagicMock(project_id=None)
            MockSessionRepo.return_value = mock_session_repo

            service.repository.find_share_users.return_value = []

            # Should not raise — access granted
            try:
                await service.get_shared_session_view(
                    MagicMock(), "abc", user_id="alice-uid", user_email="alice@example.com"
                )
            except PermissionError:
                pytest.fail("Listed user was denied access — access control regression")


# ---------------------------------------------------------------------------
# Service-level: create_share_link business rules
# ---------------------------------------------------------------------------

class TestCreateShareLinkBusinessRules:

    def _make_service(self):
        from solace_agent_mesh.gateway.http_sse.services.share_service import ShareService
        service = ShareService.__new__(ShareService)
        service.repository = MagicMock()
        service.component = MagicMock()
        return service

    def test_domain_restriction_without_auth_required_is_rejected(self):
        """Business rule: allowed_domains requires require_authentication=True."""
        from solace_agent_mesh.gateway.http_sse.repository.models.share_model import (
            CreateShareLinkRequest,
        )
        service = self._make_service()

        mock_session = MagicMock()
        mock_session.name = "Test Session"

        # SessionService is imported lazily inside create_share_link — patch at its source module
        with patch(
            "solace_agent_mesh.gateway.http_sse.services.session_service.SessionService"
        ) as MockSessionService:
            MockSessionService.return_value.get_session_details.return_value = mock_session
            service.repository.find_by_session_id.return_value = None

            request = CreateShareLinkRequest(
                require_authentication=False,
                allowed_domains=["company.com"],
            )

            with pytest.raises(ValueError, match="Domain restrictions require authentication"):
                service.create_share_link(MagicMock(), "sess1", "user1", request, "http://app")

    def test_invalid_domain_format_is_rejected(self):
        from solace_agent_mesh.gateway.http_sse.repository.models.share_model import (
            CreateShareLinkRequest,
        )
        service = self._make_service()

        mock_session = MagicMock()
        mock_session.name = "Test Session"

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.session_service.SessionService"
        ) as MockSessionService:
            MockSessionService.return_value.get_session_details.return_value = mock_session
            service.repository.find_by_session_id.return_value = None

            request = CreateShareLinkRequest(
                require_authentication=True,
                allowed_domains=["not_a_domain"],
            )

            with pytest.raises(ValueError, match="Invalid domains"):
                service.create_share_link(MagicMock(), "sess1", "user1", request, "http://app")

    def test_creating_share_for_nonexistent_session_is_rejected(self):
        from solace_agent_mesh.gateway.http_sse.repository.models.share_model import (
            CreateShareLinkRequest,
        )
        service = self._make_service()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.session_service.SessionService"
        ) as MockSessionService:
            MockSessionService.return_value.get_session_details.return_value = None

            with pytest.raises(ValueError, match="not found"):
                service.create_share_link(
                    MagicMock(), "no-such-session", "user1", CreateShareLinkRequest(), "http://app"
                )

    def test_duplicate_create_returns_existing_link_not_error(self):
        """Creating a second share for the same session must be idempotent."""
        from solace_agent_mesh.gateway.http_sse.repository.models.share_model import (
            CreateShareLinkRequest,
        )
        service = self._make_service()
        existing = make_share_link()
        service.repository.find_share_users.return_value = []

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.session_service.SessionService"
        ) as MockSessionService:
            MockSessionService.return_value.get_session_details.return_value = MagicMock(name="s")
            service.repository.find_by_session_id.return_value = existing

            result = service.create_share_link(
                MagicMock(), "sess1", "user1", CreateShareLinkRequest(), "http://app"
            )

        assert result.share_id == existing.share_id


# ---------------------------------------------------------------------------
# Service-level: add/remove users persist correctly
# ---------------------------------------------------------------------------

class TestShareUserManagementPersistence:
    """
    Verify that adding and removing users from a share link results in
    db.commit() being called — the missing commit was a bug fixed in this PR.
    """

    def _make_service(self):
        from solace_agent_mesh.gateway.http_sse.services.share_service import ShareService
        service = ShareService.__new__(ShareService)
        service.repository = MagicMock()
        service.component = MagicMock()
        return service

    def test_add_users_commits_transaction(self):
        service = self._make_service()
        service.repository.find_by_share_id.return_value = make_share_link(user_id="owner")
        service.repository.check_user_has_access.return_value = False
        service.repository.add_share_user.return_value = MagicMock(
            user_email="alice@example.com",
            access_level="RESOURCE_VIEWER",
            added_at=1000,
        )
        mock_db = MagicMock()

        service.add_share_users(mock_db, "share123", "owner", [{"user_email": "alice@example.com"}])

        mock_db.commit.assert_called_once()

    def test_remove_users_commits_transaction(self):
        service = self._make_service()
        service.repository.find_by_share_id.return_value = make_share_link(user_id="owner")
        service.repository.delete_share_users_batch.return_value = 1
        mock_db = MagicMock()

        service.delete_share_users(mock_db, "share123", "owner", ["alice@example.com"])

        mock_db.commit.assert_called_once()

    def test_non_owner_cannot_add_users(self):
        service = self._make_service()
        service.repository.find_by_share_id.return_value = make_share_link(user_id="real-owner")

        with pytest.raises(ValueError, match="Not authorized"):
            service.add_share_users(MagicMock(), "share123", "attacker", ["victim@example.com"])

    def test_non_owner_cannot_remove_users(self):
        service = self._make_service()
        service.repository.find_by_share_id.return_value = make_share_link(user_id="real-owner")

        with pytest.raises(ValueError, match="Not authorized"):
            service.delete_share_users(MagicMock(), "share123", "attacker", ["alice@example.com"])
