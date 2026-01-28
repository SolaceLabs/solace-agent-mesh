"""
Test concurrent session handling with authentication enabled.

This test verifies that when authentication is enabled, multiple concurrent
sessions from different users maintain proper isolation and don't interfere
with each other.
"""

import asyncio
import pytest
import uuid
from fastapi.testclient import TestClient
from ..infrastructure.gateway_adapter import GatewayAdapter

# Custom header for test user identification
TEST_USER_HEADER = "X-Test-User-Id"


@pytest.mark.all
@pytest.mark.asyncio
@pytest.mark.api
@pytest.mark.gateway
async def test_concurrent_sessions_with_different_users(
    api_client: TestClient, gateway_adapter: GatewayAdapter, api_client_factory
):
    """
    Test that concurrent sessions from different users maintain proper isolation.
    
    This test verifies that when multiple users make CONCURRENT requests,
    each user receives their own response without cross-contamination.
    
    Note: Uses asyncio.gather() to create truly concurrent operations,
    simulating multiple users with proper database persistence.
    """
    scenario_id = "concurrent_sessions_with_auth_001"
    print(f"\nRunning scenario: {scenario_id}")
    
    # Create a HeaderBasedTestClient class for creating user-specific clients
    class HeaderBasedTestClient(TestClient):
        def __init__(self, app, user_id: str):
            super().__init__(app)
            self.test_user_id = user_id

        def request(self, method, url, **kwargs):
            # Inject user ID via custom header for every request
            if "headers" not in kwargs or kwargs["headers"] is None:
                kwargs["headers"] = {}
            kwargs["headers"][TEST_USER_HEADER] = self.test_user_id
            return super().request(method, url, **kwargs)
    
    # Create 3 different user sessions (simulating different users)
    num_users = 3
    
    # Create async function for session creation
    async def create_user_session(user_id: str, user_index: int):
        """Create session for a single user concurrently."""
        session = await asyncio.to_thread(
            gateway_adapter.create_session,
            user_id=user_id,
            agent_name="TestAgent"
        )
        await asyncio.to_thread(
            gateway_adapter.send_message,
            session.id,
            f"Initial message for user {user_index}"
        )
        user_client = HeaderBasedTestClient(api_client_factory.app, user_id)
        print(f"Created session {session.id} for user {user_index}")
        return {
            "user_id": user_index,
            "user_id_str": user_id,
            "session_id": session.id,
            "client": user_client,
        }
    
    # Create sessions CONCURRENTLY using asyncio.gather
    print(f"Creating {num_users} sessions concurrently...")
    user_sessions = await asyncio.gather(*[
        create_user_session(f"test_user_{i}", i)
        for i in range(num_users)
    ])
    
    # Send follow-up messages from each user CONCURRENTLY
    print(f"\nSending follow-up messages from {num_users} users concurrently...")
    
    async def send_followup(user_info):
        """Send follow-up message for a user concurrently."""
        user_id = user_info["user_id"]
        session_id = user_info["session_id"]
        await asyncio.to_thread(
            gateway_adapter.send_message,
            session_id,
            f"Follow-up message from user {user_id}"
        )
        print(f"✓ User {user_id} sent follow-up message to session {session_id}")
    
    await asyncio.gather(*[send_followup(user_info) for user_info in user_sessions])
    
    # Verify each session has the correct message history
    print(f"\nVerifying message history for each user...")
    
    for user_info in user_sessions:
        user_id = user_info["user_id"]
        session_id = user_info["session_id"]
        user_client = user_info["client"]
        
        # Use the user-specific client to fetch history
        history_response = user_client.get(f"/api/v1/sessions/{session_id}/messages")
        assert history_response.status_code == 200, (
            f"Failed to get history for user {user_id}. Response: {history_response.status_code} - {history_response.text}"
        )
        
        history = history_response.json()
        
        # Debug: Print what we got
        print(f"User {user_id} history: {len(history)} messages")
        
        # Verify the session contains messages for this specific user
        all_message_contents = [msg.get("message", "") for msg in history]
        
        # Check for user-specific messages
        assert f"Initial message for user {user_id}" in all_message_contents, (
            f"User {user_id} session missing initial message. Got messages: {all_message_contents}"
        )
        assert f"Follow-up message from user {user_id}" in all_message_contents, (
            f"User {user_id} session missing follow-up message. Got messages: {all_message_contents}"
        )
        
        # Verify no cross-contamination from other users
        for other_user_id in range(num_users):
            if other_user_id != user_id:
                # Messages from other users should NOT be in this session
                other_user_initial = f"Initial message for user {other_user_id}"
                other_user_followup = f"Follow-up message from user {other_user_id}"
                
                assert other_user_initial not in all_message_contents, (
                    f"User {user_id} session contaminated with user {other_user_id} initial message"
                )
                assert other_user_followup not in all_message_contents, (
                    f"User {user_id} session contaminated with user {other_user_id} follow-up message"
                )
        
        print(f"✓ User {user_id} session has correct isolated history")
    
    print(f"\nScenario {scenario_id}: All concurrent sessions properly isolated ✓")


@pytest.mark.all
@pytest.mark.asyncio
@pytest.mark.api
@pytest.mark.gateway
async def test_concurrent_session_creation(api_client: TestClient):
    """
    Test that multiple users can create sessions CONCURRENTLY without conflicts.
    
    Note: Uses asyncio.gather() to create truly concurrent session creation requests.
    """
    scenario_id = "concurrent_session_creation_001"
    print(f"\nRunning scenario: {scenario_id}")
    
    num_users = 5
    
    # Create async function for session creation
    async def create_session_via_api(user_index: int):
        """Create a session via API call concurrently."""
        task_payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [
                        {"kind": "text", "text": f"Session creation test user {user_index}"}
                    ],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        }
        
        response = await asyncio.to_thread(
            api_client.post,
            "/api/v1/message:stream",
            json=task_payload
        )
        return {
            "user_index": user_index,
            "status_code": response.status_code,
            "session_id": response.json()["result"]["contextId"] if response.status_code == 200 else None,
        }
    
    # Create sessions CONCURRENTLY using asyncio.gather
    print(f"Creating {num_users} sessions concurrently...")
    results = await asyncio.gather(*[
        create_session_via_api(i)
        for i in range(num_users)
    ])
    
    # Verify all sessions were created successfully
    assert len(results) == num_users
    
    session_ids = set()
    for result in results:
        assert result["status_code"] == 200, (
            f"User {result['user_index']} failed to create session"
        )
        assert result["session_id"] is not None
        session_ids.add(result["session_id"])
    
    # Verify all session IDs are unique (no collisions)
    assert len(session_ids) == num_users, (
        f"Expected {num_users} unique sessions, "
        f"but got {len(session_ids)} (possible ID collision)"
    )
    
    print(f"✓ Created {num_users} unique sessions")
    print(f"Scenario {scenario_id}: Session creation successful ✓")


@pytest.mark.all
@pytest.mark.asyncio
@pytest.mark.api
@pytest.mark.gateway
async def test_session_isolation_under_load(api_client: TestClient, api_client_factory, gateway_adapter: GatewayAdapter):
    """
    Test session isolation under load with CONCURRENT requests.
    
    This test creates multiple sessions and sends multiple CONCURRENT
    messages to verify that session state remains isolated under true concurrent load.
    
    Note: Uses asyncio.gather() to create truly concurrent operations.
    """
    scenario_id = "session_isolation_under_load_001"
    print(f"\nRunning scenario: {scenario_id}")
    
    # Create a HeaderBasedTestClient class for creating user-specific clients
    class HeaderBasedTestClient(TestClient):
        def __init__(self, app, user_id: str):
            super().__init__(app)
            self.test_user_id = user_id

        def request(self, method, url, **kwargs):
            # Inject user ID via custom header for every request
            if "headers" not in kwargs or kwargs["headers"] is None:
                kwargs["headers"] = {}
            kwargs["headers"][TEST_USER_HEADER] = self.test_user_id
            return super().request(method, url, **kwargs)
    
    num_users = 3
    messages_per_user = 5
    
    # Create async function for session creation
    async def create_user_session(user_index: int):
        """Create session for a single user concurrently."""
        user_id = f"test_user_{user_index}"
        user_client = HeaderBasedTestClient(api_client_factory.app, user_id)
        
        # Create session directly in database with correct user_id
        session = await asyncio.to_thread(
            gateway_adapter.create_session,
            user_id=user_id,
            agent_name="TestAgent"
        )
        session_id = session.id
        
        # Send initial message via gateway_adapter to ensure it's in the database
        await asyncio.to_thread(
            gateway_adapter.send_message,
            session_id,
            f"Load test user {user_index} - initial"
        )
        
        print(f"Created session {session_id} for user {user_id}")
        return {"user_id": user_index, "user_id_str": user_id, "session_id": session_id, "client": user_client}
    
    # Create sessions CONCURRENTLY
    print(f"Creating {num_users} sessions concurrently...")
    user_sessions = await asyncio.gather(*[
        create_user_session(i)
        for i in range(num_users)
    ])
    
    # Send multiple messages from each user CONCURRENTLY
    print(f"Sending {num_users * messages_per_user} messages concurrently...")
    
    async def send_message_async(user_info, msg_num: int):
        """Send a message for a user concurrently."""
        user_id = user_info["user_id"]
        session_id = user_info["session_id"]
        
        await asyncio.to_thread(
            gateway_adapter.send_message,
            session_id,
            f"User {user_id} message {msg_num}"
        )
        print(f"✓ User {user_id} sent message {msg_num} to session {session_id}")
    
    # Create all message sending tasks (interleaved from different users)
    message_tasks = []
    for msg_num in range(messages_per_user):
        for user_info in user_sessions:
            message_tasks.append(send_message_async(user_info, msg_num))
    
    # Execute all message sends CONCURRENTLY
    await asyncio.gather(*message_tasks)
    
    print(f"✓ All {num_users * messages_per_user} messages sent successfully")
    
    # Verify session isolation - each session should have only its own messages
    for user_info in user_sessions:
        user_id = user_info["user_id"]
        user_id_str = user_info["user_id_str"]
        session_id = user_info["session_id"]
        user_client = user_info["client"]
        
        # Use the user-specific client to fetch history
        history_response = user_client.get(f"/api/v1/sessions/{session_id}/messages")
        assert history_response.status_code == 200, (
            f"Failed to get history for user {user_id} ({user_id_str}). "
            f"Response: {history_response.status_code}, Body: {history_response.text}"
        )
        
        history = history_response.json()
        all_message_contents = [msg.get("message", "") for msg in history]
        
        # Count messages for this user (including both user and agent messages)
        user_message_count = sum(
            1 for msg in all_message_contents
            if f"User {user_id}" in msg or f"Load test user {user_id}" in msg
        )
        
        # Should have initial message + messages_per_user messages + agent responses
        # Each send_message creates 2 messages (user + agent), so we expect at least:
        # (1 initial + messages_per_user) * 2 messages
        expected_min = (1 + messages_per_user) * 2
        assert user_message_count >= expected_min, (
            f"User {user_id} expected at least {expected_min} messages, "
            f"found {user_message_count}. Messages: {all_message_contents}"
        )
        
        # Verify no messages from other users leaked in
        for other_user_id in range(num_users):
            if other_user_id != user_id:
                other_user_messages = sum(
                    1 for msg in all_message_contents
                    if f"User {other_user_id}" in msg or f"Load test user {other_user_id}" in msg
                )
                assert other_user_messages == 0, (
                    f"User {user_id} session contaminated with "
                    f"{other_user_messages} messages from user {other_user_id}"
                )
        
        print(f"✓ User {user_id} session isolated with {user_message_count} messages")
    
    print(f"Scenario {scenario_id}: Session isolation maintained under load ✓")
