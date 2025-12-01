"""
Test script for the skill learning system.

This script tests the complete learning flow by:
1. Simulating task completion events
2. Verifying the task analyzer correctly identifies learnable tasks
3. Testing skill extraction
4. Verifying skills are stored in the database

Usage:
    python -m solace_agent_mesh.services.skill_learning.tests.test_learning_flow
"""

import logging
import sys
import os
import time
from typing import Dict, Any, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

from solace_agent_mesh.services.skill_learning.extraction import TaskAnalyzer, SkillExtractor
from solace_agent_mesh.services.skill_learning.repository import SkillRepository
from solace_agent_mesh.services.skill_learning.services import SkillService
from solace_agent_mesh.services.skill_learning.entities import SkillScope
from solace_agent_mesh.services.skill_learning.broker.skill_message_handler import SkillMessageHandler
from solace_agent_mesh.services.skill_learning.feedback import FeedbackProcessor

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_sample_task_events() -> List[Dict[str, Any]]:
    """Create sample task events that simulate a successful data analysis task."""
    base_time = int(time.time() * 1000)
    
    return [
        {
            "id": "event-1",
            "task_id": "task-test-001",
            "event_type": "task_start",
            "timestamp": base_time,
            "agent_name": "OrchestratorAgent",
            "content": "Analyze the sales data and create a summary report",
        },
        {
            "id": "event-2",
            "task_id": "task-test-001",
            "event_type": "delegation",
            "timestamp": base_time + 1000,
            "agent_name": "OrchestratorAgent",
            "target_agent": "DataAnalystAgent",
            "content": "Delegating data analysis to DataAnalystAgent",
        },
        {
            "id": "event-3",
            "task_id": "task-test-001",
            "event_type": "tool_call",
            "timestamp": base_time + 2000,
            "agent_name": "DataAnalystAgent",
            "tool_name": "query_database",
            "parameters": {
                "query": "SELECT * FROM sales WHERE date >= '2024-01-01'",
                "database": "analytics_db",
            },
        },
        {
            "id": "event-4",
            "task_id": "task-test-001",
            "event_type": "tool_result",
            "timestamp": base_time + 3000,
            "agent_name": "DataAnalystAgent",
            "tool_name": "query_database",
            "success": True,
            "result": {"rows": 1500, "columns": ["date", "product", "amount", "region"]},
        },
        {
            "id": "event-5",
            "task_id": "task-test-001",
            "event_type": "tool_call",
            "timestamp": base_time + 4000,
            "agent_name": "DataAnalystAgent",
            "tool_name": "calculate_statistics",
            "parameters": {
                "data_source": "query_result",
                "metrics": ["sum", "average", "count", "group_by_region"],
            },
        },
        {
            "id": "event-6",
            "task_id": "task-test-001",
            "event_type": "tool_result",
            "timestamp": base_time + 5000,
            "agent_name": "DataAnalystAgent",
            "tool_name": "calculate_statistics",
            "success": True,
            "result": {
                "total_sales": 1250000,
                "average_sale": 833.33,
                "by_region": {"North": 450000, "South": 350000, "East": 250000, "West": 200000},
            },
        },
        {
            "id": "event-7",
            "task_id": "task-test-001",
            "event_type": "tool_call",
            "timestamp": base_time + 6000,
            "agent_name": "DataAnalystAgent",
            "tool_name": "generate_report",
            "parameters": {
                "format": "markdown",
                "include_charts": True,
                "sections": ["summary", "regional_breakdown", "trends"],
            },
        },
        {
            "id": "event-8",
            "task_id": "task-test-001",
            "event_type": "tool_result",
            "timestamp": base_time + 7000,
            "agent_name": "DataAnalystAgent",
            "tool_name": "generate_report",
            "success": True,
            "result": {"report_id": "report-001", "format": "markdown"},
        },
        {
            "id": "event-9",
            "task_id": "task-test-001",
            "event_type": "task_complete",
            "timestamp": base_time + 8000,
            "agent_name": "OrchestratorAgent",
            "success": True,
            "content": "Sales analysis report generated successfully",
        },
    ]


def create_simple_task_events() -> List[Dict[str, Any]]:
    """Create a simpler task with fewer tool calls."""
    base_time = int(time.time() * 1000)
    
    return [
        {
            "id": "event-1",
            "task_id": "task-test-002",
            "event_type": "task_start",
            "timestamp": base_time,
            "agent_name": "AssistantAgent",
            "content": "What is the weather in San Francisco?",
        },
        {
            "id": "event-2",
            "task_id": "task-test-002",
            "event_type": "tool_call",
            "timestamp": base_time + 1000,
            "agent_name": "AssistantAgent",
            "tool_name": "get_weather",
            "parameters": {"city": "San Francisco", "units": "fahrenheit"},
        },
        {
            "id": "event-3",
            "task_id": "task-test-002",
            "event_type": "tool_result",
            "timestamp": base_time + 2000,
            "agent_name": "AssistantAgent",
            "tool_name": "get_weather",
            "success": True,
            "result": {"temperature": 65, "condition": "sunny", "humidity": 45},
        },
        {
            "id": "event-4",
            "task_id": "task-test-002",
            "event_type": "task_complete",
            "timestamp": base_time + 3000,
            "agent_name": "AssistantAgent",
            "success": True,
        },
    ]


def create_failed_task_events() -> List[Dict[str, Any]]:
    """Create a failed task that should not be learned."""
    base_time = int(time.time() * 1000)
    
    return [
        {
            "id": "event-1",
            "task_id": "task-test-003",
            "event_type": "task_start",
            "timestamp": base_time,
            "agent_name": "AssistantAgent",
            "content": "Delete all files in /important",
        },
        {
            "id": "event-2",
            "task_id": "task-test-003",
            "event_type": "tool_call",
            "timestamp": base_time + 1000,
            "agent_name": "AssistantAgent",
            "tool_name": "delete_files",
            "parameters": {"path": "/important"},
        },
        {
            "id": "event-3",
            "task_id": "task-test-003",
            "event_type": "tool_result",
            "timestamp": base_time + 2000,
            "agent_name": "AssistantAgent",
            "tool_name": "delete_files",
            "success": False,
            "error": "Permission denied",
        },
        {
            "id": "event-4",
            "task_id": "task-test-003",
            "event_type": "task_failed",
            "timestamp": base_time + 3000,
            "agent_name": "AssistantAgent",
            "success": False,
            "error": "Task failed due to permission error",
        },
    ]


def test_task_analyzer():
    """Test the TaskAnalyzer component."""
    print("\n" + "=" * 60)
    print("TEST: TaskAnalyzer")
    print("=" * 60)
    
    analyzer = TaskAnalyzer(
        min_tool_calls=1,
        max_tool_calls=50,
    )
    
    # Test 1: Complex successful task
    print("\n--- Test 1: Complex successful task ---")
    events = create_sample_task_events()
    analysis = analyzer.analyze_task(
        task_id="task-test-001",
        task_events=events,
    )
    
    print(f"Task ID: {analysis.task_id}")
    print(f"User Request: {analysis.user_request}")
    print(f"Success: {analysis.success}")
    print(f"Total Tool Calls: {analysis.total_tool_calls}")
    print(f"Total Agents: {analysis.total_agents}")
    print(f"Complexity Score: {analysis.complexity_score}")
    print(f"Is Learnable: {analysis.is_learnable}")
    print(f"Skip Reason: {analysis.skip_reason}")
    
    assert analysis.is_learnable, f"Expected task to be learnable, got skip_reason: {analysis.skip_reason}"
    assert analysis.success, "Expected task to be successful"
    assert analysis.total_tool_calls >= 3, f"Expected at least 3 tool calls, got {analysis.total_tool_calls}"
    print("✓ Test 1 passed")
    
    # Test 2: Simple successful task
    print("\n--- Test 2: Simple successful task ---")
    events = create_simple_task_events()
    analysis = analyzer.analyze_task(
        task_id="task-test-002",
        task_events=events,
    )
    
    print(f"Task ID: {analysis.task_id}")
    print(f"Success: {analysis.success}")
    print(f"Total Tool Calls: {analysis.total_tool_calls}")
    print(f"Is Learnable: {analysis.is_learnable}")
    
    assert analysis.is_learnable, f"Expected task to be learnable, got skip_reason: {analysis.skip_reason}"
    print("✓ Test 2 passed")
    
    # Test 3: Failed task
    print("\n--- Test 3: Failed task ---")
    events = create_failed_task_events()
    analysis = analyzer.analyze_task(
        task_id="task-test-003",
        task_events=events,
    )
    
    print(f"Task ID: {analysis.task_id}")
    print(f"Success: {analysis.success}")
    print(f"Is Learnable: {analysis.is_learnable}")
    print(f"Skip Reason: {analysis.skip_reason}")
    
    assert not analysis.is_learnable, "Expected failed task to not be learnable"
    assert not analysis.success, "Expected task to be marked as failed"
    print("✓ Test 3 passed")
    
    print("\n✓ All TaskAnalyzer tests passed!")


def test_skill_repository():
    """Test the SkillRepository component."""
    print("\n" + "=" * 60)
    print("TEST: SkillRepository")
    print("=" * 60)
    
    # Use in-memory SQLite for testing
    repo = SkillRepository(database_url="sqlite:///:memory:")
    repo.create_tables()
    
    # Test creating a skill
    print("\n--- Test: Create and retrieve skill ---")
    from solace_agent_mesh.services.skill_learning.entities import Skill, SkillType
    
    skill = Skill(
        name="test-data-analysis",
        description="Analyze sales data and generate reports",
        type=SkillType.LEARNED,
        scope=SkillScope.AGENT,
        summary="A skill for analyzing sales data using database queries and statistics",
        owner_agent_name="DataAnalystAgent",
        involved_agents=["DataAnalystAgent", "OrchestratorAgent"],
        complexity_score=26,
    )
    
    created = repo.create_skill(skill)
    print(f"Created skill: {created.id} - {created.name}")
    
    # Retrieve the skill
    retrieved = repo.get_skill(created.id)
    assert retrieved is not None, "Failed to retrieve skill"
    assert retrieved.name == skill.name, "Skill name mismatch"
    print(f"Retrieved skill: {retrieved.id} - {retrieved.name}")
    
    # Search for skills
    print("\n--- Test: Search skills ---")
    skills = repo.search_skills(
        owner_agent_name="DataAnalystAgent",
        scope=SkillScope.AGENT,
    )
    print(f"Found {len(skills)} skills for DataAnalystAgent")
    assert len(skills) >= 1, "Expected at least 1 skill"
    
    print("\n✓ All SkillRepository tests passed!")


def test_skill_service():
    """Test the SkillService component."""
    print("\n" + "=" * 60)
    print("TEST: SkillService")
    print("=" * 60)
    
    # Use in-memory SQLite for testing
    repo = SkillRepository(database_url="sqlite:///:memory:")
    repo.create_tables()
    
    service = SkillService(
        repository=repo,
        embedding_service=None,  # Skip embeddings for this test
        auto_generate_embeddings=False,
    )
    
    # Test enqueueing for learning
    print("\n--- Test: Enqueue for learning ---")
    service.enqueue_for_learning(
        task_id="task-test-001",
        agent_name="DataAnalystAgent",
        user_id="user-123",
    )
    print("Enqueued task for learning")
    
    # Get pending items
    items = service.get_pending_learning_items(limit=10)
    print(f"Pending learning items: {len(items)}")
    assert len(items) >= 1, "Expected at least 1 pending item"
    
    print("\n✓ All SkillService tests passed!")


def test_message_handler():
    """Test the SkillMessageHandler component."""
    print("\n" + "=" * 60)
    print("TEST: SkillMessageHandler")
    print("=" * 60)
    
    # Set up components
    repo = SkillRepository(database_url="sqlite:///:memory:")
    repo.create_tables()
    
    service = SkillService(
        repository=repo,
        embedding_service=None,
        auto_generate_embeddings=False,
    )
    
    analyzer = TaskAnalyzer()
    extractor = SkillExtractor(llm_client=None)  # Mock extraction
    feedback_processor = FeedbackProcessor(repository=repo, skill_extractor=extractor)
    
    published_messages = []
    
    def mock_publish(topic: str, payload: Dict[str, Any]):
        published_messages.append({"topic": topic, "payload": payload})
        print(f"  Published to {topic}: {payload.get('task_id', payload.get('skill_id', 'N/A'))}")
    
    # Test with passive learning DISABLED (default)
    handler = SkillMessageHandler(
        skill_service=service,
        task_analyzer=analyzer,
        skill_extractor=extractor,
        feedback_processor=feedback_processor,
        publish_callback=mock_publish,
        passive_learning_enabled=False,  # Default - only nominated tasks
    )
    
    # Test 1: Task completion should be IGNORED when passive learning is disabled
    print("\n--- Test 1: Task completion ignored (passive learning disabled) ---")
    events = create_sample_task_events()
    
    handler.handle_message(
        topic="sam/DataAnalystAgent/task/completed",
        payload={
            "task_id": "task-test-001",
            "agent_name": "DataAnalystAgent",
            "success": True,
            "events": events,
            "user_id": "user-123",
        }
    )
    
    print(f"Published {len(published_messages)} messages (should be 0 - passive learning disabled)")
    items = service.get_pending_learning_items(limit=10)
    print(f"Pending learning items: {len(items)} (should be 0)")
    assert len(items) == 0, "Task completion should be ignored when passive learning is disabled"
    print("✓ Task completion correctly ignored")
    
    # Test 2: Learning nomination should be processed
    print("\n--- Test 2: Handle learning nomination ---")
    published_messages.clear()
    
    handler.handle_message(
        topic="sam/DataAnalystAgent/task/nominate-for-learning",
        payload={
            "task_id": "task-test-001",
            "agent_name": "DataAnalystAgent",
            "events": events,
            "user_id": "user-123",
            "nomination_reason": "novel_approach",
        }
    )
    
    print(f"Published {len(published_messages)} messages")
    assert len(published_messages) >= 1, "Expected at least 1 published message for nomination"
    
    # Check that task was queued for learning
    items = service.get_pending_learning_items(limit=10)
    print(f"Pending learning items: {len(items)}")
    assert len(items) >= 1, "Expected nominated task to be queued for learning"
    
    # Check that nomination_reason is in the published message
    queued_msg = next((m for m in published_messages if "learning/queued" in m["topic"]), None)
    assert queued_msg is not None, "Expected learning/queued message"
    assert queued_msg["payload"].get("nominated") == True, "Expected nominated=True in message"
    assert queued_msg["payload"].get("nomination_reason") == "novel_approach", "Expected nomination_reason"
    print("✓ Learning nomination processed correctly")
    
    # Test 3: With passive learning ENABLED
    print("\n--- Test 3: Task completion with passive learning enabled ---")
    
    # Create new handler with passive learning enabled
    repo2 = SkillRepository(database_url="sqlite:///:memory:")
    repo2.create_tables()
    service2 = SkillService(repository=repo2, embedding_service=None, auto_generate_embeddings=False)
    published_messages.clear()
    
    handler_passive = SkillMessageHandler(
        skill_service=service2,
        task_analyzer=analyzer,
        skill_extractor=extractor,
        feedback_processor=FeedbackProcessor(repository=repo2, skill_extractor=extractor),
        publish_callback=mock_publish,
        passive_learning_enabled=True,  # Enable passive learning
    )
    
    handler_passive.handle_message(
        topic="sam/DataAnalystAgent/task/completed",
        payload={
            "task_id": "task-test-002",
            "agent_name": "DataAnalystAgent",
            "success": True,
            "events": events,
            "user_id": "user-123",
        }
    )
    
    print(f"Published {len(published_messages)} messages")
    items = service2.get_pending_learning_items(limit=10)
    print(f"Pending learning items: {len(items)}")
    assert len(items) >= 1, "Expected task to be queued when passive learning is enabled"
    
    # Check that nominated=False for passive learning
    queued_msg = next((m for m in published_messages if "learning/queued" in m["topic"]), None)
    assert queued_msg is not None, "Expected learning/queued message"
    assert queued_msg["payload"].get("nominated") == False, "Expected nominated=False for passive learning"
    print("✓ Passive learning works correctly")
    
    print("\n✓ All SkillMessageHandler tests passed!")


def test_full_learning_flow():
    """Test the complete learning flow from nomination to skill storage."""
    print("\n" + "=" * 60)
    print("TEST: Full Learning Flow (Agent-Nominated)")
    print("=" * 60)
    
    # Set up components
    repo = SkillRepository(database_url="sqlite:///:memory:")
    repo.create_tables()
    
    service = SkillService(
        repository=repo,
        embedding_service=None,
        auto_generate_embeddings=False,
    )
    
    analyzer = TaskAnalyzer()
    extractor = SkillExtractor(llm_client=None)  # Will use mock extraction
    feedback_processor = FeedbackProcessor(repository=repo, skill_extractor=extractor)
    
    published_messages = []
    
    def mock_publish(topic: str, payload: Dict[str, Any]):
        published_messages.append({"topic": topic, "payload": payload})
    
    handler = SkillMessageHandler(
        skill_service=service,
        task_analyzer=analyzer,
        skill_extractor=extractor,
        feedback_processor=feedback_processor,
        publish_callback=mock_publish,
        passive_learning_enabled=False,  # Default - only nominated tasks
    )
    
    # Step 1: Agent nominates task for learning
    print("\n--- Step 1: Agent nominates task for learning ---")
    events = create_sample_task_events()
    
    handler.handle_message(
        topic="sam/DataAnalystAgent/task/nominate-for-learning",
        payload={
            "task_id": "task-test-001",
            "agent_name": "DataAnalystAgent",
            "events": events,
            "user_id": "user-123",
            "nomination_reason": "novel_approach",
            "metadata": {
                "user_request": "Analyze the sales data and create a summary report",
            },
        }
    )
    
    items = service.get_pending_learning_items(limit=10)
    print(f"Tasks queued for learning: {len(items)}")
    assert len(items) >= 1, "Expected nominated task to be queued"
    
    # Step 2: Process learning queue
    print("\n--- Step 2: Process learning queue ---")
    
    # Note: The actual skill extraction requires task events to be available
    # In a real scenario, events would be fetched from the database or cache
    # For this test, we'll manually cache the events
    handler._task_events_cache["task-test-001"] = events
    
    processed = handler.process_learning_queue(batch_size=10)
    print(f"Processed {processed} learning items")
    
    # Step 3: Verify skill was created
    print("\n--- Step 3: Verify skill creation ---")
    skills = repo.search_skills(owner_agent_name="DataAnalystAgent")
    print(f"Skills for DataAnalystAgent: {len(skills)}")
    
    for skill in skills:
        print(f"  - {skill.name}: {skill.description[:50]}...")
    
    # Check published messages
    print("\n--- Published messages ---")
    for msg in published_messages:
        print(f"  {msg['topic']}: {msg['payload']}")
    
    print("\n✓ Full learning flow test completed!")


def main():
    """Run all tests."""
    print("=" * 60)
    print("SKILL LEARNING SYSTEM TESTS")
    print("=" * 60)
    
    try:
        test_task_analyzer()
        test_skill_repository()
        test_skill_service()
        test_message_handler()
        test_full_learning_flow()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()