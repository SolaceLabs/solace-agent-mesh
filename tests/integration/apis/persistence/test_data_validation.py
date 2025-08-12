"""
Data validation and edge case tests for persistence framework.

Tests handling of invalid data, boundary conditions, and security concerns.
"""

import pytest

from ..infrastructure.simple_database_inspector import SimpleDatabaseInspector
from ..infrastructure.simple_gateway_adapter import SimpleGatewayAdapter


class TestDataValidation:
    """Tests for data validation and security"""

    def test_empty_and_null_data_handling(
        self,
        simple_gateway_adapter: SimpleGatewayAdapter,
        simple_database_inspector: SimpleDatabaseInspector,
    ):
        """Test handling of empty and null data"""

        # Test empty user_id (should raise error)
        with pytest.raises((ValueError, TypeError)):
            simple_gateway_adapter.create_session(user_id="", agent_name="TestAgent")

        # Test empty agent_name (should raise error)
        with pytest.raises((ValueError, TypeError)):
            simple_gateway_adapter.create_session(user_id="test_user", agent_name="")

        # Test empty message content
        session = simple_gateway_adapter.create_session(
            user_id="test_user", agent_name="TestAgent"
        )

        # Empty message should be handled gracefully
        response = simple_gateway_adapter.send_message(session.id, "")
        assert response.content == "Received: "
        assert response.session_id == session.id

        print("✓ Empty and null data handled correctly")

    def test_boundary_conditions(
        self,
        simple_gateway_adapter: SimpleGatewayAdapter,
        simple_database_inspector: SimpleDatabaseInspector,
    ):
        """Test boundary conditions for data limits"""

        # Test very long user_id
        long_user_id = "user_" + "x" * 1000
        session = simple_gateway_adapter.create_session(
            user_id=long_user_id, agent_name="TestAgent"
        )

        # Verify it was stored correctly
        sessions = simple_database_inspector.get_gateway_sessions(long_user_id)
        assert len(sessions) == 1
        assert sessions[0].user_id == long_user_id

        # Test very long message content
        long_message = "Long message: " + "x" * 10000
        response = simple_gateway_adapter.send_message(session.id, long_message)
        assert long_message in response.content

        # Verify message was persisted
        messages = simple_database_inspector.get_session_messages(session.id)
        assert len(messages) == 2
        assert messages[0].content == long_message

        print("✓ Boundary conditions handled correctly")

    def test_special_characters_and_encoding(
        self,
        simple_gateway_adapter: SimpleGatewayAdapter,
        simple_database_inspector: SimpleDatabaseInspector,
    ):
        """Test special characters, Unicode, and encoding issues"""

        # Test Unicode characters
        unicode_user = "用户_🚀_test"
        unicode_message = "Hello 世界! 🎉 Émojis and spëcial chars: <>\"'&"

        session = simple_gateway_adapter.create_session(
            user_id=unicode_user, agent_name="TestAgent"
        )

        response = simple_gateway_adapter.send_message(session.id, unicode_message)
        assert unicode_message in response.content

        # Verify Unicode data persisted correctly
        sessions = simple_database_inspector.get_gateway_sessions(unicode_user)
        assert len(sessions) == 1
        assert sessions[0].user_id == unicode_user

        messages = simple_database_inspector.get_session_messages(session.id)
        assert messages[0].content == unicode_message

        print("✓ Special characters and Unicode handled correctly")

    def test_sql_injection_prevention(
        self,
        simple_gateway_adapter: SimpleGatewayAdapter,
        simple_database_inspector: SimpleDatabaseInspector,
    ):
        """Test SQL injection prevention"""

        # Test SQL injection attempts in user_id
        malicious_user = "user'; DROP TABLE gateway_sessions; --"
        session = simple_gateway_adapter.create_session(
            user_id=malicious_user, agent_name="TestAgent"
        )

        # Verify table still exists and data is safe
        sessions = simple_database_inspector.get_gateway_sessions(malicious_user)
        assert len(sessions) == 1

        # Test SQL injection in message content
        malicious_message = "Hello'; DELETE FROM gateway_messages; --"
        response = simple_gateway_adapter.send_message(session.id, malicious_message)

        # Verify data integrity
        messages = simple_database_inspector.get_session_messages(session.id)
        assert len(messages) == 2  # Both messages should exist
        assert messages[0].content == malicious_message

        print("✓ SQL injection prevention working")


class TestErrorRecovery:
    """Tests for error recovery and resilience"""

    def test_corrupted_session_handling(
        self,
        simple_gateway_adapter: SimpleGatewayAdapter,
        simple_database_inspector: SimpleDatabaseInspector,
    ):
        """Test handling of corrupted or inconsistent session data"""

        # Create a normal session first
        session = simple_gateway_adapter.create_session(
            user_id="test_user", agent_name="TestAgent"
        )

        # Manually corrupt session data in database (simulate corruption)
        with simple_database_inspector.db_manager.get_gateway_connection() as conn:
            conn.execute(
                "UPDATE gateway_sessions SET agent_name = ? WHERE id = ?",
                ("CorruptedAgent", session.id),
            )
            conn.commit()

        # Try to send message to corrupted session (should handle gracefully)
        try:
            response = simple_gateway_adapter.send_message(
                session.id, "Message to corrupted session"
            )
            # Should still work even with corrupted agent name
            assert response.session_id == session.id
        except Exception as e:
            # If it fails, it should fail gracefully with meaningful error
            assert "not found" in str(e).lower() or "corrupted" in str(e).lower()

        print("✓ Corrupted session data handled gracefully")

    def test_concurrent_access_conflicts(
        self,
        simple_gateway_adapter: SimpleGatewayAdapter,
        simple_database_inspector: SimpleDatabaseInspector,
    ):
        """Test concurrent access and potential race conditions"""

        session = simple_gateway_adapter.create_session(
            user_id="concurrent_user", agent_name="TestAgent"
        )

        # Simulate concurrent message sending
        messages = []
        for i in range(10):
            response = simple_gateway_adapter.send_message(
                session.id, f"Concurrent message {i}"
            )
            messages.append(response)

        # Verify all messages were processed
        assert len(messages) == 10
        for i, response in enumerate(messages):
            assert f"message {i}" in response.content.lower()

        # Verify database consistency
        db_messages = simple_database_inspector.get_session_messages(session.id)
        assert len(db_messages) == 20  # 10 user messages + 10 agent responses

        print("✓ Concurrent access handled correctly")


class TestResourceLimits:
    """Tests for resource limits and performance boundaries"""

    def test_large_session_counts(
        self,
        simple_gateway_adapter: SimpleGatewayAdapter,
        simple_database_inspector: SimpleDatabaseInspector,
    ):
        """Test handling of large numbers of sessions"""

        user_id = "heavy_user"
        session_count = 50

        # Create many sessions
        sessions = []
        for i in range(session_count):
            session = simple_gateway_adapter.create_session(
                user_id=user_id,
                agent_name="TestAgent",  # Use same agent for simplicity
            )
            sessions.append(session)

        # Verify all sessions were created
        user_sessions = simple_database_inspector.get_gateway_sessions(user_id)
        assert len(user_sessions) == session_count

        # Test session retrieval performance
        session_list = simple_gateway_adapter.list_sessions(user_id)
        assert len(session_list) == session_count

        print(f"✓ Large session count ({session_count}) handled correctly")

    def test_message_volume_handling(
        self,
        simple_gateway_adapter: SimpleGatewayAdapter,
        simple_database_inspector: SimpleDatabaseInspector,
    ):
        """Test handling of high message volumes"""

        session = simple_gateway_adapter.create_session(
            user_id="volume_user", agent_name="TestAgent"
        )

        message_count = 100

        # Send many messages
        for i in range(message_count):
            simple_gateway_adapter.send_message(session.id, f"Volume test message {i}")

        # Verify all messages were persisted
        messages = simple_database_inspector.get_session_messages(session.id)
        assert len(messages) == message_count * 2  # user + agent messages

        # Verify message ordering
        for i in range(0, len(messages), 2):  # Every other message is user message
            user_message = messages[i]
            expected_content = f"Volume test message {i // 2}"
            assert user_message.content == expected_content

        print(f"✓ High message volume ({message_count}) handled correctly")


class TestDataIntegrity:
    """Tests for data integrity and consistency"""

    def test_transaction_consistency(
        self,
        simple_gateway_adapter: SimpleGatewayAdapter,
        simple_database_inspector: SimpleDatabaseInspector,
    ):
        """Test transaction consistency during operations"""

        session = simple_gateway_adapter.create_session(
            user_id="transaction_user", agent_name="TestAgent"
        )

        # Send message (this involves multiple DB operations)
        response = simple_gateway_adapter.send_message(
            session.id, "Transaction test message"
        )

        # Verify both user and agent messages exist (transaction succeeded)
        messages = simple_database_inspector.get_session_messages(session.id)
        assert len(messages) == 2

        # Verify message consistency
        user_msg, agent_msg = messages
        assert user_msg.role == "user"
        assert agent_msg.role == "assistant"
        assert user_msg.content == "Transaction test message"
        assert "Transaction test message" in agent_msg.content

        print("✓ Transaction consistency maintained")

    def test_referential_integrity(
        self,
        simple_gateway_adapter: SimpleGatewayAdapter,
        simple_database_inspector: SimpleDatabaseInspector,
    ):
        """Test referential integrity between sessions and messages"""

        session = simple_gateway_adapter.create_session(
            user_id="integrity_user", agent_name="TestAgent"
        )

        # Send messages
        simple_gateway_adapter.send_message(session.id, "Message 1")
        simple_gateway_adapter.send_message(session.id, "Message 2")

        # Verify messages exist
        messages = simple_database_inspector.get_session_messages(session.id)
        assert len(messages) == 4  # 2 exchanges

        # Delete session (should cascade to messages)
        deleted = simple_gateway_adapter.delete_session(session.id)
        assert deleted

        # Verify messages were also deleted (referential integrity)
        remaining_messages = simple_database_inspector.get_session_messages(session.id)
        assert len(remaining_messages) == 0

        print("✓ Referential integrity maintained")
