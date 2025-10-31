"""
Pytest fixtures for generic gateway integration tests.

These fixtures provide configured GenericGatewayComponent instances with
various mock adapters for testing different scenarios.
"""

import pytest
from typing import TYPE_CHECKING

from solace_ai_connector.solace_ai_connector import SolaceAiConnector
from solace_agent_mesh.gateway.generic.component import GenericGatewayComponent

if TYPE_CHECKING:
    from sam_test_infrastructure.artifact_service.service import (
        TestInMemoryArtifactService,
    )


# --- Gateway Component Fixtures ---
# These fixtures retrieve the generic gateway apps that were added to
# shared_solace_connector in the main conftest.py


@pytest.fixture(scope="session")
def minimal_gateway_component(
    shared_solace_connector: SolaceAiConnector,
) -> GenericGatewayComponent:
    """
    Provides the GenericGatewayComponent with MinimalAdapter.

    This gateway is part of the shared_solace_connector with access
    to real agents and A2A messaging.
    """
    app = shared_solace_connector.get_app("MinimalGatewayApp")
    if not app:
        raise RuntimeError("MinimalGatewayApp not found in shared_solace_connector")
    return _get_component_from_app(app)


@pytest.fixture(scope="session")
def auth_gateway_component(
    shared_solace_connector: SolaceAiConnector,
) -> GenericGatewayComponent:
    """Provides the GenericGatewayComponent with AuthTestAdapter"""
    app = shared_solace_connector.get_app("AuthGatewayApp")
    if not app:
        raise RuntimeError("AuthGatewayApp not found in shared_solace_connector")
    return _get_component_from_app(app)


@pytest.fixture(scope="session")
def file_gateway_component(
    shared_solace_connector: SolaceAiConnector,
) -> GenericGatewayComponent:
    """Provides the GenericGatewayComponent with FileAdapter"""
    app = shared_solace_connector.get_app("FileGatewayApp")
    if not app:
        raise RuntimeError("FileGatewayApp not found in shared_solace_connector")
    return _get_component_from_app(app)


@pytest.fixture(scope="session")
def dispatching_gateway_component(
    shared_solace_connector: SolaceAiConnector,
) -> GenericGatewayComponent:
    """Provides the GenericGatewayComponent with DispatchingAdapter"""
    app = shared_solace_connector.get_app("DispatchingGatewayApp")
    if not app:
        raise RuntimeError("DispatchingGatewayApp not found in shared_solace_connector")
    return _get_component_from_app(app)


# --- Configuration Fixtures ---


@pytest.fixture(scope="session")
def error_adapter_config():
    """Configuration for ErrorAdapter"""
    return {
        "namespace": "test_namespace",
        "gateway_id": "ErrorTestGateway",
        "gateway_adapter": "tests.integration.gateway.generic.fixtures.mock_adapters.ErrorAdapter",
        "adapter_config": {},
        "artifact_service": {"type": "test_in_memory"},
    }


# --- Helper Functions ---


def simple_llm_response(text: str) -> dict:
    """
    Helper to create a simple text response for TestLLMServer.

    Returns a dict that can be passed to configure_static_response or prime_responses.
    """
    return {
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text,
                },
                "finish_reason": "stop",
            }
        ],
    }


def _get_component_from_app(app) -> GenericGatewayComponent:
    """Extract the GenericGatewayComponent from an app"""
    if app.flows and app.flows[0].component_groups:
        for group in app.flows[0].component_groups:
            for component_wrapper in group:
                component = (
                    component_wrapper.component
                    if hasattr(component_wrapper, "component")
                    else component_wrapper
                )
                if isinstance(component, GenericGatewayComponent):
                    return component
    raise RuntimeError(f"GenericGatewayComponent not found in app {app.name}")


# --- Cleanup Fixtures ---


@pytest.fixture(autouse=True, scope="function")
def clear_generic_gateway_state_between_tests(request):
    """
    Clears adapter state from generic gateway components after each test.

    This fixture automatically runs after each test that uses any of the
    generic gateway component fixtures.
    """
    # Store original methods before test runs
    original_methods = {}
    for fixture_name in request.fixturenames:
        if fixture_name.endswith("_gateway_component"):
            try:
                component = request.getfixturevalue(fixture_name)
                if isinstance(component, GenericGatewayComponent):
                    # Store original adapter methods that tests might replace
                    adapter_class = component.adapter.__class__
                    original_methods[fixture_name] = {
                        "handle_update": adapter_class.handle_update,
                        "extract_auth_claims": adapter_class.extract_auth_claims,
                    }
            except Exception:
                pass

    yield

    # Get all generic gateway components from the test's fixtures
    for fixture_name in request.fixturenames:
        if fixture_name.endswith("_gateway_component"):
            try:
                component = request.getfixturevalue(fixture_name)
                if isinstance(component, GenericGatewayComponent):
                    # Restore original methods if they were stored
                    if fixture_name in original_methods:
                        for method_name, original_method in original_methods[fixture_name].items():
                            setattr(component.adapter.__class__, method_name, original_method)

                    # Clear adapter state if it has tracking attributes
                    if hasattr(component.adapter, "received_updates"):
                        component.adapter.received_updates.clear()
                    if hasattr(component.adapter, "completed_tasks"):
                        component.adapter.completed_tasks.clear()
                    if hasattr(component.adapter, "errors"):
                        component.adapter.errors.clear()
                    if hasattr(component.adapter, "echoed_updates"):
                        component.adapter.echoed_updates.clear()
                    if hasattr(component.adapter, "uploaded_files"):
                        component.adapter.uploaded_files.clear()
                    if hasattr(component.adapter, "received_files"):
                        component.adapter.received_files.clear()
                    if hasattr(component.adapter, "auth_attempts"):
                        component.adapter.auth_attempts.clear()
                    if hasattr(component.adapter, "error_count"):
                        component.adapter.error_count = 0
                    if hasattr(component.adapter, "fail_on"):
                        component.adapter.fail_on = None
                    # DispatchingAdapter attributes
                    if hasattr(component.adapter, "text_chunks"):
                        component.adapter.text_chunks.clear()
                    if hasattr(component.adapter, "files"):
                        component.adapter.files.clear()
                    if hasattr(component.adapter, "data_parts"):
                        component.adapter.data_parts.clear()
                    if hasattr(component.adapter, "status_updates"):
                        component.adapter.status_updates.clear()

                    # Reset AuthTestAdapter config mutations
                    if hasattr(component.adapter, "context") and component.adapter.context:
                        if hasattr(component.adapter.context.adapter_config, "require_token"):
                            component.adapter.context.adapter_config.require_token = False

                    # Reset component config mutations
                    if hasattr(component, "component_config"):
                        # Restore default_user_identity if it was cleared
                        if component.component_config.get("default_user_identity") is None:
                            component.component_config["default_user_identity"] = "default-user@example.com"

                    # Clear task context
                    if component.task_context_manager:
                        component.task_context_manager.clear_all_contexts_for_testing()
            except Exception:
                # Fixture may not have been used in this test
                pass
