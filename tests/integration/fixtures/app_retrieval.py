"""App and component retrieval fixtures for integration tests.

This module contains fixtures that retrieve apps and components from the
shared_solace_connector, plus state cleanup fixtures.
Extracted from the main integration conftest to improve maintainability.
"""
from typing import Generator, TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from sam_test_infrastructure.a2a_validator.validator import A2AMessageValidator
from sam_test_infrastructure.gateway_interface.app import TestGatewayApp
from sam_test_infrastructure.gateway_interface.component import TestGatewayComponent
from solace_ai_connector.solace_ai_connector import SolaceAiConnector

from solace_agent_mesh.agent.sac.app import SamAgentApp
from solace_agent_mesh.agent.sac.component import SamAgentComponent
from solace_agent_mesh.gateway.http_sse.app import WebUIBackendApp
from solace_agent_mesh.gateway.http_sse.component import WebUIBackendComponent

if TYPE_CHECKING:
    from solace_agent_mesh.agent.proxies.base.component import BaseProxyComponent


def get_component_from_app(app: SamAgentApp) -> SamAgentComponent:
    """Helper to get the component from an app."""
    if app.flows and app.flows[0].component_groups:
        for group in app.flows[0].component_groups:
            for component_wrapper in group:
                component = (
                    component_wrapper.component
                    if hasattr(component_wrapper, "component")
                    else component_wrapper
                )
                if isinstance(component, SamAgentComponent):
                    return component
    raise RuntimeError("SamAgentComponent not found in the application flow.")


# Agent app retrieval fixtures
@pytest.fixture(scope="session")
def sam_app_under_test(shared_solace_connector: SolaceAiConnector) -> SamAgentApp:
    """Retrieves the main SamAgentApp instance."""
    app_instance = shared_solace_connector.get_app("TestSamAgentApp")
    assert isinstance(app_instance, SamAgentApp), "Failed to retrieve SamAgentApp."
    print(f"sam_app_under_test fixture: Retrieved app {app_instance.name} from shared SolaceAiConnector.")
    yield app_instance


@pytest.fixture(scope="session")
def peer_agent_a_app_under_test(shared_solace_connector: SolaceAiConnector) -> SamAgentApp:
    """Retrieves the TestPeerAgentA_App instance."""
    app_instance = shared_solace_connector.get_app("TestPeerAgentA_App")
    assert isinstance(app_instance, SamAgentApp), "Failed to retrieve TestPeerAgentA_App."
    yield app_instance


@pytest.fixture(scope="session")
def peer_agent_b_app_under_test(shared_solace_connector: SolaceAiConnector) -> SamAgentApp:
    """Retrieves the TestPeerAgentB_App instance."""
    app_instance = shared_solace_connector.get_app("TestPeerAgentB_App")
    assert isinstance(app_instance, SamAgentApp), "Failed to retrieve TestPeerAgentB_App."
    yield app_instance


@pytest.fixture(scope="session")
def peer_agent_c_app_under_test(shared_solace_connector: SolaceAiConnector) -> SamAgentApp:
    """Retrieves the TestPeerAgentC_App instance."""
    app_instance = shared_solace_connector.get_app("TestPeerAgentC_App")
    assert isinstance(app_instance, SamAgentApp), "Failed to retrieve TestPeerAgentC_App."
    yield app_instance


@pytest.fixture(scope="session")
def peer_agent_d_app_under_test(shared_solace_connector: SolaceAiConnector) -> SamAgentApp:
    """Retrieves the TestPeerAgentD_App instance."""
    app_instance = shared_solace_connector.get_app("TestPeerAgentD_App")
    assert isinstance(app_instance, SamAgentApp), "Failed to retrieve TestPeerAgentD_App."
    yield app_instance


@pytest.fixture(scope="session")
def combined_dynamic_agent_app_under_test(shared_solace_connector: SolaceAiConnector) -> SamAgentApp:
    """Retrieves the CombinedDynamicAgent_App instance."""
    app_instance = shared_solace_connector.get_app("CombinedDynamicAgent_App")
    assert isinstance(app_instance, SamAgentApp), "Failed to retrieve CombinedDynamicAgent_App."
    yield app_instance


@pytest.fixture(scope="session")
def empty_provider_agent_app_under_test(shared_solace_connector: SolaceAiConnector) -> SamAgentApp:
    """Retrieves the EmptyProviderAgent_App instance."""
    app_instance = shared_solace_connector.get_app("EmptyProviderAgent_App")
    assert isinstance(app_instance, SamAgentApp), "Failed to retrieve EmptyProviderAgent_App."
    yield app_instance


@pytest.fixture(scope="session")
def docstringless_agent_app_under_test(shared_solace_connector: SolaceAiConnector) -> SamAgentApp:
    """Retrieves the DocstringlessAgent_App instance."""
    app_instance = shared_solace_connector.get_app("DocstringlessAgent_App")
    assert isinstance(app_instance, SamAgentApp), "Failed to retrieve DocstringlessAgent_App."
    yield app_instance


@pytest.fixture(scope="session")
def mixed_discovery_agent_app_under_test(shared_solace_connector: SolaceAiConnector) -> SamAgentApp:
    """Retrieves the MixedDiscoveryAgent_App instance."""
    app_instance = shared_solace_connector.get_app("MixedDiscoveryAgent_App")
    assert isinstance(app_instance, SamAgentApp), "Failed to retrieve MixedDiscoveryAgent_App."
    yield app_instance


@pytest.fixture(scope="session")
def complex_signatures_agent_app_under_test(shared_solace_connector: SolaceAiConnector) -> SamAgentApp:
    """Retrieves the ComplexSignaturesAgent_App instance."""
    app_instance = shared_solace_connector.get_app("ComplexSignaturesAgent_App")
    assert isinstance(app_instance, SamAgentApp), "Failed to retrieve ComplexSignaturesAgent_App."
    yield app_instance


@pytest.fixture(scope="session")
def config_context_agent_component_app_under_test(shared_solace_connector: SolaceAiConnector) -> SamAgentApp:
    """Retrieves the ConfigContextAgent_App instance."""
    app_instance = shared_solace_connector.get_app("ConfigContextAgent_App")
    assert isinstance(app_instance, SamAgentApp), "Failed to retrieve ConfigContextAgent_App."
    yield app_instance


@pytest.fixture(scope="session")
def artifact_content_agent_app_under_test(shared_solace_connector: SolaceAiConnector) -> SamAgentApp:
    """Retrieves the ArtifactContentAgent_App instance."""
    app_instance = shared_solace_connector.get_app("ArtifactContentAgent_App")
    assert isinstance(app_instance, SamAgentApp), "Failed to retrieve ArtifactContentAgent_App."
    yield app_instance


@pytest.fixture(scope="session")
def compaction_agent_app_under_test(shared_solace_connector: SolaceAiConnector) -> SamAgentApp:
    """Retrieves the TestAgentCompaction_App instance."""
    app_instance = shared_solace_connector.get_app("TestAgentCompaction_App")
    assert isinstance(app_instance, SamAgentApp), "Failed to retrieve TestAgentCompaction_App."
    yield app_instance


# Component retrieval fixtures
@pytest.fixture(scope="session")
def main_agent_component(sam_app_under_test: SamAgentApp) -> SamAgentComponent:
    """Retrieves the main SamAgentComponent instance."""
    return get_component_from_app(sam_app_under_test)


@pytest.fixture(scope="session")
def peer_a_component(peer_agent_a_app_under_test: SamAgentApp) -> SamAgentComponent:
    """Retrieves the TestPeerAgentA component instance."""
    return get_component_from_app(peer_agent_a_app_under_test)


@pytest.fixture(scope="session")
def peer_b_component(peer_agent_b_app_under_test: SamAgentApp) -> SamAgentComponent:
    """Retrieves the TestPeerAgentB component instance."""
    return get_component_from_app(peer_agent_b_app_under_test)


@pytest.fixture(scope="session")
def peer_c_component(peer_agent_c_app_under_test: SamAgentApp) -> SamAgentComponent:
    """Retrieves the TestPeerAgentC component instance."""
    return get_component_from_app(peer_agent_c_app_under_test)


@pytest.fixture(scope="session")
def peer_d_component(peer_agent_d_app_under_test: SamAgentApp) -> SamAgentComponent:
    """Retrieves the TestPeerAgentD component instance."""
    return get_component_from_app(peer_agent_d_app_under_test)


@pytest.fixture(scope="session")
def combined_dynamic_agent_component(combined_dynamic_agent_app_under_test: SamAgentApp) -> SamAgentComponent:
    """Retrieves the CombinedDynamicAgent component instance."""
    return get_component_from_app(combined_dynamic_agent_app_under_test)


@pytest.fixture(scope="session")
def empty_provider_agent_component(empty_provider_agent_app_under_test: SamAgentApp) -> SamAgentComponent:
    """Retrieves the EmptyProviderAgent component instance."""
    return get_component_from_app(empty_provider_agent_app_under_test)


@pytest.fixture(scope="session")
def docstringless_agent_component(docstringless_agent_app_under_test: SamAgentApp) -> SamAgentComponent:
    """Retrieves the DocstringlessAgent component instance."""
    return get_component_from_app(docstringless_agent_app_under_test)


@pytest.fixture(scope="session")
def mixed_discovery_agent_component(mixed_discovery_agent_app_under_test: SamAgentApp) -> SamAgentComponent:
    """Retrieves the MixedDiscoveryAgent component instance."""
    return get_component_from_app(mixed_discovery_agent_app_under_test)


@pytest.fixture(scope="session")
def complex_signatures_agent_component(complex_signatures_agent_app_under_test: SamAgentApp) -> SamAgentComponent:
    """Retrieves the ComplexSignaturesAgent component instance."""
    return get_component_from_app(complex_signatures_agent_app_under_test)


@pytest.fixture(scope="session")
def config_context_agent_component(config_context_agent_component_app_under_test: SamAgentApp) -> SamAgentComponent:
    """Retrieves the ConfigContextAgent component instance."""
    return get_component_from_app(config_context_agent_component_app_under_test)


@pytest.fixture(scope="session")
def artifact_content_agent_component(artifact_content_agent_app_under_test: SamAgentApp) -> SamAgentComponent:
    """Retrieves the ArtifactContentAgent component instance."""
    return get_component_from_app(artifact_content_agent_app_under_test)


# Workflow app fixtures
@pytest.fixture(scope="session")
def test_simple_workflow_app(shared_solace_connector: SolaceAiConnector):
    """Retrieves the TestSimpleWorkflowApp instance."""
    from solace_agent_mesh.workflow.app import WorkflowApp
    app_instance = shared_solace_connector.get_app("TestSimpleWorkflowApp")
    assert isinstance(app_instance, WorkflowApp), "Failed to retrieve TestSimpleWorkflowApp."
    yield app_instance


@pytest.fixture(scope="session")
def test_simple_workflow_component(test_simple_workflow_app):
    """Retrieves the SimpleTestWorkflow component instance."""
    from solace_agent_mesh.workflow.component import WorkflowComponent
    component = get_component_from_app(test_simple_workflow_app)
    assert isinstance(component, WorkflowComponent), "Failed to retrieve WorkflowComponent."
    return component


# Gateway fixtures
@pytest.fixture(scope="session")
def webui_api_client(shared_solace_connector: SolaceAiConnector) -> Generator[TestClient, None, None]:
    """Provides a FastAPI TestClient for the running WebUIBackendApp."""
    app_instance = shared_solace_connector.get_app("WebUIBackendApp")
    assert isinstance(app_instance, WebUIBackendApp), "Failed to retrieve WebUIBackendApp."

    component_instance = app_instance.get_component()
    assert isinstance(component_instance, WebUIBackendComponent), "Failed to retrieve WebUIBackendComponent."

    fastapi_app_instance = component_instance.fastapi_app
    if not fastapi_app_instance:
        pytest.fail("WebUIBackendComponent's FastAPI app is not initialized.")

    with TestClient(fastapi_app_instance) as client:
        print("[SessionFixture] TestClient for WebUIBackendApp created.")
        yield client
    print("[SessionFixture] TestClient for WebUIBackendApp closed.")


@pytest.fixture(scope="session")
def a2a_proxy_component(shared_solace_connector: SolaceAiConnector) -> "BaseProxyComponent":
    """Retrieves the A2AProxyComponent instance."""
    from solace_agent_mesh.agent.proxies.base.component import BaseProxyComponent

    app_instance = shared_solace_connector.get_app("TestA2AProxyApp")
    assert app_instance, "Could not find TestA2AProxyApp in the connector."

    if app_instance.flows and app_instance.flows[0].component_groups:
        for group in app_instance.flows[0].component_groups:
            for comp_wrapper in group:
                component = (
                    comp_wrapper.component
                    if hasattr(comp_wrapper, "component")
                    else comp_wrapper
                )
                if isinstance(component, BaseProxyComponent):
                    return component
    raise RuntimeError("A2AProxyComponent not found in the application flow.")


@pytest.fixture(scope="session")
def test_gateway_app_instance(shared_solace_connector: SolaceAiConnector) -> TestGatewayComponent:
    """Retrieves the TestGatewayApp instance and yields its TestGatewayComponent."""
    app_instance = shared_solace_connector.get_app("TestHarnessGatewayApp")
    assert isinstance(app_instance, TestGatewayApp), "Failed to retrieve TestGatewayApp."
    print(f"test_gateway_app_instance fixture: Retrieved app {app_instance.name}.")

    component_instance = None
    if app_instance.flows and app_instance.flows[0].component_groups:
        for group in app_instance.flows[0].component_groups:
            for comp_wrapper in group:
                actual_comp = (
                    comp_wrapper.component
                    if hasattr(comp_wrapper, "component")
                    else comp_wrapper
                )
                if isinstance(actual_comp, TestGatewayComponent):
                    component_instance = actual_comp
                    break
            if component_instance:
                break

    if not component_instance:
        if hasattr(app_instance, "get_component"):
            comp_from_method = app_instance.get_component()
            if isinstance(comp_from_method, TestGatewayComponent):
                component_instance = comp_from_method
            elif hasattr(comp_from_method, "component") and isinstance(
                comp_from_method.component, TestGatewayComponent
            ):
                component_instance = comp_from_method.component

    if not component_instance:
        pytest.fail("TestGatewayComponent instance could not be retrieved.")

    print(f"[SessionFixture] TestGatewayComponent instance ({component_instance.name}) retrieved for session.")
    yield component_instance


# State cleanup fixtures
def _clear_agent_component_state(agent_app: SamAgentApp):
    """Helper function to clear state from a SamAgentComponent."""
    component = get_component_from_app(agent_app)

    if component:
        with component.active_tasks_lock:
            component.active_tasks.clear()

        if (
            hasattr(component, "invocation_monitor")
            and component.invocation_monitor
            and hasattr(component.invocation_monitor, "_reset_session")
        ):
            component.invocation_monitor._reset_session()


@pytest.fixture(autouse=True, scope="function")
def clear_test_gateway_state_between_tests(request):
    """Clears state from the session-scoped TestGatewayComponent after each test."""
    yield
    if "shared_solace_connector" in request.fixturenames:
        test_gateway_app_instance = request.getfixturevalue("test_gateway_app_instance")
        test_gateway_app_instance.clear_captured_outputs()
        test_gateway_app_instance.clear_all_captured_cancel_calls()
        if test_gateway_app_instance.task_context_manager:
            test_gateway_app_instance.task_context_manager.clear_all_contexts_for_testing()


@pytest.fixture(autouse=True, scope="function")
def clear_all_agent_states_between_tests(request):
    """Clears state from all agent components after each test."""
    yield
    if "shared_solace_connector" not in request.fixturenames:
        return

    agent_app_fixtures = [
        "sam_app_under_test",
        "peer_agent_a_app_under_test",
        "peer_agent_b_app_under_test",
        "peer_agent_c_app_under_test",
        "peer_agent_d_app_under_test",
        "combined_dynamic_agent_app_under_test",
        "empty_provider_agent_app_under_test",
        "docstringless_agent_app_under_test",
        "mixed_discovery_agent_app_under_test",
        "complex_signatures_agent_app_under_test",
        "config_context_agent_component_app_under_test",
        "compaction_agent_app_under_test"
    ]

    for fixture_name in agent_app_fixtures:
        if fixture_name in request.fixturenames:
            app = request.getfixturevalue(fixture_name)
            _clear_agent_component_state(app)

    if "a2a_proxy_component" in request.fixturenames:
        a2a_proxy_component = request.getfixturevalue("a2a_proxy_component")
        a2a_proxy_component.clear_client_cache()

    if "test_a2a_agent_server_harness" in request.fixturenames:
        test_a2a_agent_server_harness = request.getfixturevalue("test_a2a_agent_server_harness")
        test_a2a_agent_server_harness.clear_captured_auth_headers()
        test_a2a_agent_server_harness.clear_captured_requests()
        test_a2a_agent_server_harness.clear_auth_state()


# A2A validation fixtures
@pytest.fixture(scope="function")
def a2a_message_validator(
    sam_app_under_test: SamAgentApp,
    peer_agent_a_app_under_test: SamAgentApp,
    peer_agent_b_app_under_test: SamAgentApp,
    peer_agent_c_app_under_test: SamAgentApp,
    peer_agent_d_app_under_test: SamAgentApp,
    combined_dynamic_agent_app_under_test: SamAgentApp,
    test_gateway_app_instance: TestGatewayComponent,
) -> A2AMessageValidator:
    """
    Provides an A2AMessageValidator activated to monitor all agent components and test gateway.
    """
    validator = A2AMessageValidator()

    all_apps = [
        sam_app_under_test,
        peer_agent_a_app_under_test,
        peer_agent_b_app_under_test,
        peer_agent_c_app_under_test,
        peer_agent_d_app_under_test,
        combined_dynamic_agent_app_under_test,
    ]

    components_to_patch = [get_component_from_app(app) for app in all_apps]
    components_to_patch.append(test_gateway_app_instance)
    final_components_to_patch = [c for c in components_to_patch if c is not None]

    if not final_components_to_patch:
        pytest.skip("No suitable components found to patch for A2A validation.")

    print(f"A2A Validator activating on components: {[c.name for c in final_components_to_patch]}")
    validator.activate(final_components_to_patch)
    yield validator
    validator.deactivate()


# A2A mock fixtures for testing
@pytest.fixture(scope="session")
def mock_agent_skills():
    """Provides mock agent skills for A2A agent card testing."""
    from a2a.types import AgentSkill
    return AgentSkill(
        id="skill-1",
        name="Skill 1",
        description="Description for Skill 1",
        tags=["tag1", "tag2"],
        examples=["Example 1", "Example 2"],
        input_modes=["text/plain"],
        output_modes=["text/plain"],
    )


@pytest.fixture(scope="session")
def mock_agent_card(mock_agent_skills):
    """Provides mock A2A agent card for testing."""
    from a2a.types import (
        AgentCard,
        AgentCapabilities,
        APIKeySecurityScheme,
        HTTPAuthSecurityScheme,
        In,
        SecurityScheme,
    )

    return AgentCard(
        name="test_agent",
        description="Test Agent Description",
        url="http://test.com/test_path/agent-card.json",
        version="1.0.0",
        protocol_version="0.3.0",
        capabilities=AgentCapabilities(
            streaming=True,
            push_notifications=False,
            state_transition_history=True,
        ),
        skills=[mock_agent_skills],
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        security=[{"bearer": []}, {"apikey": []}],
        security_schemes={
            "bearer": SecurityScheme(
                root=HTTPAuthSecurityScheme(type="http", scheme="bearer")
            ),
            "apikey": SecurityScheme(
                root=APIKeySecurityScheme(
                    type="apiKey", name="X-API-Key", in_=In.header
                )
            ),
        },
    )


@pytest.fixture(scope="function")
def mock_task_response():
    """Provides a mock A2A Task object representing a completed task."""
    from a2a.types import Task, TaskState
    from solace_agent_mesh.common import a2a

    final_status = a2a.create_task_status(
        state=TaskState.completed,
        message=a2a.create_agent_text_message(
            text="Task completed successfully", message_id="msg-agent-complete-1"
        ),
    )
    final_status.timestamp = "2024-01-01T00:00:00Z"

    return a2a.create_final_task(
        task_id="task-123",
        context_id="session-456",
        final_status=final_status,
    )


@pytest.fixture(scope="function")
def mock_task_response_cancel():
    """Provides a mock A2A Task object representing a canceled task."""
    from a2a.types import Task, TaskState
    from solace_agent_mesh.common import a2a

    final_status = a2a.create_task_status(
        state=TaskState.canceled,
        message=a2a.create_agent_text_message(
            text="Task canceled successfully", message_id="msg-agent-cancel-1"
        ),
    )
    final_status.timestamp = "2023-01-01T00:00:00Z"

    return a2a.create_final_task(
        task_id="task-123",
        context_id="session-456",
        final_status=final_status,
    )


@pytest.fixture(scope="function")
def mock_sse_task_response():
    """Provides a mock A2A TaskStatusUpdateEvent for streaming response."""
    from a2a.types import TaskStatusUpdateEvent
    from solace_agent_mesh.common import a2a

    status_message = a2a.create_agent_text_message(
        text="Processing...", message_id="msg-agent-stream-1"
    )
    status_update = a2a.create_status_update(
        task_id="task-123",
        context_id="session-456",
        message=status_message,
        is_final=False,
    )
    status_update.status.timestamp = "2024-01-01T00:00:00Z"
    return status_update


@pytest.fixture(scope="function")
def mock_task_callback_response():
    """Provides a mock A2A TaskPushNotificationConfig object."""
    from a2a.types import TaskPushNotificationConfig, PushNotificationConfig

    return TaskPushNotificationConfig(
        task_id="task-123",
        push_notification_config=PushNotificationConfig(
            id="config-1",
            url="http://test.com/notify",
            token="test-token",
        ),
    )


