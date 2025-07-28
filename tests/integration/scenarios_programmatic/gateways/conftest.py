# This conftest.py sets up a dedicated, isolated test environment for the REST Gateway.
# It creates a new SolaceAiConnector instance with only the TestAgent and the
# TestRestGatewayApp, ensuring that these tests do not interfere with other integration tests.

import pytest
from solace_ai_connector.solace_ai_connector import SolaceAiConnector
from src.solace_agent_mesh.agent.sac.app import SamAgentApp
from src.solace_agent_mesh.agent.sac.component import SamAgentComponent
from tests.integration.infrastructure.rest_gateway_interface.app import TestRestGatewayApp
from tests.integration.infrastructure.rest_gateway_interface.component import TestRestGatewayComponent
from tests.integration.infrastructure.slack_gateway_interface.app import TestSlackGatewayApp
from tests.integration.infrastructure.slack_gateway_interface.component import TestSlackGatewayComponent
from tests.integration.infrastructure.web_gateway_interface.app import TestWebGatewayApp
from tests.integration.infrastructure.web_gateway_interface.component import TestWebGatewayComponent
from tests.integration.infrastructure.event_mesh_gateway_interface.app import TestEventMeshGatewayApp
from tests.integration.infrastructure.event_mesh_gateway_interface.component import TestEventMeshGatewayComponent
from tests.integration.infrastructure.webhook_gateway_interface.app import TestWebhookGatewayApp
from tests.integration.infrastructure.webhook_gateway_interface.component import TestWebhookGatewayComponent
import time

@pytest.fixture(scope="session")
def gateway_test_solace_connector(
    test_llm_server,
    test_artifact_service_instance,
    session_monkeypatch,
) -> SolaceAiConnector:
    """
    Creates and manages a new, isolated SolaceAiConnector instance for all
    gateway tests. It includes the main TestAgent and all TestGatewayApps.
    """

    def create_agent_config(
        agent_name,
        description,
        allow_list,
        tools,
        model_suffix,
        session_behavior="RUN_BASED",
    ):
        return {
            "namespace": "test_namespace",
            "supports_streaming": True,
            "agent_name": agent_name,
            "model": {
                "model": f"openai/test-model-{model_suffix}-{time.time_ns()}",
                "api_base": f"{test_llm_server.url}/v1",
                "api_key": f"fake_test_key_{model_suffix}",
            },
            "session_service": {"type": "memory", "default_behavior": session_behavior},
            "artifact_handling_mode": "embed",
            "artifact_service": {"type": "test_in_memory"},
            "memory_service": {"type": "memory"},
            "agent_card": {
                "description": description,
                "defaultInputModes": ["text"],
                "defaultOutputModes": ["text"],
                "jsonrpc": "2.0",
                "id": "agent_card_pub"
            },
            "agent_card_publishing": {"interval_seconds": 1},
            "agent_discovery": {"enabled": True},
            "inter_agent_communication": {
                "allow_list": allow_list,
                "request_timeout_seconds": 5,
            },
            "tools": tools,
        }

    test_agent_tools = [
        {"tool_type": "builtin", "tool_name": "time_delay"},
        {"tool_type": "builtin", "tool_name": "create_artifact"}
    ]
    sam_agent_app_config = create_agent_config(
        agent_name="GatewayTestAgent",
        description="The main test agent",
        allow_list=[],
        tools=test_agent_tools,
        model_suffix="sam",
    )

    rest_gateway_config = {
        "namespace": "test_namespace",
        "gateway_id": "TestRestGateway_01",
        "artifact_service": {"type": "test_in_memory"},
        "rest_api_server_port": 8099,
    }

    slack_gateway_config = {
        "namespace": "test_namespace",
        "gateway_id": "TestSlackGateway_01",
        "artifact_service": {"type": "test_in_memory"},
        "slack_bot_token": "fake-bot-token",
        "slack_app_token": "fake-app-token",
        "default_agent_name": "GatewayTestAgent",
    }

    web_gateway_config = {
        "namespace": "test_namespace",
        "gateway_id": "TestWebGateway_01",
        "artifact_service": {"type": "test_in_memory"},
        "session_secret_key": "test-secret-key",
        "fastapi_port": 8098,
    }

    event_mesh_gateway_config = {
        "namespace": "test_namespace",
        "gateway_id": "TestEventMeshGateway_01",
        "artifact_service": {"type": "test_in_memory"},
        "event_mesh_broker_config": {
            "broker_url": "localhost",
            "broker_vpn": "default",
            "broker_username": "test",
            "broker_password": "test",
        },
        "event_handlers": [
            {
                "name": "test_handler",
                "subscriptions": [{"topic": "test/topic"}],
                "input_expression": "input.payload:text",
                "target_agent_name": "GatewayTestAgent",
                "on_success": "test_output_handler",
                "user_identity_expression": "user_data.user_id"
            },
            {
                "name": "non_existent_agent_handler",
                "subscriptions": [{"topic": "test/topic/non_existent_agent"}],
                "input_expression": "input.payload:text",
                "target_agent_name": "NonExistentAgent",
                "on_success": "test_output_handler",
                "user_identity_expression": "user_data.user_id"
            }
        ],
        "output_handlers": [
            {
                "name": "test_output_handler",
                "topic_expression": "user_data.original_solace_topic",
                "payload_expression": "input.payload:text",
            }
        ],
    }

    webhook_gateway_config = {
        "namespace": "test_namespace",
        "gateway_id": "TestWebhookGateway_01",
        "artifact_service": {"type": "test_in_memory"},
        "webhook_endpoints": [
            {
                "path": "/hooks/test",
                "target_agent_name": "GatewayTestAgent",
                "input_template": "{{ request.json.text }}",
            }
        ],
    }

    app_infos = [
        {
            "name": "GatewayTestTargetAgentApp",
            "app_config": sam_agent_app_config,
            "broker": {"dev_mode": True},
            "app_module": "src.solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "TestRestGatewayApp",
            "app_config": rest_gateway_config,
            "broker": {"dev_mode": True},
            "app_module": "tests.integration.infrastructure.rest_gateway_interface.app",
        },
        {
            "name": "TestSlackGatewayApp",
            "app_config": slack_gateway_config,
            "broker": {"dev_mode": True},
            "app_module": "tests.integration.infrastructure.slack_gateway_interface.app",
        },
        {
            "name": "TestWebGatewayApp",
            "app_config": web_gateway_config,
            "broker": {"dev_mode": True},
            "app_module": "tests.integration.infrastructure.web_gateway_interface.app",
        },
        {
            "name": "TestEventMeshGatewayApp",
            "app_config": event_mesh_gateway_config,
            "broker": {"dev_mode": True},
            "app_module": "tests.integration.infrastructure.event_mesh_gateway_interface.app",
        },
        {
            "name": "TestWebhookGatewayApp",
            "app_config": webhook_gateway_config,
            "broker": {"dev_mode": True},
            "app_module": "tests.integration.infrastructure.webhook_gateway_interface.app",
        },
    ]

    session_monkeypatch.setattr(
        "src.solace_agent_mesh.agent.adk.services.TestInMemoryArtifactService",
        lambda: test_artifact_service_instance,
    )

    connector_config = {
        "apps": app_infos,
        "log": {
            "stdout_log_level": "INFO",
            "log_file_level": "INFO",
            "enable_trace": False,
        },
    }
    connector = SolaceAiConnector(config=connector_config)
    connector.run()
    yield connector
    connector.stop()
    connector.cleanup()

@pytest.fixture(scope="session")
def sam_app_for_gateway_test(gateway_test_solace_connector: SolaceAiConnector) -> SamAgentApp:
    app_instance = gateway_test_solace_connector.get_app("GatewayTestTargetAgentApp")
    assert isinstance(app_instance, SamAgentApp)
    return app_instance

@pytest.fixture(scope="session")
def main_agent_component_for_gateway_test(sam_app_for_gateway_test: SamAgentApp) -> SamAgentComponent:
    for group in sam_app_for_gateway_test.flows[0].component_groups:
        for component_wrapper in group:
            component = (
                component_wrapper.component
                if hasattr(component_wrapper, "component")
                else component_wrapper
            )
            if isinstance(component, SamAgentComponent):
                return component
    raise RuntimeError("SamAgentComponent not found in the application flow.")

# REST Gateway Fixtures
@pytest.fixture(scope="session")
def test_rest_gateway_app(gateway_test_solace_connector: SolaceAiConnector) -> TestRestGatewayApp:
    app_instance = gateway_test_solace_connector.get_app("TestRestGatewayApp")
    assert isinstance(app_instance, TestRestGatewayApp)
    return app_instance

@pytest.fixture(scope="session")
def test_rest_gateway_component(test_rest_gateway_app: TestRestGatewayApp) -> TestRestGatewayComponent:
    for group in test_rest_gateway_app.flows[0].component_groups:
        for comp_wrapper in group:
            actual_comp = (
                comp_wrapper.component
                if hasattr(comp_wrapper, "component")
                else comp_wrapper
            )
            if isinstance(actual_comp, TestRestGatewayComponent):
                return actual_comp
    pytest.fail("TestRestGatewayComponent not found in the application flow.")

# Slack Gateway Fixtures
@pytest.fixture(scope="session")
def test_slack_gateway_app(gateway_test_solace_connector: SolaceAiConnector) -> TestSlackGatewayApp:
    app_instance = gateway_test_solace_connector.get_app("TestSlackGatewayApp")
    assert isinstance(app_instance, TestSlackGatewayApp)
    return app_instance

@pytest.fixture(scope="session")
def test_slack_gateway_component(test_slack_gateway_app: TestSlackGatewayApp) -> TestSlackGatewayComponent:
    for group in test_slack_gateway_app.flows[0].component_groups:
        for comp_wrapper in group:
            actual_comp = (
                comp_wrapper.component
                if hasattr(comp_wrapper, "component")
                else comp_wrapper
            )
            if isinstance(actual_comp, TestSlackGatewayComponent):
                return actual_comp
    pytest.fail("TestSlackGatewayComponent not found in the application flow.")

# Web Gateway Fixtures
@pytest.fixture(scope="session")
def test_web_gateway_app(gateway_test_solace_connector: SolaceAiConnector) -> TestWebGatewayApp:
    app_instance = gateway_test_solace_connector.get_app("TestWebGatewayApp")
    assert isinstance(app_instance, TestWebGatewayApp)
    return app_instance

@pytest.fixture(scope="session")
def test_web_gateway_component(test_web_gateway_app: TestWebGatewayApp) -> TestWebGatewayComponent:
    for group in test_web_gateway_app.flows[0].component_groups:
        for comp_wrapper in group:
            actual_comp = (
                comp_wrapper.component
                if hasattr(comp_wrapper, "component")
                else comp_wrapper
            )
            if isinstance(actual_comp, TestWebGatewayComponent):
                return actual_comp
    pytest.fail("TestWebGatewayComponent not found in the application flow.")

# Event Mesh Gateway Fixtures
@pytest.fixture(scope="session")
def test_event_mesh_gateway_app(gateway_test_solace_connector: SolaceAiConnector) -> TestEventMeshGatewayApp:
    app_instance = gateway_test_solace_connector.get_app("TestEventMeshGatewayApp")
    assert isinstance(app_instance, TestEventMeshGatewayApp)
    return app_instance

@pytest.fixture(scope="session")
def test_event_mesh_gateway_component(test_event_mesh_gateway_app: TestEventMeshGatewayApp) -> TestEventMeshGatewayComponent:
    for group in test_event_mesh_gateway_app.flows[0].component_groups:
        for comp_wrapper in group:
            actual_comp = (
                comp_wrapper.component
                if hasattr(comp_wrapper, "component")
                else comp_wrapper
            )
            if isinstance(actual_comp, TestEventMeshGatewayComponent):
                return actual_comp
    pytest.fail("TestEventMeshGatewayComponent not found in the application flow.")

# Webhook Gateway Fixtures
@pytest.fixture(scope="session")
def test_webhook_gateway_app(gateway_test_solace_connector: SolaceAiConnector) -> TestWebhookGatewayApp:
    app_instance = gateway_test_solace_connector.get_app("TestWebhookGatewayApp")
    assert isinstance(app_instance, TestWebhookGatewayApp)
    return app_instance

@pytest.fixture(scope="session")
def test_webhook_gateway_component(test_webhook_gateway_app: TestWebhookGatewayApp) -> TestWebhookGatewayComponent:
    for group in test_webhook_gateway_app.flows[0].component_groups:
        for comp_wrapper in group:
            actual_comp = (
                comp_wrapper.component
                if hasattr(comp_wrapper, "component")
                else comp_wrapper
            )
            if isinstance(actual_comp, TestWebhookGatewayComponent):
                return actual_comp
    pytest.fail("TestWebhookGatewayComponent not found in the application flow.")

@pytest.fixture(autouse=True)
def clear_gateway_component_states(test_rest_gateway_component: TestRestGatewayComponent, test_slack_gateway_component: TestSlackGatewayComponent, test_web_gateway_component: TestWebGatewayComponent, test_event_mesh_gateway_component: TestEventMeshGatewayComponent, test_webhook_gateway_component: TestWebhookGatewayComponent):
    """
    Clears the state of all test gateway components before each test.
    """
    yield
    test_rest_gateway_component.clear_captured_outputs()
    test_slack_gateway_component.clear_captured_outputs()
    test_web_gateway_component.clear_captured_outputs()
    test_event_mesh_gateway_component.clear_captured_outputs()
    test_webhook_gateway_component.clear_captured_outputs()
