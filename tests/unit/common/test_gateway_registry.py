"""
Unit tests for common/gateway_registry.py
Tests the GatewayRegistry class for managing discovered A2A gateways.
Mirrors test_agent_registry.py structure for consistency.
"""

import pytest
import time
import threading
from unittest.mock import MagicMock
from a2a.types import AgentCard, AgentCapabilities, AgentExtension

from solace_agent_mesh.common.gateway_registry import GatewayRegistry


def create_test_gateway_card(
    gateway_id: str,
    gateway_type: str,
    namespace: str = "test/sam",
    deployment_id: str = None,
    description: str = None
) -> AgentCard:
    """Helper function to create test gateway cards."""
    extensions = [
        AgentExtension(
            uri="https://solace.com/a2a/extensions/sam/gateway-role",
            required=False,
            params={
                "gateway_id": gateway_id,
                "gateway_type": gateway_type,
                "namespace": namespace,
            }
        )
    ]

    if deployment_id:
        extensions.append(
            AgentExtension(
                uri="https://solace.com/a2a/extensions/sam/deployment",
                required=False,
                params={"deployment_id": deployment_id}
            )
        )

    return AgentCard(
        name=gateway_id,
        url=f"solace:{namespace}/a2a/v1/gateway/request/{gateway_id}",
        description=description or f"{gateway_type.upper()} Gateway",
        version="1.0.0",
        protocolVersion="1.0",
        capabilities={
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": False,
            "extensions": extensions,
        },
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
        skills=[],
    )


@pytest.fixture
def sample_gateway_card():
    """Create a sample gateway AgentCard for testing."""
    return create_test_gateway_card(
        gateway_id="TestGateway",
        gateway_type="http_sse",
        namespace="test/sam"
    )


@pytest.fixture
def sample_gateway_card_with_deployment():
    """Create a gateway card with deployment extension."""
    return create_test_gateway_card(
        gateway_id="TestGateway",
        gateway_type="http_sse",
        namespace="test/sam",
        deployment_id="k8s-pod-abc123"
    )


@pytest.fixture
def gateway_registry():
    """Create a fresh GatewayRegistry instance for each test."""
    return GatewayRegistry()


class TestGatewayRegistryBasicOperations:
    """Test basic CRUD operations on GatewayRegistry."""

    def test_add_new_gateway(self, gateway_registry, sample_gateway_card):
        """Test adding a new gateway to the registry."""
        is_new = gateway_registry.add_or_update_gateway(sample_gateway_card)

        assert is_new is True
        assert "TestGateway" in gateway_registry.get_gateway_ids()

        retrieved = gateway_registry.get_gateway("TestGateway")
        assert retrieved is not None
        assert retrieved.name == "TestGateway"
        assert retrieved.description == "HTTP_SSE Gateway"

    def test_update_existing_gateway(self, gateway_registry, sample_gateway_card):
        """Test updating an existing gateway in the registry."""
        is_new_first = gateway_registry.add_or_update_gateway(sample_gateway_card)
        assert is_new_first is True

        updated_card = sample_gateway_card.model_copy(
            update={"description": "Updated description"}
        )
        is_new_second = gateway_registry.add_or_update_gateway(updated_card)

        assert is_new_second is False
        retrieved = gateway_registry.get_gateway("TestGateway")
        assert retrieved.description == "Updated description"

    def test_add_invalid_gateway_card(self, gateway_registry):
        """Test adding an invalid gateway card (None or missing name)."""
        result = gateway_registry.add_or_update_gateway(None)
        assert result is False

        invalid_card = MagicMock()
        invalid_card.name = None
        result = gateway_registry.add_or_update_gateway(invalid_card)
        assert result is False

    def test_get_nonexistent_gateway(self, gateway_registry):
        """Test retrieving a gateway that doesn't exist."""
        result = gateway_registry.get_gateway("NonExistentGateway")
        assert result is None

    def test_get_gateway_ids_empty(self, gateway_registry):
        """Test getting gateway IDs from empty registry."""
        ids = gateway_registry.get_gateway_ids()
        assert ids == []

    def test_get_gateway_ids_sorted(self, gateway_registry):
        """Test that gateway IDs are returned in sorted order."""
        gateways = [
            create_test_gateway_card(name, "http_sse")
            for name in ["Zebra", "Alpha", "Mike", "Charlie"]
        ]

        for gateway in gateways:
            gateway_registry.add_or_update_gateway(gateway)

        ids = gateway_registry.get_gateway_ids()
        assert ids == ["Alpha", "Charlie", "Mike", "Zebra"]

    def test_remove_existing_gateway(self, gateway_registry, sample_gateway_card):
        """Test removing an existing gateway from the registry."""
        gateway_registry.add_or_update_gateway(sample_gateway_card)

        result = gateway_registry.remove_gateway("TestGateway")
        assert result is True

        assert gateway_registry.get_gateway("TestGateway") is None
        assert "TestGateway" not in gateway_registry.get_gateway_ids()

    def test_remove_nonexistent_gateway(self, gateway_registry):
        """Test removing a gateway that doesn't exist."""
        result = gateway_registry.remove_gateway("NonExistentGateway")
        assert result is False

    def test_clear_registry(self, gateway_registry):
        """Test clearing all gateways from the registry."""
        for i in range(3):
            card = create_test_gateway_card(f"Gateway{i}", "http_sse")
            gateway_registry.add_or_update_gateway(card)

        assert len(gateway_registry.get_gateway_ids()) == 3

        gateway_registry.clear()

        assert len(gateway_registry.get_gateway_ids()) == 0
        assert gateway_registry.get_gateway("Gateway0") is None


class TestGatewayRegistryHealthTracking:
    """Test health tracking and TTL functionality."""

    def test_last_seen_timestamp_on_add(self, gateway_registry, sample_gateway_card):
        """Test that last_seen timestamp is set when adding a gateway."""
        before_time = time.time()
        gateway_registry.add_or_update_gateway(sample_gateway_card)
        after_time = time.time()

        last_seen = gateway_registry.get_last_seen("TestGateway")
        assert last_seen is not None
        assert before_time <= last_seen <= after_time

    def test_last_seen_timestamp_on_update(self, gateway_registry, sample_gateway_card):
        """Test that last_seen timestamp is updated when updating a gateway."""
        gateway_registry.add_or_update_gateway(sample_gateway_card)
        first_seen = gateway_registry.get_last_seen("TestGateway")

        time.sleep(0.1)

        updated_card = sample_gateway_card.model_copy(
            update={"description": "Updated"}
        )
        gateway_registry.add_or_update_gateway(updated_card)
        second_seen = gateway_registry.get_last_seen("TestGateway")

        assert second_seen > first_seen

    def test_get_last_seen_nonexistent_gateway(self, gateway_registry):
        """Test getting last_seen for a gateway that doesn't exist."""
        result = gateway_registry.get_last_seen("NonExistentGateway")
        assert result is None

    def test_check_ttl_not_expired(self, gateway_registry, sample_gateway_card):
        """Test checking TTL for a gateway that hasn't expired."""
        gateway_registry.add_or_update_gateway(sample_gateway_card)

        is_expired, seconds_since = gateway_registry.check_ttl_expired(
            "TestGateway", ttl_seconds=90
        )

        assert is_expired is False
        assert seconds_since < 90

    def test_check_ttl_expired(self, gateway_registry, sample_gateway_card):
        """Test checking TTL for a gateway that has expired."""
        gateway_registry.add_or_update_gateway(sample_gateway_card)

        gateway_registry._last_seen["TestGateway"] = time.time() - 120

        is_expired, seconds_since = gateway_registry.check_ttl_expired(
            "TestGateway", ttl_seconds=90
        )

        assert is_expired is True
        assert seconds_since > 90

    def test_check_ttl_nonexistent_gateway(self, gateway_registry):
        """Test checking TTL for a gateway that doesn't exist."""
        is_expired, seconds_since = gateway_registry.check_ttl_expired(
            "NonExistentGateway", ttl_seconds=90
        )

        assert is_expired is False
        assert seconds_since == 0

    def test_default_ttl_90_seconds(self, gateway_registry, sample_gateway_card):
        """Test default TTL is 90 seconds."""
        gateway_registry.add_or_update_gateway(sample_gateway_card)
        gateway_registry._last_seen["TestGateway"] = time.time() - 91

        is_expired, _ = gateway_registry.check_ttl_expired("TestGateway")

        assert is_expired is True


class TestGatewayRegistryMetadataExtraction:
    """Test extraction of gateway-specific metadata from extensions."""

    def test_get_gateway_type(self, gateway_registry):
        """Test extracting gateway type from card."""
        card = create_test_gateway_card("gw-1", "http_sse")
        gateway_registry.add_or_update_gateway(card)

        gateway_type = gateway_registry.get_gateway_type("gw-1")
        assert gateway_type == "http_sse"

    def test_get_gateway_type_nonexistent(self, gateway_registry):
        """Test get_gateway_type for non-existent gateway."""
        result = gateway_registry.get_gateway_type("NonExistent")
        assert result is None

    def test_get_gateway_type_missing_extension(self, gateway_registry):
        """Test get_gateway_type when extension missing."""
        card = AgentCard(
            name="BadGateway",
            url="solace:test/sam/a2a/v1/gateway/request/BadGateway",
            description="Gateway without extension",
            version="1.0.0",
            protocolVersion="1.0",
            capabilities={
                "streaming": True,
                "pushNotifications": False,
                "stateTransitionHistory": False,
                "extensions": []
            },
            defaultInputModes=["text/plain"],
            defaultOutputModes=["text/plain"],
            skills=[]
        )
        gateway_registry.add_or_update_gateway(card)

        result = gateway_registry.get_gateway_type("BadGateway")
        assert result is None

    def test_get_gateway_namespace(self, gateway_registry):
        """Test extracting namespace from card."""
        card = create_test_gateway_card("gw-1", "http_sse", namespace="test/prod")
        gateway_registry.add_or_update_gateway(card)

        namespace = gateway_registry.get_gateway_namespace("gw-1")
        assert namespace == "test/prod"

    def test_get_gateway_namespace_nonexistent(self, gateway_registry):
        """Test get_gateway_namespace for non-existent gateway."""
        result = gateway_registry.get_gateway_namespace("NonExistent")
        assert result is None

    def test_get_deployment_id_present(self, gateway_registry):
        """Test extracting deployment ID when present."""
        card = create_test_gateway_card("gw-1", "http_sse", deployment_id="k8s-pod-123")
        gateway_registry.add_or_update_gateway(card)

        deployment_id = gateway_registry.get_deployment_id("gw-1")
        assert deployment_id == "k8s-pod-123"

    def test_get_deployment_id_absent(self, gateway_registry):
        """Test extracting deployment ID when absent."""
        card = create_test_gateway_card("gw-1", "http_sse")
        gateway_registry.add_or_update_gateway(card)

        deployment_id = gateway_registry.get_deployment_id("gw-1")
        assert deployment_id is None

    def test_get_deployment_id_nonexistent_gateway(self, gateway_registry):
        """Test get_deployment_id for non-existent gateway."""
        result = gateway_registry.get_deployment_id("NonExistent")
        assert result is None

    def test_multiple_gateway_types(self, gateway_registry):
        """Test registry handles multiple gateway types."""
        gateway_registry.add_or_update_gateway(create_test_gateway_card("gw-http", "http_sse"))
        gateway_registry.add_or_update_gateway(create_test_gateway_card("gw-slack", "slack"))
        gateway_registry.add_or_update_gateway(create_test_gateway_card("gw-rest", "rest"))

        assert gateway_registry.get_gateway_type("gw-http") == "http_sse"
        assert gateway_registry.get_gateway_type("gw-slack") == "slack"
        assert gateway_registry.get_gateway_type("gw-rest") == "rest"


class TestGatewayRegistryThreadSafety:
    """Test thread safety of GatewayRegistry operations."""

    def test_concurrent_add_operations(self, gateway_registry):
        """Test concurrent add from multiple threads."""
        num_threads = 10
        gateways_per_thread = 5

        def add_gateways(thread_id):
            for i in range(gateways_per_thread):
                card = create_test_gateway_card(
                    f"Gateway_{thread_id}_{i}",
                    "http_sse"
                )
                gateway_registry.add_or_update_gateway(card)

        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=add_gateways, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        ids = gateway_registry.get_gateway_ids()
        assert len(ids) == num_threads * gateways_per_thread

    def test_concurrent_read_write_operations(self, gateway_registry, sample_gateway_card):
        """Test concurrent read and write operations."""
        gateway_registry.add_or_update_gateway(sample_gateway_card)

        results = {"reads": 0, "writes": 0}
        lock = threading.Lock()

        def read_gateway():
            for _ in range(100):
                gateway = gateway_registry.get_gateway("TestGateway")
                if gateway:
                    with lock:
                        results["reads"] += 1

        def write_gateway():
            for i in range(100):
                updated_card = sample_gateway_card.model_copy(
                    update={"description": f"Update {i}"}
                )
                gateway_registry.add_or_update_gateway(updated_card)
                with lock:
                    results["writes"] += 1

        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=read_gateway))
            threads.append(threading.Thread(target=write_gateway))

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert results["reads"] == 500
        assert results["writes"] == 500

        final_gateway = gateway_registry.get_gateway("TestGateway")
        assert final_gateway is not None
        assert final_gateway.name == "TestGateway"

    def test_concurrent_remove_operations(self, gateway_registry):
        """Test concurrent remove operations."""
        for i in range(10):
            card = create_test_gateway_card(f"Gateway_{i}", "http_sse")
            gateway_registry.add_or_update_gateway(card)

        def remove_gateways(start_idx, end_idx):
            for i in range(start_idx, end_idx):
                gateway_registry.remove_gateway(f"Gateway_{i}")

        threads = [
            threading.Thread(target=remove_gateways, args=(0, 5)),
            threading.Thread(target=remove_gateways, args=(5, 10)),
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(gateway_registry.get_gateway_ids()) == 0

    def test_concurrent_health_checks(self, gateway_registry):
        """Test concurrent TTL checks."""
        for i in range(5):
            card = create_test_gateway_card(f"Gateway_{i}", "http_sse")
            gateway_registry.add_or_update_gateway(card)

        check_count = {"count": 0}
        lock = threading.Lock()

        def check_health():
            for gateway_id in gateway_registry.get_gateway_ids():
                gateway_registry.check_ttl_expired(gateway_id, ttl_seconds=90)
                with lock:
                    check_count["count"] += 1

        threads = []
        for _ in range(10):
            thread = threading.Thread(target=check_health)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert check_count["count"] == 50


class TestGatewayRegistryEdgeCases:
    """Test edge cases and error conditions."""

    def test_add_gateway_with_empty_name(self, gateway_registry):
        """Test adding gateway with empty name."""
        card = create_test_gateway_card("", "http_sse")

        result = gateway_registry.add_or_update_gateway(card)
        assert result is False

    def test_multiple_updates_preserve_last_seen(self, gateway_registry, sample_gateway_card):
        """Test rapid updates preserve last_seen tracking."""
        timestamps = []

        for i in range(5):
            gateway_registry.add_or_update_gateway(sample_gateway_card)
            timestamps.append(gateway_registry.get_last_seen("TestGateway"))
            time.sleep(0.05)

        for i in range(1, len(timestamps)):
            assert timestamps[i] >= timestamps[i-1]

    def test_remove_gateway_clears_last_seen(self, gateway_registry, sample_gateway_card):
        """Test removing gateway clears tracking data."""
        gateway_registry.add_or_update_gateway(sample_gateway_card)
        assert gateway_registry.get_last_seen("TestGateway") is not None

        gateway_registry.remove_gateway("TestGateway")
        assert gateway_registry.get_last_seen("TestGateway") is None

    def test_clear_removes_all_tracking_data(self, gateway_registry):
        """Test clear() removes gateways and tracking."""
        for i in range(3):
            card = create_test_gateway_card(f"Gateway{i}", "http_sse")
            gateway_registry.add_or_update_gateway(card)

        for i in range(3):
            assert gateway_registry.get_last_seen(f"Gateway{i}") is not None

        gateway_registry.clear()

        for i in range(3):
            assert gateway_registry.get_last_seen(f"Gateway{i}") is None

    def test_gateway_with_multiple_extensions(self, gateway_registry):
        """Test gateway with gateway-role + deployment extensions."""
        card = create_test_gateway_card("gw-1", "http_sse", deployment_id="k8s-pod-123")
        gateway_registry.add_or_update_gateway(card)

        assert gateway_registry.get_gateway_type("gw-1") == "http_sse"
        assert gateway_registry.get_deployment_id("gw-1") == "k8s-pod-123"

    def test_gateway_with_only_gateway_role_extension(self, gateway_registry):
        """Test gateway with only gateway-role extension."""
        card = create_test_gateway_card("gw-1", "http_sse")
        gateway_registry.add_or_update_gateway(card)

        assert gateway_registry.get_gateway_type("gw-1") == "http_sse"
        assert gateway_registry.get_deployment_id("gw-1") is None


class TestGatewayRegistryCallbacks:
    """Test callback functionality for gateway lifecycle."""

    def test_on_gateway_added_callback_called_for_new(self, sample_gateway_card):
        """Test callback called when new gateway added."""
        callback_invocations = []

        def on_added(agent_card):
            callback_invocations.append(agent_card.name)

        registry = GatewayRegistry(on_gateway_added=on_added)
        registry.add_or_update_gateway(sample_gateway_card)

        assert len(callback_invocations) == 1
        assert callback_invocations[0] == "TestGateway"

    def test_on_gateway_added_callback_not_called_for_update(self, sample_gateway_card):
        """Test callback NOT called for updates."""
        callback_invocations = []

        def on_added(agent_card):
            callback_invocations.append(agent_card.name)

        registry = GatewayRegistry(on_gateway_added=on_added)

        registry.add_or_update_gateway(sample_gateway_card)
        assert len(callback_invocations) == 1

        updated_card = sample_gateway_card.model_copy(
            update={"description": "Updated description"}
        )
        registry.add_or_update_gateway(updated_card)

        assert len(callback_invocations) == 1

    def test_on_gateway_removed_callback_called(self, sample_gateway_card):
        """Test callback called when gateway removed."""
        removal_invocations = []

        def on_removed(gateway_id):
            removal_invocations.append(gateway_id)

        registry = GatewayRegistry(on_gateway_removed=on_removed)
        registry.add_or_update_gateway(sample_gateway_card)

        registry.remove_gateway("TestGateway")

        assert len(removal_invocations) == 1
        assert removal_invocations[0] == "TestGateway"

    def test_on_gateway_removed_callback_not_called_for_nonexistent(self):
        """Test callback NOT called for non-existent removal."""
        removal_invocations = []

        def on_removed(gateway_id):
            removal_invocations.append(gateway_id)

        registry = GatewayRegistry(on_gateway_removed=on_removed)

        registry.remove_gateway("NonExistentGateway")

        assert len(removal_invocations) == 0

    def test_callbacks_with_both_add_and_remove(self, sample_gateway_card):
        """Test both callbacks work together."""
        added_gateways = []
        removed_gateways = []

        def on_added(agent_card):
            added_gateways.append(agent_card.name)

        def on_removed(gateway_id):
            removed_gateways.append(gateway_id)

        registry = GatewayRegistry(
            on_gateway_added=on_added,
            on_gateway_removed=on_removed
        )

        for i in range(3):
            card = create_test_gateway_card(f"Gateway{i}", "http_sse")
            registry.add_or_update_gateway(card)

        assert len(added_gateways) == 3
        assert added_gateways == ["Gateway0", "Gateway1", "Gateway2"]

        registry.remove_gateway("Gateway1")

        assert len(removed_gateways) == 1
        assert removed_gateways[0] == "Gateway1"

    def test_callback_exception_handling_on_add(self, sample_gateway_card):
        """Test exceptions in callbacks handled gracefully."""
        def failing_callback(agent_card):
            raise ValueError("Callback failed!")

        registry = GatewayRegistry(on_gateway_added=failing_callback)

        result = registry.add_or_update_gateway(sample_gateway_card)

        assert result is True
        assert registry.get_gateway("TestGateway") is not None

    def test_callback_exception_handling_on_remove(self, sample_gateway_card):
        """Test exceptions in remove callback handled gracefully."""
        def failing_callback(gateway_id):
            raise ValueError("Callback failed!")

        registry = GatewayRegistry(on_gateway_removed=failing_callback)
        registry.add_or_update_gateway(sample_gateway_card)

        result = registry.remove_gateway("TestGateway")

        assert result is True
        assert registry.get_gateway("TestGateway") is None

    def test_callbacks_are_optional(self, sample_gateway_card):
        """Test registry works without callbacks."""
        registry = GatewayRegistry()

        result = registry.add_or_update_gateway(sample_gateway_card)
        assert result is True

        result = registry.remove_gateway("TestGateway")
        assert result is True

    def test_callback_receives_correct_gateway_card(self, sample_gateway_card):
        """Test callback receives actual gateway card object."""
        received_cards = []

        def on_added(agent_card):
            received_cards.append(agent_card)

        registry = GatewayRegistry(on_gateway_added=on_added)
        registry.add_or_update_gateway(sample_gateway_card)

        assert len(received_cards) == 1
        received_card = received_cards[0]

        assert received_card.name == "TestGateway"
        assert received_card.description == "HTTP_SSE Gateway"
        assert received_card.version == "1.0.0"

    def test_callback_invoked_outside_lock(self, sample_gateway_card):
        """Test callbacks invoked outside lock (no deadlock)."""
        registry_ref = []

        def on_added(agent_card):
            if registry_ref:
                ids = registry_ref[0].get_gateway_ids()
                assert agent_card.name in ids

        registry = GatewayRegistry(on_gateway_added=on_added)
        registry_ref.append(registry)

        registry.add_or_update_gateway(sample_gateway_card)

    def test_callback_thread_safety(self, sample_gateway_card):
        """Test callbacks work with concurrent operations."""
        added_gateways = []
        lock = threading.Lock()

        def on_added(agent_card):
            with lock:
                added_gateways.append(agent_card.name)

        registry = GatewayRegistry(on_gateway_added=on_added)

        def add_gateways(thread_id):
            for i in range(5):
                card = create_test_gateway_card(
                    f"Gateway_{thread_id}_{i}",
                    "http_sse"
                )
                registry.add_or_update_gateway(card)

        threads = []
        for i in range(3):
            thread = threading.Thread(target=add_gateways, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(added_gateways) == 15
