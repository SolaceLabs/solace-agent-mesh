"""
Tests for the Control Service component and protocol helpers.
"""

import json
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from solace_agent_mesh.common.a2a.protocol import (
    get_control_subscription_topic,
    get_control_apps_topic,
    get_control_app_topic,
    parse_control_topic,
    CONTROL_VERSION,
    CONTROL_BASE_PATH,
)
from solace_agent_mesh.services.control.component import (
    ControlServiceComponent,
    ERROR_INVALID_REQUEST,
    ERROR_METHOD_NOT_ALLOWED,
    ERROR_NOT_FOUND,
    ERROR_CONFLICT,
    ERROR_AUTH_DENIED,
    ERROR_OPERATION_FAILED,
)


# --- Protocol Helper Tests ---


class TestControlTopicHelpers:
    """Tests for control plane topic construction and parsing."""

    def test_control_subscription_topic(self):
        topic = get_control_subscription_topic("myns")
        assert topic == "myns/sam/v1/control/>"

    def test_control_subscription_topic_strips_trailing_slash(self):
        topic = get_control_subscription_topic("myns/")
        assert topic == "myns/sam/v1/control/>"

    def test_control_subscription_topic_empty_namespace_raises(self):
        with pytest.raises(ValueError):
            get_control_subscription_topic("")

    def test_control_apps_topic(self):
        topic = get_control_apps_topic("myns", "get")
        assert topic == "myns/sam/v1/control/get/apps"

    def test_control_apps_topic_uppercased_method(self):
        topic = get_control_apps_topic("myns", "POST")
        assert topic == "myns/sam/v1/control/post/apps"

    def test_control_app_topic(self):
        topic = get_control_app_topic("myns", "my_agent", "get")
        assert topic == "myns/sam/v1/control/get/apps/my_agent"

    def test_control_app_topic_empty_name_raises(self):
        with pytest.raises(ValueError):
            get_control_app_topic("myns", "", "get")

    def test_control_app_topic_empty_method_raises(self):
        with pytest.raises(ValueError):
            get_control_app_topic("myns", "my_agent", "")

    def test_parse_control_topic_apps_collection(self):
        method, resource, app_name, custom_path = parse_control_topic(
            "myns", "myns/sam/v1/control/get/apps"
        )
        assert method == "get"
        assert resource == "apps"
        assert app_name is None
        assert custom_path == []

    def test_parse_control_topic_individual_app(self):
        method, resource, app_name, custom_path = parse_control_topic(
            "myns", "myns/sam/v1/control/get/apps/my_agent"
        )
        assert method == "get"
        assert resource == "apps"
        assert app_name == "my_agent"
        assert custom_path == []

    def test_parse_control_topic_custom_endpoint(self):
        method, resource, app_name, custom_path = parse_control_topic(
            "myns", "myns/sam/v1/control/get/apps/my_agent/tools/list"
        )
        assert method == "get"
        assert resource == "apps"
        assert app_name == "my_agent"
        assert custom_path == ["tools", "list"]

    def test_parse_control_topic_unrelated_topic(self):
        method, resource, app_name, custom_path = parse_control_topic(
            "myns", "myns/a2a/v1/agent/request/foo"
        )
        assert method is None
        assert resource is None
        assert app_name is None
        assert custom_path == []

    def test_parse_control_topic_no_resource(self):
        method, resource, app_name, custom_path = parse_control_topic(
            "myns", "myns/sam/v1/control/get/unknown"
        )
        assert method is None

    def test_parse_control_topic_method_only(self):
        """A topic with just a method and no resource should not match."""
        method, resource, app_name, custom_path = parse_control_topic(
            "myns", "myns/sam/v1/control/get"
        )
        assert method is None

    def test_parse_control_topic_trailing_slash_namespace(self):
        method, resource, app_name, custom_path = parse_control_topic(
            "myns/", "myns/sam/v1/control/post/apps"
        )
        assert method == "post"
        assert resource == "apps"

    def test_parse_control_topic_different_methods(self):
        """Verify all HTTP methods are extracted correctly."""
        for m in ["get", "post", "put", "patch", "delete"]:
            method, resource, _, _ = parse_control_topic(
                "myns", f"myns/sam/v1/control/{m}/apps"
            )
            assert method == m
            assert resource == "apps"


# --- Component Tests ---


def _make_mock_component(auth_type="none"):
    """Create a mock ControlServiceComponent with all dependencies mocked."""
    component = MagicMock(spec=ControlServiceComponent)
    component.log_identifier = "[test]"
    component.namespace = "testns"
    component.auth_type = auth_type
    component.connector = MagicMock()
    component.publish_a2a_message = MagicMock()
    component.trust_manager = None

    # Bind actual methods to the mock
    component._authorize = ControlServiceComponent._authorize.__get__(component)
    component._extract_user_config = ControlServiceComponent._extract_user_config.__get__(component)
    component._route_request = ControlServiceComponent._route_request.__get__(component)
    component._handle_list_apps = ControlServiceComponent._handle_list_apps.__get__(component)
    component._handle_create_app = ControlServiceComponent._handle_create_app.__get__(component)
    component._handle_get_app = ControlServiceComponent._handle_get_app.__get__(component)
    component._handle_update_app = ControlServiceComponent._handle_update_app.__get__(component)
    component._handle_patch_app = ControlServiceComponent._handle_patch_app.__get__(component)
    component._handle_delete_app = ControlServiceComponent._handle_delete_app.__get__(component)
    component._handle_custom_endpoint = ControlServiceComponent._handle_custom_endpoint.__get__(component)
    component._success_response = ControlServiceComponent._success_response
    component._error_response = ControlServiceComponent._error_response

    return component


def _make_mock_message(user_config=None, auth_token=None):
    """Create a mock message with user properties."""
    message = MagicMock()
    user_props = {}
    if user_config is not None:
        user_props["a2aUserConfig"] = user_config
    if auth_token is not None:
        user_props["authToken"] = auth_token
    message.get_user_properties.return_value = user_props
    return message


def _make_mock_app(name="test_app", status="running", enabled=True):
    """Create a mock App with get_info and lifecycle methods."""
    app = MagicMock()
    app.name = name
    app.status = status
    app.enabled = enabled
    app.num_instances = 1
    app.get_info.return_value = {
        "name": name,
        "enabled": enabled,
        "status": status,
        "num_instances": 1,
        "app_module": None,
    }
    app.get_management_endpoints.return_value = []
    app.handle_management_request.return_value = None
    return app


class TestControlServiceAuthorization:
    """Tests for authorization logic."""

    def test_auth_none_allows_all(self):
        component = _make_mock_component(auth_type="none")
        result = component._authorize("GET", "apps", None, [], MagicMock())
        assert result is None  # No error = authorized

    def test_auth_deny_all_denies(self):
        component = _make_mock_component(auth_type="deny_all")
        result = component._authorize("GET", "apps", None, [], MagicMock())
        assert result is not None
        assert result["error"]["code"] == ERROR_AUTH_DENIED

    def test_auth_unknown_type_uses_config_resolver(self):
        """Unknown auth types delegate to ConfigResolver.
        Default ConfigResolver returns valid=True, so access is granted."""
        component = _make_mock_component(auth_type="custom_rbac")
        result = component._authorize("GET", "apps", None, [], _make_mock_message())
        assert result is None  # Default ConfigResolver allows all


class TestControlServiceListApps:
    """Tests for GET /apps."""

    def test_list_apps_empty(self):
        component = _make_mock_component()
        component.connector.get_apps.return_value = []
        result = component._handle_list_apps("req-1")
        assert result["result"]["apps"] == []

    def test_list_apps_with_apps(self):
        component = _make_mock_component()
        app1 = _make_mock_app("app1")
        app2 = _make_mock_app("app2", status="stopped", enabled=False)
        component.connector.get_apps.return_value = [app1, app2]

        result = component._handle_list_apps("req-1")
        assert len(result["result"]["apps"]) == 2
        assert result["result"]["apps"][0]["name"] == "app1"
        assert result["result"]["apps"][1]["name"] == "app2"
        assert result["result"]["apps"][1]["status"] == "stopped"


class TestControlServiceCreateApp:
    """Tests for POST /apps."""

    def test_create_app_success(self):
        component = _make_mock_component()
        new_app = _make_mock_app("new_app")
        component.connector.add_app.return_value = new_app

        result = component._handle_create_app("req-1", {"name": "new_app", "flows": []})
        assert result["result"]["name"] == "new_app"
        component.connector.add_app.assert_called_once()

    def test_create_app_no_body(self):
        component = _make_mock_component()
        result = component._handle_create_app("req-1", None)
        assert result["error"]["code"] == ERROR_INVALID_REQUEST

    def test_create_app_no_name(self):
        component = _make_mock_component()
        result = component._handle_create_app("req-1", {"flows": []})
        assert result["error"]["code"] == ERROR_INVALID_REQUEST
        assert "name" in result["error"]["message"].lower()

    def test_create_app_duplicate_name(self):
        component = _make_mock_component()
        component.connector.add_app.side_effect = ValueError("App 'dup' already exists")

        result = component._handle_create_app("req-1", {"name": "dup", "flows": []})
        assert result["error"]["code"] == ERROR_CONFLICT

    def test_create_app_invalid_config(self):
        component = _make_mock_component()
        component.connector.add_app.side_effect = ValueError("Invalid config")

        result = component._handle_create_app("req-1", {"name": "bad", "flows": []})
        assert result["error"]["code"] == ERROR_INVALID_REQUEST


class TestControlServiceGetApp:
    """Tests for GET /apps/{name}."""

    def test_get_app_success(self):
        component = _make_mock_component()
        app = _make_mock_app("my_app")
        component.connector.get_app.return_value = app

        result = component._handle_get_app("req-1", "my_app")
        assert result["result"]["name"] == "my_app"
        assert "management_endpoints" in result["result"]

    def test_get_app_not_found(self):
        component = _make_mock_component()
        component.connector.get_app.return_value = None

        result = component._handle_get_app("req-1", "nonexistent")
        assert result["error"]["code"] == ERROR_NOT_FOUND


class TestControlServicePatchApp:
    """Tests for PATCH /apps/{name}."""

    def test_patch_disable_app(self):
        component = _make_mock_component()
        app = _make_mock_app("my_app")
        # After stop, get_info returns stopped state
        app.get_info.return_value = {
            "name": "my_app", "enabled": False, "status": "stopped",
            "num_instances": 1, "app_module": None,
        }
        component.connector.get_app.return_value = app

        result = component._handle_patch_app("req-1", "my_app", {"enabled": False})
        app.stop.assert_called_once()
        assert result["result"]["status"] == "stopped"

    def test_patch_enable_app(self):
        component = _make_mock_component()
        app = _make_mock_app("my_app", status="stopped", enabled=False)
        app.get_info.return_value = {
            "name": "my_app", "enabled": True, "status": "running",
            "num_instances": 1, "app_module": None,
        }
        component.connector.get_app.return_value = app

        result = component._handle_patch_app("req-1", "my_app", {"enabled": True})
        app.start.assert_called_once()

    def test_patch_app_not_found(self):
        component = _make_mock_component()
        component.connector.get_app.return_value = None

        result = component._handle_patch_app("req-1", "nonexistent", {"enabled": False})
        assert result["error"]["code"] == ERROR_NOT_FOUND

    def test_patch_app_no_body(self):
        component = _make_mock_component()
        result = component._handle_patch_app("req-1", "my_app", None)
        assert result["error"]["code"] == ERROR_INVALID_REQUEST


class TestControlServiceDeleteApp:
    """Tests for DELETE /apps/{name}."""

    def test_delete_app_success(self):
        component = _make_mock_component()
        result = component._handle_delete_app("req-1", "my_app")
        component.connector.remove_app.assert_called_once_with("my_app")
        assert result["result"]["deleted"] == "my_app"

    def test_delete_app_not_found(self):
        component = _make_mock_component()
        component.connector.remove_app.side_effect = ValueError("App 'x' not found")

        result = component._handle_delete_app("req-1", "x")
        assert result["error"]["code"] == ERROR_NOT_FOUND


class TestControlServiceCustomEndpoint:
    """Tests for custom app management endpoints."""

    def test_custom_endpoint_delegated(self):
        component = _make_mock_component()
        app = _make_mock_app("my_agent")
        app.handle_management_request.return_value = {"tools": ["tool1", "tool2"]}
        component.connector.get_app.return_value = app

        message = _make_mock_message(user_config={"role": "admin"})
        result = component._handle_custom_endpoint(
            "req-1", "GET", "my_agent", ["tools", "list"], {}, message
        )
        app.handle_management_request.assert_called_once_with(
            "GET", ["tools", "list"], {}, {"user_config": {"role": "admin"}}
        )
        assert result["result"]["tools"] == ["tool1", "tool2"]

    def test_custom_endpoint_not_handled(self):
        component = _make_mock_component()
        app = _make_mock_app("my_agent")
        app.handle_management_request.return_value = None
        component.connector.get_app.return_value = app

        result = component._handle_custom_endpoint(
            "req-1", "GET", "my_agent", ["unknown"], {}, MagicMock()
        )
        assert result["error"]["code"] == ERROR_METHOD_NOT_ALLOWED

    def test_custom_endpoint_app_not_found(self):
        component = _make_mock_component()
        component.connector.get_app.return_value = None

        result = component._handle_custom_endpoint(
            "req-1", "GET", "nonexistent", ["foo"], {}, MagicMock()
        )
        assert result["error"]["code"] == ERROR_NOT_FOUND


class TestControlServiceRouting:
    """Tests for request routing based on topic + method."""

    def test_route_get_apps(self):
        component = _make_mock_component()
        component.connector.get_apps.return_value = []

        result = component._route_request("req-1", "GET", "apps", None, [], {}, MagicMock())
        assert "apps" in result["result"]

    def test_route_post_apps(self):
        component = _make_mock_component()
        new_app = _make_mock_app("new")
        component.connector.add_app.return_value = new_app

        result = component._route_request(
            "req-1", "POST", "apps", None, [], {"name": "new", "flows": []}, MagicMock()
        )
        assert result["result"]["name"] == "new"

    def test_route_get_specific_app(self):
        component = _make_mock_component()
        app = _make_mock_app("my_app")
        component.connector.get_app.return_value = app

        result = component._route_request(
            "req-1", "GET", "apps", "my_app", [], {}, MagicMock()
        )
        assert result["result"]["name"] == "my_app"

    def test_route_delete_specific_app(self):
        component = _make_mock_component()
        result = component._route_request(
            "req-1", "DELETE", "apps", "my_app", [], {}, MagicMock()
        )
        assert result["result"]["deleted"] == "my_app"

    def test_route_invalid_method_on_collection(self):
        component = _make_mock_component()
        result = component._route_request(
            "req-1", "DELETE", "apps", None, [], {}, MagicMock()
        )
        assert result["error"]["code"] == ERROR_METHOD_NOT_ALLOWED

    def test_route_custom_endpoint(self):
        component = _make_mock_component()
        app = _make_mock_app("my_agent")
        app.handle_management_request.return_value = {"result": "ok"}
        component.connector.get_app.return_value = app

        result = component._route_request(
            "req-1", "GET", "apps", "my_agent", ["tools"], {}, MagicMock()
        )
        assert result["result"]["result"] == "ok"


class TestControlServiceJsonRpc:
    """Tests for JSON-RPC response format."""

    def test_success_response_format(self):
        response = ControlServiceComponent._success_response("req-1", {"foo": "bar"})
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "req-1"
        assert response["result"] == {"foo": "bar"}
        assert "error" not in response

    def test_error_response_format(self):
        response = ControlServiceComponent._error_response("req-1", -32001, "Not found")
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "req-1"
        assert response["error"]["code"] == -32001
        assert response["error"]["message"] == "Not found"
        assert "result" not in response

    def test_error_response_with_data(self):
        response = ControlServiceComponent._error_response(
            "req-1", -32001, "Not found", data={"extra": "info"}
        )
        assert response["error"]["data"] == {"extra": "info"}


class TestControlServiceRBACIntegration:
    """Tests for RBAC integration via ConfigResolver and Trust Manager."""

    def test_config_resolver_called_with_correct_operation_spec(self):
        """Verify ConfigResolver receives correct operation_spec for control plane access."""
        component = _make_mock_component(auth_type="default_rbac")
        message = _make_mock_message(user_config={"_enterprise_capabilities": ["sam:apps:read"]})

        mock_resolver = MagicMock()
        mock_resolver.validate_operation_config.return_value = {"valid": True}

        with patch(
            "solace_agent_mesh.services.control.component.MiddlewareRegistry.get_config_resolver",
            return_value=mock_resolver,
        ):
            result = component._authorize("GET", "apps", "my_app", [], message)

        assert result is None  # Authorized
        mock_resolver.validate_operation_config.assert_called_once()
        call_args = mock_resolver.validate_operation_config.call_args
        operation_spec = call_args[0][1]
        assert operation_spec["operation_type"] == "control_plane_access"
        assert operation_spec["method"] == "GET"
        assert operation_spec["app_name"] == "my_app"
        assert operation_spec["custom_path"] == []

    def test_config_resolver_denial_returns_auth_denied(self):
        """Verify that ConfigResolver denial produces ERROR_AUTH_DENIED."""
        component = _make_mock_component(auth_type="default_rbac")
        message = _make_mock_message(user_config={})

        mock_resolver = MagicMock()
        mock_resolver.validate_operation_config.return_value = {
            "valid": False,
            "reason": "insufficient_scopes",
        }

        with patch(
            "solace_agent_mesh.services.control.component.MiddlewareRegistry.get_config_resolver",
            return_value=mock_resolver,
        ):
            result = component._authorize("DELETE", "apps", "my_app", [], message)

        assert result is not None
        assert result["error"]["code"] == ERROR_AUTH_DENIED
        assert result["error"]["message"] == "Access denied"

    def test_config_resolver_approval_returns_none(self):
        """Verify that ConfigResolver approval returns None (authorized)."""
        component = _make_mock_component(auth_type="default_rbac")
        message = _make_mock_message(user_config={"_enterprise_capabilities": ["sam:apps:*"]})

        mock_resolver = MagicMock()
        mock_resolver.validate_operation_config.return_value = {"valid": True}

        with patch(
            "solace_agent_mesh.services.control.component.MiddlewareRegistry.get_config_resolver",
            return_value=mock_resolver,
        ):
            result = component._authorize("POST", "apps", None, [], message)

        assert result is None

    def test_config_resolver_custom_path_in_operation_spec(self):
        """Verify custom_path is passed through in the operation_spec."""
        component = _make_mock_component(auth_type="default_rbac")
        message = _make_mock_message()

        mock_resolver = MagicMock()
        mock_resolver.validate_operation_config.return_value = {"valid": True}

        with patch(
            "solace_agent_mesh.services.control.component.MiddlewareRegistry.get_config_resolver",
            return_value=mock_resolver,
        ):
            result = component._authorize("GET", "apps", "my_agent", ["tools", "list"], message)

        call_args = mock_resolver.validate_operation_config.call_args
        operation_spec = call_args[0][1]
        assert operation_spec["custom_path"] == ["tools", "list"]

    def test_extract_user_config_from_message(self):
        """Verify extraction of a2aUserConfig from message user properties."""
        component = _make_mock_component()
        user_config = {"_enterprise_capabilities": ["sam:apps:read"]}
        message = _make_mock_message(user_config=user_config)

        result = component._extract_user_config(message)
        assert result == user_config

    def test_extract_user_config_missing_returns_empty_dict(self):
        """Verify fallback to empty dict when a2aUserConfig is missing."""
        component = _make_mock_component()
        message = _make_mock_message()

        result = component._extract_user_config(message)
        assert result == {}

    def test_extract_user_config_non_dict_returns_empty_dict(self):
        """Verify fallback when a2aUserConfig is not a dict."""
        component = _make_mock_component()
        message = _make_mock_message(user_config="not_a_dict")

        result = component._extract_user_config(message)
        assert result == {}

    def test_trust_manager_auth_failure_sends_error_response(self):
        """When Trust Manager verification fails, an auth error response is sent."""
        component = _make_mock_component(auth_type="default_rbac")
        component.trust_manager = MagicMock()
        component.trust_manager.is_trust_card_topic.return_value = False
        component.trust_manager.verify_request_authentication.side_effect = ValueError(
            "Invalid JWT"
        )

        # Bind _handle_message_async and _send_response
        component._handle_message_async = ControlServiceComponent._handle_message_async.__get__(
            component
        )
        component._send_response = ControlServiceComponent._send_response.__get__(component)

        # Build a valid JSON-RPC message on a control topic
        payload = json.dumps({"jsonrpc": "2.0", "id": "req-123", "params": {"body": {}}})
        message = _make_mock_message(user_config={}, auth_token="bad.jwt")
        message.get_payload.return_value = payload
        message.get_user_properties.return_value["reply_to_topic"] = "reply/topic"

        topic = "testns/sam/v1/control/get/apps"
        asyncio.get_event_loop().run_until_complete(
            component._handle_message_async(message, topic)
        )

        # Verify error response was published
        component.publish_a2a_message.assert_called_once()
        call_kwargs = component.publish_a2a_message.call_args[1]
        response = call_kwargs["payload"]
        assert response["error"]["code"] == ERROR_AUTH_DENIED
        assert response["error"]["message"] == "Authentication failed"
        assert response["id"] == "req-123"

    def test_trust_manager_success_continues_to_authorize(self):
        """Successful Trust Manager verification proceeds to ConfigResolver authorization."""
        component = _make_mock_component(auth_type="default_rbac")
        component.trust_manager = MagicMock()
        component.trust_manager.is_trust_card_topic.return_value = False
        component.trust_manager.verify_request_authentication.return_value = {
            "user_id": "test_user"
        }

        # Bind _handle_message_async and _send_response
        component._handle_message_async = ControlServiceComponent._handle_message_async.__get__(
            component
        )
        component._send_response = ControlServiceComponent._send_response.__get__(component)

        # Build a valid JSON-RPC message
        payload = json.dumps({"jsonrpc": "2.0", "id": "req-456", "params": {"body": {}}})
        message = _make_mock_message(user_config={}, auth_token="valid.jwt")
        message.get_payload.return_value = payload
        message.get_user_properties.return_value["reply_to_topic"] = "reply/topic"

        # Mock ConfigResolver to allow
        mock_resolver = MagicMock()
        mock_resolver.validate_operation_config.return_value = {"valid": True}

        topic = "testns/sam/v1/control/get/apps"
        component.connector.get_apps.return_value = []

        with patch(
            "solace_agent_mesh.services.control.component.MiddlewareRegistry.get_config_resolver",
            return_value=mock_resolver,
        ):
            asyncio.get_event_loop().run_until_complete(
                component._handle_message_async(message, topic)
            )

        # Trust Manager was called with correct args
        component.trust_manager.verify_request_authentication.assert_called_once_with(
            message=message,
            task_id="req-456",
            namespace="testns",
            jsonrpc_request_id="req-456",
        )
        # ConfigResolver was also called (auth passed through)
        mock_resolver.validate_operation_config.assert_called_once()

    def test_trust_manager_called_with_request_id_as_task_id(self):
        """verify_request_authentication receives JSON-RPC id as task_id."""
        component = _make_mock_component(auth_type="default_rbac")
        component.trust_manager = MagicMock()
        component.trust_manager.is_trust_card_topic.return_value = False
        component.trust_manager.verify_request_authentication.return_value = {"user_id": "u1"}

        component._handle_message_async = ControlServiceComponent._handle_message_async.__get__(
            component
        )
        component._send_response = ControlServiceComponent._send_response.__get__(component)

        payload = json.dumps({"jsonrpc": "2.0", "id": "my-unique-id", "params": {"body": {}}})
        message = _make_mock_message()
        message.get_payload.return_value = payload
        message.get_user_properties.return_value["reply_to_topic"] = "reply/topic"

        mock_resolver = MagicMock()
        mock_resolver.validate_operation_config.return_value = {"valid": True}

        topic = "testns/sam/v1/control/get/apps"
        component.connector.get_apps.return_value = []

        with patch(
            "solace_agent_mesh.services.control.component.MiddlewareRegistry.get_config_resolver",
            return_value=mock_resolver,
        ):
            asyncio.get_event_loop().run_until_complete(
                component._handle_message_async(message, topic)
            )

        call_kwargs = component.trust_manager.verify_request_authentication.call_args[1]
        assert call_kwargs["task_id"] == "my-unique-id"
        assert call_kwargs["jsonrpc_request_id"] == "my-unique-id"
        assert call_kwargs["namespace"] == "testns"

    def test_error_messages_do_not_leak_topic(self):
        """Verify error messages don't contain raw topic strings."""
        component = _make_mock_component(auth_type="default_rbac")

        mock_resolver = MagicMock()
        mock_resolver.validate_operation_config.return_value = {
            "valid": False,
            "reason": "denied",
        }

        message = _make_mock_message()
        with patch(
            "solace_agent_mesh.services.control.component.MiddlewareRegistry.get_config_resolver",
            return_value=mock_resolver,
        ):
            result = component._authorize("GET", "apps", None, [], message)

        # Error message should be generic, not contain topic or auth_type
        assert "topic" not in result["error"]["message"].lower()
        assert "default_rbac" not in result["error"]["message"]

    def test_custom_endpoint_passes_user_config_in_context(self):
        """Verify custom endpoint handler passes user_config in context dict."""
        component = _make_mock_component()
        app = _make_mock_app("my_agent")
        app.handle_management_request.return_value = {"ok": True}
        component.connector.get_app.return_value = app

        user_config = {"_enterprise_capabilities": ["sam:apps/my_agent:manage"]}
        message = _make_mock_message(user_config=user_config)

        result = component._handle_custom_endpoint(
            "req-1", "GET", "my_agent", ["status"], {}, message
        )

        call_args = app.handle_management_request.call_args
        context = call_args[0][3]
        assert "user_config" in context
        assert context["user_config"] == user_config
