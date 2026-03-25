"""
Integration tests for ProjectUserRepository operations.

Tests repository methods against real SQLite and PostgreSQL databases.
These tests replace the mocked unit tests in tests/unit/repository/test_project_user_repository.py
which used mocked DB sessions.

The entity business logic tests (TestProjectUserEntity) remain in unit tests as they test
pure logic without database operations.

All tests in this file run against both SQLite and PostgreSQL via pytest parametrization.
Docker must be running for PostgreSQL tests (testcontainers handles container lifecycle).
"""

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from tests.integration.apis.infrastructure.database_inspector import DatabaseInspector
from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter
from solace_agent_mesh.gateway.http_sse.repository.project_user_repository import (
    ProjectUserRepository,
)
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms


class TestAddUserToProject:
    """Tests for adding users to projects with real database."""

    def test_add_user_creates_record_with_correct_data(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that adding a user creates a record in the database with correct data."""
        # Arrange: Create a project
        project_id = "proj-add-user-123"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Test Project",
            user_id="sam_dev_user",
        )

        # Act: Add user to project using repository
        db_session = db_session_factory()
        repo = ProjectUserRepository(db_session)
        result = repo.add_user_to_project(
            project_id=project_id,
            user_id="user-456",
            role="editor",
            added_by_user_id="sam_dev_user",
        )
        db_session.close()

        # Assert: Verify return value
        assert result is not None
        assert result.project_id == project_id
        assert result.user_id == "user-456"
        assert result.role == "editor"
        assert result.added_by_user_id == "sam_dev_user"

        # Assert: Verify database record
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            project_users_table = metadata.tables["project_users"]
            query = sa.select(project_users_table).where(
                sa.and_(
                    project_users_table.c.project_id == project_id,
                    project_users_table.c.user_id == "user-456",
                )
            )
            db_record = conn.execute(query).first()

            assert db_record is not None
            assert db_record.role == "EDITOR"
            assert db_record.added_by_user_id == "sam_dev_user"
            assert db_record.added_at is not None


class TestGetProjectUsers:
    """Tests for getting users with access to a project."""

    def test_get_project_users_returns_all_users(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that get_project_users returns all users with access to a project."""
        # Arrange: Create project
        project_id = "proj-get-users-123"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Test Project",
            user_id="owner@example.com",
        )

        # Add users directly to database
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            project_users_table = metadata.tables["project_users"]
            now = now_epoch_ms()

            # Add two users
            conn.execute(
                sa.insert(project_users_table).values(
                    id="pu-1",
                    project_id=project_id,
                    user_id="user-1",
                    role="OWNER",
                    added_at=now,
                    added_by_user_id="user-1",
                )
            )
            conn.execute(
                sa.insert(project_users_table).values(
                    id="pu-2",
                    project_id=project_id,
                    user_id="user-2",
                    role="EDITOR",
                    added_at=now,
                    added_by_user_id="user-1",
                )
            )
            conn.commit()

        # Act: Get project users
        db_session = db_session_factory()
        repo = ProjectUserRepository(db_session)
        result = repo.get_project_users(project_id)
        db_session.close()

        # Assert
        assert len(result) == 2
        user_ids = [pu.user_id for pu in result]
        assert "user-1" in user_ids
        assert "user-2" in user_ids

        # Verify roles - repository returns lowercase via enum.value
        user1 = next(pu for pu in result if pu.user_id == "user-1")
        user2 = next(pu for pu in result if pu.user_id == "user-2")
        assert user1.role == "owner"
        assert user2.role == "editor"

    def test_get_project_users_returns_empty_list_when_no_users(
        self,
        gateway_adapter: GatewayAdapter,
        db_session_factory,
    ):
        """Test that get_project_users returns empty list when no users have access."""
        # Arrange: Create project with no users
        project_id = "proj-no-users-123"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Project Without Users",
            user_id="owner@example.com",
        )

        # Act: Get project users
        db_session = db_session_factory()
        repo = ProjectUserRepository(db_session)
        result = repo.get_project_users(project_id)
        db_session.close()

        # Assert
        assert result == []


class TestGetUserProjectAccess:
    """Tests for getting specific user's access to a project."""

    def test_get_user_project_access_returns_access_when_exists(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that get_user_project_access returns access record when it exists."""
        # Arrange: Create project and add user
        project_id = "proj-access-123"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Test Project",
            user_id="owner@example.com",
        )

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            project_users_table = metadata.tables["project_users"]

            conn.execute(
                sa.insert(project_users_table).values(
                    id="pu-1",
                    project_id=project_id,
                    user_id="user-456",
                    role="EDITOR",
                    added_at=now_epoch_ms(),
                    added_by_user_id="owner@example.com",
                )
            )
            conn.commit()

        # Act: Get user's access
        db_session = db_session_factory()
        repo = ProjectUserRepository(db_session)
        result = repo.get_user_project_access(project_id, "user-456")
        db_session.close()

        # Assert
        assert result is not None
        assert result.project_id == project_id
        assert result.user_id == "user-456"
        assert result.role == "editor"  # Repository returns lowercase

    def test_get_user_project_access_returns_none_when_not_exists(
        self,
        gateway_adapter: GatewayAdapter,
        db_session_factory,
    ):
        """Test that get_user_project_access returns None when access doesn't exist."""
        # Arrange: Create project without adding the user
        project_id = "proj-no-access-123"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Test Project",
            user_id="owner@example.com",
        )

        # Act: Try to get non-existent access
        db_session = db_session_factory()
        repo = ProjectUserRepository(db_session)
        result = repo.get_user_project_access(project_id, "user-456")
        db_session.close()

        # Assert
        assert result is None


class TestUpdateUserRole:
    """Tests for updating user roles with real database."""

    def test_update_user_role_updates_and_returns_entity(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that update_user_role updates the role in database and returns updated entity."""
        # Arrange: Create project and add user with viewer role
        project_id = "proj-update-role-123"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Test Project",
            user_id="owner@example.com",
        )

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            project_users_table = metadata.tables["project_users"]

            conn.execute(
                sa.insert(project_users_table).values(
                    id="pu-update-1",
                    project_id=project_id,
                    user_id="user-456",
                    role="VIEWER",
                    added_at=now_epoch_ms(),
                    added_by_user_id="owner@example.com",
                )
            )
            conn.commit()

        # Act: Update role to editor
        db_session = db_session_factory()
        repo = ProjectUserRepository(db_session)
        result = repo.update_user_role(project_id, "user-456", "editor")
        db_session.close()

        # Assert: Return value - repository returns lowercase
        assert result is not None
        assert result.role == "editor"

        # Assert: Database updated - DB stores uppercase
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            project_users_table = metadata.tables["project_users"]
            query = sa.select(project_users_table).where(
                sa.and_(
                    project_users_table.c.project_id == project_id,
                    project_users_table.c.user_id == "user-456",
                )
            )
            db_record = conn.execute(query).first()

            assert db_record.role == "EDITOR"

    def test_update_user_role_returns_none_when_not_found(
        self, gateway_adapter: GatewayAdapter, db_session_factory
    ):
        """Test that update_user_role returns None when access record doesn't exist."""
        # Arrange: Create project without adding the user
        project_id = "proj-no-user-123"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Test Project",
            user_id="owner@example.com",
        )

        # Act: Try to update non-existent user access
        db_session = db_session_factory()
        repo = ProjectUserRepository(db_session)
        result = repo.update_user_role(project_id, "user-456", "editor")
        db_session.close()

        # Assert
        assert result is None


class TestRemoveUserFromProject:
    """Tests for removing user access with real database."""

    def test_remove_user_from_project_deletes_and_returns_true(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that remove_user_from_project deletes record from database."""
        # Arrange: Create project and add user
        project_id = "proj-remove-user-123"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Test Project",
            user_id="owner@example.com",
        )

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            project_users_table = metadata.tables["project_users"]

            conn.execute(
                sa.insert(project_users_table).values(
                    id="pu-remove-1",
                    project_id=project_id,
                    user_id="user-456",
                    role="EDITOR",
                    added_at=now_epoch_ms(),
                    added_by_user_id="owner@example.com",
                )
            )
            conn.commit()

        # Act: Remove user
        db_session = db_session_factory()
        repo = ProjectUserRepository(db_session)
        result = repo.remove_user_from_project(project_id, "user-456")
        db_session.close()

        # Assert: Returns True
        assert result is True

        # Assert: Record deleted from database
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            project_users_table = metadata.tables["project_users"]
            query = sa.select(project_users_table).where(
                sa.and_(
                    project_users_table.c.project_id == project_id,
                    project_users_table.c.user_id == "user-456",
                )
            )
            db_record = conn.execute(query).first()

            assert db_record is None  # Record should be deleted

    def test_remove_user_from_project_returns_false_when_not_found(
        self, gateway_adapter: GatewayAdapter, db_session_factory
    ):
        """Test that remove_user_from_project returns False when record doesn't exist."""
        # Arrange: Create project without the user
        project_id = "proj-no-remove-123"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Test Project",
            user_id="owner@example.com",
        )

        # Act: Try to remove non-existent user
        db_session = db_session_factory()
        repo = ProjectUserRepository(db_session)
        result = repo.remove_user_from_project(project_id, "user-456")
        db_session.close()

        # Assert
        assert result is False


class TestUserHasAccess:
    """Tests for checking user access with real database."""

    def test_user_has_access_returns_true_when_access_exists(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that user_has_access returns True when user has access."""
        # Arrange: Create project and add user
        project_id = "proj-has-access-123"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Test Project",
            user_id="owner@example.com",
        )

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            project_users_table = metadata.tables["project_users"]

            conn.execute(
                sa.insert(project_users_table).values(
                    id="pu-access-1",
                    project_id=project_id,
                    user_id="user-456",
                    role="VIEWER",
                    added_at=now_epoch_ms(),
                    added_by_user_id="owner@example.com",
                )
            )
            conn.commit()

        # Act: Check access
        db_session = db_session_factory()
        repo = ProjectUserRepository(db_session)
        result = repo.user_has_access(project_id, "user-456")
        db_session.close()

        # Assert
        assert result is True

    def test_user_has_access_returns_false_when_no_access(
        self, gateway_adapter: GatewayAdapter, db_session_factory
    ):
        """Test that user_has_access returns False when user has no access."""
        # Arrange: Create project without adding the user
        project_id = "proj-no-access-456"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Test Project",
            user_id="owner@example.com",
        )

        # Act: Check access for user not in project
        db_session = db_session_factory()
        repo = ProjectUserRepository(db_session)
        result = repo.user_has_access(project_id, "user-456")
        db_session.close()

        # Assert
        assert result is False


class TestGetUserProjectsAccess:
    """Tests for getting all projects a user has access to."""

    def test_get_user_projects_access_returns_all_projects(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that get_user_projects_access returns all projects user can access."""
        # Arrange: Create multiple projects
        gateway_adapter.seed_project(
            project_id="proj-1",
            name="Project 1",
            user_id="owner@example.com",
        )
        gateway_adapter.seed_project(
            project_id="proj-2",
            name="Project 2",
            user_id="owner@example.com",
        )

        # Add user to both projects
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            project_users_table = metadata.tables["project_users"]
            now = now_epoch_ms()

            conn.execute(
                sa.insert(project_users_table).values(
                    id="pu-multi-1",
                    project_id="proj-1",
                    user_id="user-123",
                    role="OWNER",
                    added_at=now,
                    added_by_user_id="user-123",
                )
            )
            conn.execute(
                sa.insert(project_users_table).values(
                    id="pu-multi-2",
                    project_id="proj-2",
                    user_id="user-123",
                    role="VIEWER",
                    added_at=now,
                    added_by_user_id="owner@example.com",
                )
            )
            conn.commit()

        # Act: Get user's project access
        db_session = db_session_factory()
        repo = ProjectUserRepository(db_session)
        result = repo.get_user_projects_access("user-123")
        db_session.close()

        # Assert
        assert len(result) == 2
        project_ids = [pu.project_id for pu in result]
        assert "proj-1" in project_ids
        assert "proj-2" in project_ids

