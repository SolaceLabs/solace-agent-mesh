"""
Data validation and edge case tests for persistence framework.

Tests handling of invalid data, boundary conditions, and security concerns.
"""

import json

import pytest
import sqlalchemy as sa

from ..infrastructure.database_inspector import DatabaseInspector
from ..infrastructure.gateway_adapter import GatewayAdapter


class TestDataValidation:
    """Tests for data validation and security"""

    @pytest.mark.xfail(
        reason="SessionResponse model validation intercepts the IntegrityError from the database."
    )
    def test_empty_and_null_data_handling(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Test handling of empty and null data"""

        # Test null user_id (should raise IntegrityError)
        with pytest.raises(sa.exc.IntegrityError):
            gateway_adapter.create_session(user_id=None, agent_name="TestAgent")

        # Test null agent_name (should raise IntegrityError)
        with pytest.raises(sa.exc.IntegrityError):
            gateway_adapter.create_session(user_id="test_user", agent_name=None)

        # Test empty message content
        session = gateway_adapter.create_session(
            user_id="test_user", agent_name="TestAgent"
        )

        # Empty message should be handled gracefully
        response = gateway_adapter.send_message(session.id, "")
        assert response.user_message == ""
        assert response.session_id == session.id

    def test_boundary_conditions(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Test boundary conditions for data limits"""

        # Test very long user_id
        long_user_id = "user_" + "x" * 1000
        session = gateway_adapter.create_session(
            user_id=long_user_id, agent_name="TestAgent"
        )

        # Verify it was stored correctly
        sessions = database_inspector.get_gateway_sessions(long_user_id)
        assert len(sessions) == 1
        assert sessions[0].user_id == long_user_id

        # Test very long message content
        long_message = "Long message: " + "x" * 10000
        response = gateway_adapter.send_message(session.id, long_message)
        assert long_message in response.user_message

        # Verify message was persisted
        messages = database_inspector.get_session_messages(session.id)
        assert len(messages) >= 2
        assert messages[0].user_message == long_message

    def test_special_characters_and_encoding(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Test special characters, Unicode, and encoding issues"""

        # Test Unicode characters
        unicode_user = "用户_🚀_test"
        unicode_message = "Hello 世界! 🎉 Émojis and spëcial chars: <>\"'&"

        session = gateway_adapter.create_session(
            user_id=unicode_user, agent_name="TestAgent"
        )

        response = gateway_adapter.send_message(session.id, unicode_message)
        assert unicode_message in response.user_message

        # Verify Unicode data persisted correctly
        sessions = database_inspector.get_gateway_sessions(unicode_user)
        assert len(sessions) == 1
        assert sessions[0].user_id == unicode_user

        messages = database_inspector.get_session_messages(session.id)
        assert messages[0].user_message == unicode_message

    def test_sql_injection_prevention(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Test SQL injection prevention"""

        # Test SQL injection attempts in user_id
        malicious_user = "user'; DROP TABLE sessions; --"
        session = gateway_adapter.create_session(
            user_id=malicious_user, agent_name="TestAgent"
        )

        # Verify table still exists and data is safe
        sessions = database_inspector.get_gateway_sessions(malicious_user)
        assert len(sessions) == 1

        # Test SQL injection in message content
        malicious_message = "Hello'; DELETE FROM chat_tasks; --"
        gateway_adapter.send_message(session.id, malicious_message)

        # Verify data integrity
        messages = database_inspector.get_session_messages(session.id)
        assert len(messages) >= 2
        assert messages[0].user_message == malicious_message


class TestErrorRecovery:
    """Tests for error recovery and resilience"""

    def test_corrupted_session_handling(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Test handling of corrupted or inconsistent session data"""

        # Create a normal session first
        session = gateway_adapter.create_session(
            user_id="test_user", agent_name="TestAgent"
        )

        # Manually corrupt session data in database (simulate corruption)
        with database_inspector.db_manager.get_gateway_connection() as conn:
            query = sa.text(
                "UPDATE sessions SET agent_id = :agent_id WHERE id = :session_id"
            )
            conn.execute(
                query,
                {"agent_id": "CorruptedAgent", "session_id": session.id},
            )
            if conn.in_transaction():
                conn.commit()

        # Try to send message to corrupted session (should handle gracefully)
        try:
            response = gateway_adapter.send_message(
                session.id, "Message to corrupted session"
            )
            assert response.session_id == session.id
        except Exception as e:
            assert "not found" in str(e).lower() or "corrupted" in str(e).lower()

    def test_concurrent_access_conflicts(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Test concurrent access and potential race conditions"""

        session = gateway_adapter.create_session(
            user_id="concurrent_user", agent_name="TestAgent"
        )

        # Simulate concurrent message sending
        responses = []
        for i in range(10):
            response = gateway_adapter.send_message(
                session.id, f"Concurrent message {i}"
            )
            responses.append(response)

        # Verify all messages were processed
        assert len(responses) == 10
        for i, response in enumerate(responses):
            assert f"message {i}" in response.user_message.lower()

        # Verify database consistency
        db_messages = database_inspector.get_session_messages(session.id)
        assert len(db_messages) == 20


class TestResourceLimits:
    """Tests for resource limits and performance boundaries"""

    def test_large_session_counts(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Test handling of large numbers of sessions"""

        user_id = "heavy_user"
        session_count = 50

        # Create many sessions
        sessions = []
        for _i in range(session_count):
            session = gateway_adapter.create_session(
                user_id=user_id,
                agent_name="TestAgent",
            )
            sessions.append(session)

        # Verify all sessions were created
        user_sessions = database_inspector.get_gateway_sessions(user_id)
        assert len(user_sessions) == session_count

        # Test session retrieval
        session_list = gateway_adapter.list_sessions(user_id)
        assert len(session_list) == session_count

    def test_message_volume_handling(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Test handling of high message volumes"""

        session = gateway_adapter.create_session(
            user_id="volume_user", agent_name="TestAgent"
        )

        message_count = 100

        # Send many messages
        for i in range(message_count):
            gateway_adapter.send_message(session.id, f"Volume test message {i}")

        # Verify all messages were persisted
        messages = database_inspector.get_session_messages(session.id)
        assert len(messages) == message_count * 2

        # Verify message ordering
        for i in range(message_count):
            user_message = messages[i * 2]
            agent_message = messages[i * 2 + 1]
            expected_content = f"Volume test message {i}"
            assert user_message.user_message == expected_content
            assert agent_message.user_message == f"Received: {expected_content}"


class TestDataIntegrity:
    """Tests for data integrity and consistency"""

    def test_transaction_consistency(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Test transaction consistency during operations"""

        session = gateway_adapter.create_session(
            user_id="transaction_user", agent_name="TestAgent"
        )

        # Send message (this involves multiple DB operations)
        gateway_adapter.send_message(session.id, "Transaction test message")

        # Verify both user and agent messages exist (transaction succeeded)
        messages = database_inspector.get_session_messages(session.id)
        assert len(messages) >= 2

        # Verify message consistency
        user_msg = messages[0]
        bubbles = json.loads(user_msg.message_bubbles)
        assert bubbles[0]["role"] == "user"
        assert bubbles[0]["text"] == "Transaction test message"

    def test_referential_integrity(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Test referential integrity between sessions and messages"""

        session = gateway_adapter.create_session(
            user_id="integrity_user", agent_name="TestAgent"
        )

        # Send messages
        gateway_adapter.send_message(session.id, "Message 1")
        gateway_adapter.send_message(session.id, "Message 2")

        # Verify messages exist
        messages = database_inspector.get_session_messages(session.id)
        assert len(messages) == 4

        # Delete session (should cascade to messages)
        deleted = gateway_adapter.delete_session(session.id)
        assert deleted

        # Verify messages were also deleted (referential integrity)
        remaining_messages = database_inspector.get_session_messages(session.id)
        assert len(remaining_messages) == 0
