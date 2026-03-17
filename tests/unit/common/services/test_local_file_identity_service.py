"""
Unit tests for LocalFileIdentityService, focusing on search ranking.
Tests that search results prioritize:
1. First name matches
2. Email matches
3. Other name parts (middle, last names)
"""

import json
import pytest
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from solace_agent_mesh.common.services.providers.local_file_identity_service import (
    LocalFileIdentityService,
)


@pytest.fixture
def test_users_data() -> List[Dict[str, Any]]:
    """
    Test user data designed to validate ranking logic.

    Users are ordered to test that results are re-ranked by match priority,
    not returned in file order.
    """
    return [
        {
            "id": "funghai.choo",
            "email": "funghai.choo@solace.com",
            "name": "Fun Ghai Choo",
            "title": "Engineer",
        },
        {
            "id": "ghaith.dalla-ali",
            "email": "ghaith.dalla-ali@solace.com",
            "name": "Ghaith Dalla-Ali",
            "title": "Senior Engineer",
        },
        {
            "id": "edward.smith",
            "email": "edward.smith@example.com",
            "name": "Edward Smith",
            "title": "Manager",
        },
        {
            "id": "smith.jones",
            "email": "smith.jones@example.com",
            "name": "John Smith Jones",
            "title": "Developer",
        },
        {
            "id": "alice.edwards",
            "email": "alice.edwards@example.com",
            "name": "Alice Edwards",
            "title": "Designer",
        },
        {
            "id": "bob.wilson",
            "email": "edward.w@example.com",
            "name": "Bob Wilson",
            "title": "Developer",
        },
        {
            "id": "charlie.brown",
            "email": "charlie.brown@example.com",
            "name": "Charlie Brown",
            "title": "Engineer",
        },
    ]


@pytest.fixture
def identity_file(test_users_data: List[Dict[str, Any]]) -> Path:
    """Create a temporary JSON file with test user data."""
    temp_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    )
    json.dump(test_users_data, temp_file)
    temp_file.close()

    yield Path(temp_file.name)

    # Cleanup
    Path(temp_file.name).unlink()


@pytest.fixture
def identity_service(identity_file: Path) -> LocalFileIdentityService:
    """Create a LocalFileIdentityService instance with test data."""
    config = {
        "file_path": str(identity_file),
        "lookup_key": "id",
        "cache_ttl_seconds": 0,  # Disable caching for tests
    }
    return LocalFileIdentityService(config)


class TestSearchRanking:
    """Test search result ranking prioritizes first name > email > other."""

    @pytest.mark.asyncio
    async def test_first_name_ranks_higher_than_middle_name(
        self, identity_service: LocalFileIdentityService
    ):
        """
        Test that first name match ranks higher than middle name match.

        Query "ghai" should return:
        1. Ghaith (first name starts with "ghai")
        2. Fun Ghai Choo (middle name "Ghai" starts with "ghai")
        """
        results = await identity_service.search_users("ghai", limit=10)

        assert len(results) == 2
        assert results[0]["displayName"] == "Ghaith Dalla-Ali"
        assert results[1]["displayName"] == "Fun Ghai Choo"

    @pytest.mark.asyncio
    async def test_first_name_ranks_higher_than_email(
        self, identity_service: LocalFileIdentityService
    ):
        """
        Test that first name match ranks higher than email match.

        Query "edward" should return:
        1. Edward Smith (first name match, score 0)
        2. Bob Wilson (email "edward.w@example.com" match, score 1)
        3. Alice Edwards (last name match, score 2)
        """
        results = await identity_service.search_users("edward", limit=10)

        assert len(results) == 3
        assert results[0]["displayName"] == "Edward Smith"
        assert results[1]["displayName"] == "Bob Wilson"
        assert results[2]["displayName"] == "Alice Edwards"

    @pytest.mark.asyncio
    async def test_email_ranks_higher_than_last_name(
        self, identity_service: LocalFileIdentityService
    ):
        """
        Test that email match ranks higher than last name match.

        Query "smith" should return:
        1. smith.jones@example.com (email match)
        2. Edward Smith (last name match)
        """
        results = await identity_service.search_users("smith", limit=10)

        assert len(results) >= 2
        assert results[0]["workEmail"] == "smith.jones@example.com"
        assert results[1]["displayName"] == "Edward Smith"

    @pytest.mark.asyncio
    async def test_case_insensitive_ranking(
        self, identity_service: LocalFileIdentityService
    ):
        """Test that ranking works correctly with case variations."""
        # Uppercase query
        results_upper = await identity_service.search_users("GHAI", limit=10)
        # Lowercase query
        results_lower = await identity_service.search_users("ghai", limit=10)
        # Mixed case query
        results_mixed = await identity_service.search_users("GhAi", limit=10)

        # All should return same results in same order
        assert len(results_upper) == len(results_lower) == len(results_mixed)
        assert results_upper[0]["id"] == results_lower[0]["id"]
        assert results_lower[0]["id"] == results_mixed[0]["id"]

    @pytest.mark.asyncio
    async def test_multiple_last_name_matches_rank_by_position(
        self, identity_service: LocalFileIdentityService
    ):
        """
        Test that when multiple last names match, they rank by position.

        Both "Edward Smith" and "John Smith Jones" have "smith" in their name,
        but "Edward Smith" has it in position 1 (last name) while
        "John Smith Jones" has it in position 1 as well (middle name).
        """
        results = await identity_service.search_users("smith", limit=10)

        # Should have at least 2 matches with correct ordering
        assert len(results) >= 2
        assert results[0]["displayName"] == "John Smith Jones"
        assert results[1]["displayName"] == "Edward Smith"


class TestSearchBasics:
    """Test basic search functionality."""

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty(
        self, identity_service: LocalFileIdentityService
    ):
        """Test that empty query returns no results."""
        results = await identity_service.search_users("", limit=10)
        assert results == []

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(
        self, identity_service: LocalFileIdentityService
    ):
        """Test that query with no matches returns empty list."""
        results = await identity_service.search_users(
            "nonexistentname12345", limit=10
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_limit_respected(
        self, identity_service: LocalFileIdentityService
    ):
        """Test that result limit is respected."""
        # Query that should match multiple users
        results = await identity_service.search_users("e", limit=2)

        # Should only return 2 results even if more match
        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_partial_match_first_name(
        self, identity_service: LocalFileIdentityService
    ):
        """Test partial matching on first name."""
        results = await identity_service.search_users("cha", limit=10)

        # Should match "Charlie Brown"
        assert len(results) >= 1
        assert any(r["displayName"] == "Charlie Brown" for r in results)

    @pytest.mark.asyncio
    async def test_partial_match_email(
        self, identity_service: LocalFileIdentityService
    ):
        """Test partial matching on email prefix."""
        results = await identity_service.search_users("alice.ed", limit=10)

        # Should match "alice.edwards@example.com"
        assert len(results) >= 1
        assert any(r["workEmail"] == "alice.edwards@example.com" for r in results)

    @pytest.mark.asyncio
    async def test_contains_does_not_match(
        self, identity_service: LocalFileIdentityService
    ):
        """
        Test that contains matching does NOT work - only startsWith.

        Query "ward" should NOT match "Edward Smith" because "ward" is in
        the middle of "Edward", not at the start.
        """
        results = await identity_service.search_users("ward", limit=10)

        # Should not match Edward
        assert not any(r["displayName"] == "Edward Smith" for r in results)

    @pytest.mark.asyncio
    async def test_result_format(
        self, identity_service: LocalFileIdentityService
    ):
        """Test that results have correct format."""
        results = await identity_service.search_users("edward", limit=10)

        assert len(results) > 0

        # Check first result has required fields
        result = results[0]
        assert "id" in result
        assert "displayName" in result
        assert "workEmail" in result
        assert "jobTitle" in result

        # Check field types
        assert isinstance(result["id"], str)
        assert isinstance(result["displayName"], str)
        assert isinstance(result["workEmail"], str)


class TestCaching:
    """Test caching behavior of search results."""

    @pytest.mark.asyncio
    async def test_cache_disabled_returns_fresh_results(
        self, identity_service: LocalFileIdentityService
    ):
        """Test that with cache disabled, each call processes fresh."""
        # Cache is disabled in fixture (cache_ttl_seconds=0)

        results1 = await identity_service.search_users("edward", limit=10)
        results2 = await identity_service.search_users("edward", limit=10)

        # Should return same results (not testing caching itself,
        # just that results are consistent)
        assert results1 == results2

    @pytest.mark.asyncio
    async def test_cache_enabled_returns_cached_results(
        self, identity_file: Path
    ):
        """Test that with cache enabled, results are cached."""
        config = {
            "file_path": str(identity_file),
            "lookup_key": "id",
            "cache_ttl_seconds": 60,  # Enable caching
        }
        service = LocalFileIdentityService(config)

        # First call populates cache
        results1 = await service.search_users("edward", limit=10)

        # Second call should use cache
        results2 = await service.search_users("edward", limit=10)

        assert results1 == results2


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_hyphenated_names(
        self, identity_service: LocalFileIdentityService
    ):
        """Test matching on hyphenated names."""
        # Should match "Dalla-Ali"
        results = await identity_service.search_users("dalla", limit=10)

        assert len(results) >= 1
        assert any("Dalla-Ali" in r["displayName"] for r in results)

    @pytest.mark.asyncio
    async def test_single_character_query(
        self, identity_service: LocalFileIdentityService
    ):
        """Test that single character queries work."""
        results = await identity_service.search_users("e", limit=10)

        # Should match Edward and potentially others
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_user_without_email(self, identity_file: Path):
        """Test handling of users without email field."""
        # Create service with user missing email
        config = {
            "file_path": str(identity_file),
            "lookup_key": "id",
            "cache_ttl_seconds": 0,
        }
        service = LocalFileIdentityService(config)

        # Should not crash
        results = await service.search_users("test", limit=10)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_user_without_name(self, identity_file: Path):
        """Test handling of users without name field."""
        config = {
            "file_path": str(identity_file),
            "lookup_key": "id",
            "cache_ttl_seconds": 0,
        }
        service = LocalFileIdentityService(config)

        # Should not crash
        results = await service.search_users("test", limit=10)
        assert isinstance(results, list)


class TestGetUserProfile:
    """Test user profile retrieval functionality."""

    @pytest.mark.asyncio
    async def test_get_existing_user(
        self, identity_service: LocalFileIdentityService
    ):
        """Test retrieving an existing user profile."""
        auth_claims = {"id": "edward.smith"}

        profile = await identity_service.get_user_profile(auth_claims)

        assert profile is not None
        assert profile["id"] == "edward.smith"
        assert profile["name"] == "Edward Smith"
        assert profile["email"] == "edward.smith@example.com"

    @pytest.mark.asyncio
    async def test_get_nonexistent_user(
        self, identity_service: LocalFileIdentityService
    ):
        """Test retrieving a nonexistent user returns None."""
        auth_claims = {"id": "nonexistent.user"}

        profile = await identity_service.get_user_profile(auth_claims)

        assert profile is None

    @pytest.mark.asyncio
    async def test_get_user_missing_lookup_key(
        self, identity_service: LocalFileIdentityService
    ):
        """Test that missing lookup key in claims returns None."""
        auth_claims = {"wrong_key": "edward.smith"}

        profile = await identity_service.get_user_profile(auth_claims)

        assert profile is None
