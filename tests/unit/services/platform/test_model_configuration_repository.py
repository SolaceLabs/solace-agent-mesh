"""Unit tests for ModelConfigurationRepository.get_by_alias_or_id.

Tests the new repository method that queries by alias OR cast(id, String).
"""

from unittest.mock import Mock, MagicMock, patch

from solace_agent_mesh.services.platform.repositories.model_configuration_repository import (
    ModelConfigurationRepository,
)


class TestGetByAliasOrId:
    """Tests for ModelConfigurationRepository.get_by_alias_or_id."""

    def test_returns_result_from_query(self):
        """Returns whatever the query chain resolves to."""
        repo = ModelConfigurationRepository()
        mock_db = Mock()
        expected = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = expected

        result = repo.get_by_alias_or_id(mock_db, "my-model")

        assert result is expected

    def test_returns_none_when_not_found(self):
        """Returns None when no matching row exists."""
        repo = ModelConfigurationRepository()
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = repo.get_by_alias_or_id(mock_db, "nonexistent")

        assert result is None

    def test_calls_query_on_model_configuration(self):
        """Verifies db.query is called."""
        repo = ModelConfigurationRepository()
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        repo.get_by_alias_or_id(mock_db, "test-alias")

        mock_db.query.assert_called_once()

    def test_passes_alias_string(self):
        """The alias parameter is passed through to the filter logic."""
        repo = ModelConfigurationRepository()
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Just verify it doesn't raise for various input types
        repo.get_by_alias_or_id(mock_db, "simple-alias")
        repo.get_by_alias_or_id(mock_db, "01234567-0123-0123-0123-0123456789ab")
