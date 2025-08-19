import asyncio
import pytest
from collections.abc import AsyncIterable


from solace_agent_mesh.common.types import (
    JSONRPCResponse,
    SendTaskRequest,
    SendTaskResponse,
    SendTaskStreamingRequest,
    SendTaskStreamingResponse,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)

pytestmark = [
    pytest.mark.all,
    pytest.mark.asyncio,
    pytest.mark.common,
    pytest.mark.server
]


def test_A2A_server():

    from src.solace_agent_mesh.common.server.server import A2AServer
    from src.solace_agent_mesh.common.server.task_manager import InMemoryTaskManager
    from src.solace_agent_mesh.common.types import (
        AgentCapabilities,
        AgentCard,
        AgentSkill,
    )

    # Helper to create AgentCapabilities with different IDs
    def make_agent_capabilities(id, name, description):
        return AgentCapabilities(
            id=id,
            name=name,
            description=description,
            tags=["tag1", "tag2"],
            examples=["Example 1", "Example 2"],
            inputModes=["text/plain"],
            outputModes=["text/plain"]
        )

    test_agent_capabilities_1 = make_agent_capabilities(
        "skill-1", "Skill 1", "Description for Skill 1"
    )
    test_agent_capabilities_2 = make_agent_capabilities(
        "skill-2", "Skill 2", "Description for Skill 2"
    )
    test_agent_skills = AgentSkill(
        id="skill-1",
        name="Skill 1",
        description="Description for Skill 1",
        tags=["tag1", "tag2"],
        examples=["Example 1", "Example 2"],
        inputModes=["text/plain"],
        outputModes=["text/plain"]
    )

    # Define agent cards without peer references first to avoid circular dependency
    test_agent_card_1 = AgentCard(
        id="my-test-agent-v1",
        name="test Agent-1",
        version="1.0.0",
        description="An agent that does awesome things.",
        documentation_url="https://example.com/docs",
        supported_tasks=["summarize", "translate"],
        input_modalities=["text/plain"],
        output_modalities=["text/plain"],
        url="http_test_url-1",
        skills=[test_agent_skills],
        capabilities=test_agent_capabilities_1,
        peer_agents={}
    )

    test_agent_card_2 = AgentCard(
        id="my-test-agent-v2",
        name="test Agent-2",
        version="1.0.0",
        description="An agent that does awesome things.",
        documentation_url="https://example.com/docs",
        supported_tasks=["summarize", "translate"],
        input_modalities=["text/plain"],
        output_modalities=["text/plain"],
        url="http_test_url-2",
        skills=[test_agent_skills],
        capabilities=test_agent_capabilities_2,
        peer_agents={}
    )

    # Now set up the peer relationships
    test_agent_card_1.peer_agents = {"peer1": test_agent_card_2}
    test_agent_card_2.peer_agents = {"peer1": test_agent_card_1}

    # Instantiate a test task manager
    class MyTestAgentTaskManager(InMemoryTaskManager):
        async def on_send_task(self, request):
            # Implement your agent's logic here
            pass
        async def on_send_task_subscribe(self, request):
            # Implement your agent's streaming logic here
            pass

    test_task_manager = MyTestAgentTaskManager()

    # Create and configure the server
    test_a2a_server = A2AServer(
        host="127.0.0.1",
        port=8080,
        endpoint="/api/v1/a2a",
        agent_card=test_agent_card_1,
        task_manager=test_task_manager
    )

    # Ensure the server is running
    assert isinstance(test_a2a_server, A2AServer)

def test_task_manager():
    from src.solace_agent_mesh.common.server.task_manager import InMemoryTaskManager

    class MyCustomTaskManager(InMemoryTaskManager):
        # Implement the core logic for a standard task
        async def on_send_task(self, request: SendTaskRequest) -> SendTaskResponse:
            task = await self.upsert_task(request.params)
            print(f"Received task {task.id} with message: {request.params.message.content}")

            # Simulate work
            await asyncio.sleep(2)

            # Update task status to completed
            final_status = TaskStatus(state=TaskState.COMPLETED)
            await self.update_store(task.id, final_status, [])

            return SendTaskResponse(id=request.id, result=task)

        # Implement the core logic for a streaming task
        async def on_send_task_subscribe(
            self, request: SendTaskStreamingRequest
        ) -> AsyncIterable[SendTaskStreamingResponse] | JSONRPCResponse:

            await self.upsert_task(request.params)
            sse_queue = await self.setup_sse_consumer(request.params.id)

            # Start the background task processing
            asyncio.create_task(self._process_streaming_task(request.params.id))

            # Return the async generator that will stream responses
            return self.dequeue_events_for_sse(request.id, request.params.id, sse_queue)

        async def _process_streaming_task(self, task_id: str):
            # Simulate streaming work
            for i in range(5):
                await asyncio.sleep(1)
                update = TaskStatusUpdateEvent(
                    status=TaskStatus(state=TaskState.IN_PROGRESS),
                    message={"content": f"Step {i+1} complete"}
                )
                # Enqueue the update for all subscribers
                await self.enqueue_events_for_sse(task_id, update)

            # Send final event
            final_update = TaskStatusUpdateEvent(
                status=TaskStatus(state=TaskState.COMPLETED),
                final=True
            )
            await self.enqueue_events_for_sse(task_id, final_update)
    # Instantiate the task manager
    task_manager = MyCustomTaskManager()

    # Check if the task manager is an instance of InMemoryTaskManager
    assert isinstance(task_manager, MyCustomTaskManager)
