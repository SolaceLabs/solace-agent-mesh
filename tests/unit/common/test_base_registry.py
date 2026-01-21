"""
Unit tests for common/base_registry.py
Tests the BaseRegistry base class for managing discovered A2A entities.
"""

import pytest
import time
import threading
from unittest.mock import MagicMock
from a2a.types import AgentCard, AgentSkill

from solace_agent_mesh.common.base_registry import BaseRegistry


@pytest.fixture
def sample_card():
    """Create a sample AgentCard for testing."""
    return AgentCard(
        name="TestEntity",
        description="A test entity",
        url="https://test.example.com",
        version="1.0.0",
        protocolVersion="0.3.0",
        capabilities={
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        },
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
        skills=[
            AgentSkill(
                id="test-skill",
                name="Test Skill",
                description="A test skill",
                tags=["test"],
            )
        ],
    )


@pytest.fixture
def base_registry():
    """Create a fresh BaseRegistry instance for each test."""
    return BaseRegistry(entity_name="entity")


class TestBaseRegistryBasicOperations:
    """Test basic CRUD operations on BaseRegistry."""

    def test_add_new_entity(self, base_registry, sample_card):
        """Test adding a new entity to the registry."""
        is_new = base_registry.add_or_update(sample_card)

        assert is_new is True
        assert "TestEntity" in base_registry.get_ids()

        retrieved = base_registry.get("TestEntity")
        assert retrieved is not None
        assert retrieved.name == "TestEntity"
        assert retrieved.description == "A test entity"

    def test_update_existing_entity(self, base_registry, sample_card):
        """Test updating an existing entity in the registry."""
        is_new_first = base_registry.add_or_update(sample_card)
        assert is_new_first is True

        updated_card = sample_card.model_copy(update={"description": "Updated description"})
        is_new_second = base_registry.add_or_update(updated_card)

        assert is_new_second is False
        retrieved = base_registry.get("TestEntity")
        assert retrieved.description == "Updated description"

    def test_add_invalid_card(self, base_registry):
        """Test adding an invalid card (None or missing name)."""
        result = base_registry.add_or_update(None)
        assert result is False

        invalid_card = MagicMock()
        invalid_card.name = None
        result = base_registry.add_or_update(invalid_card)
        assert result is False

    def test_get_nonexistent_entity(self, base_registry):
        """Test retrieving an entity that doesn't exist."""
        result = base_registry.get("NonExistentEntity")
        assert result is None

    def test_get_ids_empty(self, base_registry):
        """Test getting IDs from empty registry."""
        ids = base_registry.get_ids()
        assert ids == []

    def test_get_ids_sorted(self, base_registry):
        """Test that IDs are returned in sorted order."""
        cards = [
            AgentCard(
                name=name,
                description=f"Entity {name}",
                url=f"https://{name}.example.com",
                version="1.0.0",
                protocolVersion="0.3.0",
                capabilities={"streaming": True},
                defaultInputModes=["text/plain"],
                defaultOutputModes=["text/plain"],
                skills=[],
            )
            for name in ["Zebra", "Alpha", "Mike", "Charlie"]
        ]

        for card in cards:
            base_registry.add_or_update(card)

        ids = base_registry.get_ids()
        assert ids == ["Alpha", "Charlie", "Mike", "Zebra"]

    def test_remove_existing_entity(self, base_registry, sample_card):
        """Test removing an existing entity from the registry."""
        base_registry.add_or_update(sample_card)

        result = base_registry.remove("TestEntity")
        assert result is True

        assert base_registry.get("TestEntity") is None
        assert "TestEntity" not in base_registry.get_ids()

    def test_remove_nonexistent_entity(self, base_registry):
        """Test removing an entity that doesn't exist."""
        result = base_registry.remove("NonExistentEntity")
        assert result is False

    def test_clear_registry(self, base_registry, sample_card):
        """Test clearing all entities from the registry."""
        for i in range(3):
            card = sample_card.model_copy(update={"name": f"TestEntity{i}"})
            base_registry.add_or_update(card)

        assert len(base_registry.get_ids()) == 3

        base_registry.clear()

        assert len(base_registry.get_ids()) == 0
        assert base_registry.get("TestEntity0") is None

    def test_len_method(self, base_registry, sample_card):
        """Test __len__ method."""
        assert len(base_registry) == 0

        base_registry.add_or_update(sample_card)
        assert len(base_registry) == 1

        card2 = sample_card.model_copy(update={"name": "AnotherEntity"})
        base_registry.add_or_update(card2)
        assert len(base_registry) == 2

    def test_contains_method(self, base_registry, sample_card):
        """Test __contains__ method."""
        assert "TestEntity" not in base_registry

        base_registry.add_or_update(sample_card)
        assert "TestEntity" in base_registry

    def test_bool_method_empty_registry(self, base_registry):
        """Test that empty registry is still truthy (for 'if registry is None' checks)."""
        assert len(base_registry) == 0
        assert bool(base_registry) is True
        assert base_registry  # Should not be falsy even when empty

    def test_bool_method_with_entities(self, base_registry, sample_card):
        """Test that registry with entities is truthy."""
        base_registry.add_or_update(sample_card)
        assert len(base_registry) == 1
        assert bool(base_registry) is True


class TestBaseRegistryHealthTracking:
    """Test health tracking and TTL functionality."""

    def test_last_seen_timestamp_on_add(self, base_registry, sample_card):
        """Test that last_seen timestamp is set when adding an entity."""
        before_time = time.time()
        base_registry.add_or_update(sample_card)
        after_time = time.time()

        last_seen = base_registry.get_last_seen("TestEntity")
        assert last_seen is not None
        assert before_time <= last_seen <= after_time

    def test_last_seen_timestamp_on_update(self, base_registry, sample_card):
        """Test that last_seen timestamp is updated when updating an entity."""
        base_registry.add_or_update(sample_card)
        first_seen = base_registry.get_last_seen("TestEntity")

        time.sleep(0.1)

        updated_card = sample_card.model_copy(update={"description": "Updated"})
        base_registry.add_or_update(updated_card)
        second_seen = base_registry.get_last_seen("TestEntity")

        assert second_seen > first_seen

    def test_get_last_seen_nonexistent(self, base_registry):
        """Test getting last_seen for an entity that doesn't exist."""
        result = base_registry.get_last_seen("NonExistentEntity")
        assert result is None

    def test_check_ttl_not_expired(self, base_registry, sample_card):
        """Test checking TTL for an entity that hasn't expired."""
        base_registry.add_or_update(sample_card)

        is_expired, seconds_since = base_registry.check_ttl_expired("TestEntity", ttl_seconds=60)

        assert is_expired is False
        assert seconds_since < 60

    def test_check_ttl_expired(self, base_registry, sample_card):
        """Test checking TTL for an entity that has expired."""
        base_registry.add_or_update(sample_card)

        base_registry._last_seen["TestEntity"] = time.time() - 100

        is_expired, seconds_since = base_registry.check_ttl_expired("TestEntity", ttl_seconds=60)

        assert is_expired is True
        assert seconds_since > 60

    def test_check_ttl_nonexistent(self, base_registry):
        """Test checking TTL for an entity that doesn't exist."""
        is_expired, seconds_since = base_registry.check_ttl_expired(
            "NonExistentEntity", ttl_seconds=60
        )

        assert is_expired is False
        assert seconds_since == 0



class TestBaseRegistryThreadSafety:
    """Test thread safety of BaseRegistry operations."""

    def test_concurrent_add_operations(self, base_registry):
        """Test concurrent add operations from multiple threads."""
        num_threads = 10
        entities_per_thread = 5

        def add_entities(thread_id):
            for i in range(entities_per_thread):
                card = AgentCard(
                    name=f"Entity_{thread_id}_{i}",
                    description=f"Entity from thread {thread_id}",
                    url=f"https://entity{thread_id}-{i}.example.com",
                    version="1.0.0",
                    protocolVersion="0.3.0",
                    capabilities={"streaming": True},
                    defaultInputModes=["text/plain"],
                    defaultOutputModes=["text/plain"],
                    skills=[],
                )
                base_registry.add_or_update(card)

        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=add_entities, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        ids = base_registry.get_ids()
        assert len(ids) == num_threads * entities_per_thread

    def test_concurrent_read_write_operations(self, base_registry, sample_card):
        """Test concurrent read and write operations."""
        base_registry.add_or_update(sample_card)

        results = {"reads": 0, "writes": 0}
        lock = threading.Lock()

        def read_entity():
            for _ in range(100):
                entity = base_registry.get("TestEntity")
                if entity:
                    with lock:
                        results["reads"] += 1

        def write_entity():
            for i in range(100):
                updated_card = sample_card.model_copy(update={"description": f"Update {i}"})
                base_registry.add_or_update(updated_card)
                with lock:
                    results["writes"] += 1

        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=read_entity))
            threads.append(threading.Thread(target=write_entity))

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert results["reads"] == 500
        assert results["writes"] == 500

        final_entity = base_registry.get("TestEntity")
        assert final_entity is not None
        assert final_entity.name == "TestEntity"


class TestBaseRegistryCallbacks:
    """Test callback functionality for entity additions and removals."""

    def test_on_added_callback_called_for_new_entity(self, sample_card):
        """Test that on_added callback is called when a new entity is added."""
        callback_invocations = []

        def on_added(card):
            callback_invocations.append(card.name)

        registry = BaseRegistry(entity_name="entity", on_added=on_added)
        registry.add_or_update(sample_card)

        assert len(callback_invocations) == 1
        assert callback_invocations[0] == "TestEntity"

    def test_on_added_callback_not_called_for_update(self, sample_card):
        """Test that on_added callback is NOT called when updating an existing entity."""
        callback_invocations = []

        def on_added(card):
            callback_invocations.append(card.name)

        registry = BaseRegistry(entity_name="entity", on_added=on_added)

        registry.add_or_update(sample_card)
        assert len(callback_invocations) == 1

        updated_card = sample_card.model_copy(update={"description": "Updated description"})
        registry.add_or_update(updated_card)

        assert len(callback_invocations) == 1

    def test_on_removed_callback_called(self, sample_card):
        """Test that on_removed callback is called when an entity is removed."""
        removal_invocations = []

        def on_removed(item_id):
            removal_invocations.append(item_id)

        registry = BaseRegistry(entity_name="entity", on_removed=on_removed)
        registry.add_or_update(sample_card)

        registry.remove("TestEntity")

        assert len(removal_invocations) == 1
        assert removal_invocations[0] == "TestEntity"

    def test_on_removed_callback_not_called_for_nonexistent(self):
        """Test that on_removed callback is NOT called when removing nonexistent entity."""
        removal_invocations = []

        def on_removed(item_id):
            removal_invocations.append(item_id)

        registry = BaseRegistry(entity_name="entity", on_removed=on_removed)

        registry.remove("NonExistentEntity")

        assert len(removal_invocations) == 0

    def test_callback_exception_handling_on_add(self, sample_card):
        """Test that exceptions in on_added callback are handled gracefully."""

        def failing_callback(card):
            raise ValueError("Callback failed!")

        registry = BaseRegistry(entity_name="entity", on_added=failing_callback)

        result = registry.add_or_update(sample_card)

        assert result is True
        assert registry.get("TestEntity") is not None

    def test_callback_exception_handling_on_remove(self, sample_card):
        """Test that exceptions in on_removed callback are handled gracefully."""

        def failing_callback(item_id):
            raise ValueError("Callback failed!")

        registry = BaseRegistry(entity_name="entity", on_removed=failing_callback)
        registry.add_or_update(sample_card)

        result = registry.remove("TestEntity")

        assert result is True
        assert registry.get("TestEntity") is None

    def test_set_callbacks_after_init(self, sample_card):
        """Test setting callbacks after initialization."""
        added_entities = []
        removed_entities = []

        registry = BaseRegistry(entity_name="entity")

        registry.set_on_added_callback(lambda card: added_entities.append(card.name))
        registry.set_on_removed_callback(lambda item_id: removed_entities.append(item_id))

        registry.add_or_update(sample_card)
        assert len(added_entities) == 1

        registry.remove("TestEntity")
        assert len(removed_entities) == 1


class TestBaseRegistryEntityName:
    """Test entity name customization for logging."""

    def test_entity_name_used_in_init(self):
        """Test that entity_name is stored correctly."""
        registry = BaseRegistry(entity_name="custom_entity")
        assert registry._entity_name == "custom_entity"

    def test_different_entity_names(self, sample_card):
        """Test creating registries with different entity names."""
        agent_registry = BaseRegistry(entity_name="agent")
        gateway_registry = BaseRegistry(entity_name="gateway")

        assert agent_registry._entity_name == "agent"
        assert gateway_registry._entity_name == "gateway"

        agent_registry.add_or_update(sample_card)
        gateway_registry.add_or_update(sample_card)

        assert len(agent_registry) == 1
        assert len(gateway_registry) == 1
