"""
Control Service Component for Solace Agent Mesh.
Handles JSON-RPC control plane requests for dynamic app management.
"""

import json
import logging
from typing import Any, Dict, Optional

from solace_ai_connector.common.message import Message as SolaceMessage

from solace_agent_mesh.common.sac.sam_component_base import SamComponentBase
from solace_agent_mesh.common.middleware.registry import MiddlewareRegistry
from solace_agent_mesh.common.a2a import (
    parse_control_topic,
    topic_matches_subscription,
    get_control_subscription_topic,
)

log = logging.getLogger(__name__)

# JSON-RPC error codes
ERROR_INVALID_REQUEST = -32600
ERROR_METHOD_NOT_ALLOWED = -32601
ERROR_NOT_FOUND = -32001
ERROR_CONFLICT = -32002
ERROR_AUTH_DENIED = -32003
ERROR_OPERATION_FAILED = -32004

info = {
    "class_name": "ControlServiceComponent",
    "description": "Control plane component for dynamic app management via JSON-RPC over broker.",
}


class ControlServiceComponent(SamComponentBase):
    """
    Control Service Component - Dynamic app management via JSON-RPC.

    Handles RESTful operations over the broker:
    - GET /apps — list all apps
    - POST /apps — create a new app
    - GET /apps/{name} — get app details
    - PUT /apps/{name} — replace app config
    - PATCH /apps/{name} — partial update (enable/disable)
    - DELETE /apps/{name} — remove an app
    - any /apps/{name}/{path} — delegate to app's custom handler
    """

    def get_config(self, key: str, default: Any = None) -> Any:
        """Override get_config to look inside nested 'app_config' dictionary."""
        if "app_config" in self.component_config:
            value = self.component_config["app_config"].get(key)
            if value is not None:
                return value
        return super().get_config(key, default)

    def __init__(self, **kwargs):
        """Initialize the ControlServiceComponent."""
        super().__init__(info, **kwargs)
        log.info("%s Initializing Control Service Component...", self.log_identifier)

        # Authorization config
        auth_config = self.get_config("authorization", {"type": "none"})
        self.auth_type = auth_config.get("type", "none") if isinstance(auth_config, dict) else "none"

        log.info(
            "%s Control Service initialized (authorization: %s)",
            self.log_identifier,
            self.auth_type,
        )

    async def _handle_message_async(self, message, topic: str) -> None:
        """Handle incoming control plane messages."""
        log.debug(
            "%s Received control message on topic: %s",
            self.log_identifier,
            topic,
        )

        processed_successfully = False

        try:
            # Handle trust card messages first (enterprise feature)
            if (
                self.trust_manager
                and self.trust_manager.is_trust_card_topic(topic)
            ):
                payload = message.get_payload()
                if isinstance(payload, bytes):
                    payload = json.loads(payload.decode("utf-8"))
                elif isinstance(payload, str):
                    payload = json.loads(payload)
                await self.trust_manager.handle_trust_card_message(payload, topic)
                processed_successfully = True
                return

            # Verify this is a control topic
            if not topic_matches_subscription(
                topic, get_control_subscription_topic(self.namespace)
            ):
                log.debug(
                    "%s Ignoring non-control topic: %s",
                    self.log_identifier,
                    topic,
                )
                processed_successfully = True
                return

            # Parse the payload
            payload = message.get_payload()
            if isinstance(payload, bytes):
                payload = json.loads(payload.decode("utf-8"))
            elif isinstance(payload, str):
                payload = json.loads(payload)

            # Validate JSON-RPC format
            if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
                response = self._error_response(
                    payload.get("id") if isinstance(payload, dict) else None,
                    ERROR_INVALID_REQUEST,
                    "Invalid JSON-RPC 2.0 request",
                )
                self._send_response(message, response)
                processed_successfully = True
                return

            request_id = payload.get("id")
            params = payload.get("params", {})
            body = params.get("body", {})

            # Enterprise feature: Verify user authentication if trust manager enabled
            # Same pattern as agent/protocol/event_handlers.py:354-433
            if self.trust_manager:
                verification_task_id = str(request_id) if request_id else None
                if verification_task_id:
                    try:
                        verified_user_identity = (
                            self.trust_manager.verify_request_authentication(
                                message=message,
                                task_id=verification_task_id,
                                namespace=self.namespace,
                                jsonrpc_request_id=request_id,
                            )
                        )

                        if verified_user_identity:
                            log.info(
                                "%s Successfully authenticated user '%s' for request %s",
                                self.log_identifier,
                                verified_user_identity.get("user_id"),
                                request_id,
                            )

                    except Exception as e:
                        log.error(
                            "%s Authentication failed for request %s: %s",
                            self.log_identifier,
                            request_id,
                            e,
                        )
                        error_data = {
                            "reason": "authentication_failed",
                        }
                        if hasattr(e, "create_error_response_data"):
                            error_data = e.create_error_response_data()

                        response = self._error_response(
                            request_id,
                            ERROR_AUTH_DENIED,
                            "Authentication failed",
                            data=error_data,
                        )
                        self._send_response(message, response)
                        processed_successfully = True
                        return

            # Parse the topic to determine the method/resource/app
            method, resource, app_name, custom_path = parse_control_topic(
                self.namespace, topic
            )
            # Uppercase for internal routing (topic stores lowercase)
            method = method.upper() if method else ""

            if resource is None:
                response = self._error_response(
                    request_id,
                    ERROR_INVALID_REQUEST,
                    "Unrecognized control request",
                )
                self._send_response(message, response)
                processed_successfully = True
                return

            # Authorize the request
            auth_error = self._authorize(method, resource, app_name, custom_path, message)
            if auth_error:
                self._send_response(message, auth_error)
                processed_successfully = True
                return

            # Route the request
            response = self._route_request(
                request_id, method, resource, app_name, custom_path, body, message
            )
            self._send_response(message, response)
            processed_successfully = True

        except Exception as e:
            log.error(
                "%s Error handling control message on topic %s: %s",
                self.log_identifier,
                topic,
                e,
                exc_info=True,
            )
            # Try to send an error response
            try:
                request_id = None
                if isinstance(payload, dict):
                    request_id = payload.get("id")
                response = self._error_response(
                    request_id,
                    ERROR_OPERATION_FAILED,
                    "Internal server error",
                )
                self._send_response(message, response)
            except Exception:
                log.exception(
                    "%s Failed to send error response",
                    self.log_identifier,
                )
            processed_successfully = False
        finally:
            if hasattr(message, "call_acknowledgements"):
                try:
                    if processed_successfully:
                        message.call_acknowledgements()
                    else:
                        message.call_negative_acknowledgements()
                except Exception as ack_error:
                    log.warning(
                        "%s Error acknowledging message: %s",
                        self.log_identifier,
                        ack_error,
                    )

    def _extract_user_config(self, message) -> Dict[str, Any]:
        """Extract user configuration from message user properties.

        Follows the same pattern as agent/protocol/event_handlers.py for
        extracting a2aUserConfig from Solace message user properties.

        Returns:
            Dict with user configuration, or empty dict if not present.
        """
        if not hasattr(message, "get_user_properties"):
            return {}
        user_props = message.get_user_properties()
        if not user_props:
            return {}
        a2a_user_config = user_props.get("a2aUserConfig", {})
        if not isinstance(a2a_user_config, dict):
            log.warning(
                "%s a2aUserConfig is not a dict, using empty dict instead",
                self.log_identifier,
            )
            return {}
        return a2a_user_config

    def _authorize(self, method, resource, app_name, custom_path, message):
        """Check authorization for the request.

        Uses the ConfigResolver middleware pattern (same as agents and gateways)
        to delegate authorization decisions. The default ConfigResolver allows all
        operations; Enterprise overrides this with scope-based RBAC.

        Trust Manager JWT verification is handled separately in _handle_message_async()
        before this method is called, matching the agent pattern.

        Returns an error response dict if denied, or None if authorized.
        """
        if self.auth_type == "none":
            return None

        if self.auth_type == "deny_all":
            return self._error_response(
                None, ERROR_AUTH_DENIED, "All control operations are denied"
            )

        # Extract user configuration from message
        user_config = self._extract_user_config(message)

        # Delegate authorization to ConfigResolver (Enterprise RBAC when installed)
        config_resolver = MiddlewareRegistry.get_config_resolver()
        operation_spec = {
            "operation_type": "control_plane_access",
            "method": method,
            "app_name": app_name,
            "custom_path": custom_path or [],
        }
        validation_context = {
            "resource": resource,
            "component_type": "control_service",
        }
        validation_result = config_resolver.validate_operation_config(
            user_config, operation_spec, validation_context
        )

        if not validation_result.get("valid", False):
            reason = validation_result.get("reason", "authorization_denied")
            log.info(
                "%s Control plane access denied: method=%s, app=%s, reason=%s",
                self.log_identifier,
                method,
                app_name or "(collection)",
                reason,
            )
            return self._error_response(
                None, ERROR_AUTH_DENIED, "Access denied"
            )

        log.info(
            "%s Control plane access granted: method=%s, app=%s",
            self.log_identifier,
            method,
            app_name or "(collection)",
        )
        return None

    def _route_request(self, request_id, method, resource, app_name, custom_path, body, message):
        """Route the request to the appropriate handler."""
        connector = self.connector

        if custom_path:
            return self._handle_custom_endpoint(
                request_id, method, app_name, custom_path, body, message
            )

        if resource == "apps" and app_name is None:
            # Collection endpoints
            if method == "GET":
                return self._handle_list_apps(request_id)
            elif method == "POST":
                return self._handle_create_app(request_id, body)
            else:
                return self._error_response(
                    request_id,
                    ERROR_METHOD_NOT_ALLOWED,
                    f"Method '{method}' not allowed on /apps collection",
                )

        if resource == "apps" and app_name is not None:
            # Individual app endpoints
            if method == "GET":
                return self._handle_get_app(request_id, app_name)
            elif method == "PUT":
                return self._handle_update_app(request_id, app_name, body)
            elif method == "PATCH":
                return self._handle_patch_app(request_id, app_name, body)
            elif method == "DELETE":
                return self._handle_delete_app(request_id, app_name)
            else:
                return self._error_response(
                    request_id,
                    ERROR_METHOD_NOT_ALLOWED,
                    f"Method '{method}' not allowed on /apps/{{name}}",
                )

        return self._error_response(
            request_id, ERROR_INVALID_REQUEST, "Unknown resource"
        )

    def _handle_list_apps(self, request_id):
        """GET /apps — list all apps with basic info."""
        apps = self.connector.get_apps()
        apps_info = [app.get_info() for app in apps]
        return self._success_response(request_id, {"apps": apps_info})

    def _handle_create_app(self, request_id, body):
        """POST /apps — create and start a new app."""
        if not body or not isinstance(body, dict):
            return self._error_response(
                request_id, ERROR_INVALID_REQUEST, "Request body must be a JSON object"
            )

        app_name = body.get("name")
        if not app_name:
            return self._error_response(
                request_id, ERROR_INVALID_REQUEST, "App name is required in body"
            )

        try:
            app = self.connector.add_app(body)
            return self._success_response(request_id, app.get_info())
        except ValueError as e:
            # Duplicate name or invalid config
            if "already exists" in str(e):
                return self._error_response(request_id, ERROR_CONFLICT, str(e))
            return self._error_response(request_id, ERROR_INVALID_REQUEST, str(e))
        except Exception as e:
            return self._error_response(
                request_id, ERROR_OPERATION_FAILED, f"Failed to create app: {e}"
            )

    def _handle_get_app(self, request_id, app_name):
        """GET /apps/{name} — get detailed info for a specific app."""
        app = self.connector.get_app(app_name)
        if not app:
            return self._error_response(
                request_id, ERROR_NOT_FOUND, f"App '{app_name}' not found"
            )

        result = app.get_info()
        result["management_endpoints"] = app.get_management_endpoints()
        return self._success_response(request_id, result)

    def _handle_update_app(self, request_id, app_name, body):
        """PUT /apps/{name} — replace app config (stop/reconfig/start)."""
        if not body or not isinstance(body, dict):
            return self._error_response(
                request_id, ERROR_INVALID_REQUEST, "Request body must be a JSON object"
            )

        app = self.connector.get_app(app_name)
        if not app:
            return self._error_response(
                request_id, ERROR_NOT_FOUND, f"App '{app_name}' not found"
            )

        try:
            # Stop and remove the old app
            self.connector.remove_app(app_name)

            # Ensure the new config uses the same name
            body["name"] = app_name

            # Create the new app with the updated config
            new_app = self.connector.add_app(body)
            return self._success_response(request_id, new_app.get_info())
        except Exception as e:
            return self._error_response(
                request_id, ERROR_OPERATION_FAILED, f"Failed to update app: {e}"
            )

    def _handle_patch_app(self, request_id, app_name, body):
        """PATCH /apps/{name} — partial update (e.g., enable/disable)."""
        if not body or not isinstance(body, dict):
            return self._error_response(
                request_id, ERROR_INVALID_REQUEST, "Request body must be a JSON object"
            )

        app = self.connector.get_app(app_name)
        if not app:
            return self._error_response(
                request_id, ERROR_NOT_FOUND, f"App '{app_name}' not found"
            )

        try:
            if "enabled" in body:
                if body["enabled"] is False:
                    app.stop()
                elif body["enabled"] is True:
                    app.start()

            return self._success_response(request_id, app.get_info())
        except RuntimeError as e:
            return self._error_response(
                request_id, ERROR_OPERATION_FAILED, str(e)
            )
        except Exception as e:
            return self._error_response(
                request_id, ERROR_OPERATION_FAILED, f"Failed to patch app: {e}"
            )

    def _handle_delete_app(self, request_id, app_name):
        """DELETE /apps/{name} — remove an app."""
        try:
            self.connector.remove_app(app_name)
            return self._success_response(request_id, {"deleted": app_name})
        except ValueError as e:
            return self._error_response(request_id, ERROR_NOT_FOUND, str(e))
        except Exception as e:
            return self._error_response(
                request_id, ERROR_OPERATION_FAILED, f"Failed to delete app: {e}"
            )

    def _handle_custom_endpoint(self, request_id, method, app_name, custom_path, body, message):
        """Route to app's custom management handler."""
        app = self.connector.get_app(app_name)
        if not app:
            return self._error_response(
                request_id, ERROR_NOT_FOUND, f"App '{app_name}' not found"
            )

        context = {"user_config": self._extract_user_config(message)}
        result = app.handle_management_request(method, custom_path, body, context)
        if result is None:
            return self._error_response(
                request_id,
                ERROR_METHOD_NOT_ALLOWED,
                f"App '{app_name}' does not handle endpoint: {'/'.join(custom_path)}",
            )

        return self._success_response(request_id, result)

    def _send_response(self, request_message, response):
        """Publish the JSON-RPC response to the requester's reply-to topic."""
        # Get the reply-to topic from the incoming message
        reply_to = None
        if hasattr(request_message, "get_user_properties"):
            user_props = request_message.get_user_properties()
            if user_props:
                reply_to = user_props.get("reply_to_topic") or user_props.get("reply-to")

        if not reply_to:
            # Try to get reply-to from message topic metadata
            reply_to = getattr(request_message, "reply_to_topic", None)

        if not reply_to:
            log.warning(
                "%s No reply-to topic for control response, dropping response: %s",
                self.log_identifier,
                response,
            )
            return

        try:
            self.publish_a2a_message(
                payload=response,
                topic=reply_to,
                user_properties={},
            )
        except Exception as e:
            log.error(
                "%s Failed to publish control response to %s: %s",
                self.log_identifier,
                reply_to,
                e,
            )

    @staticmethod
    def _success_response(request_id, result):
        """Build a JSON-RPC 2.0 success response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    @staticmethod
    def _error_response(request_id, code, message_text, data=None):
        """Build a JSON-RPC 2.0 error response."""
        error = {"code": code, "message": message_text}
        if data is not None:
            error["data"] = data
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": error,
        }

    def _get_component_id(self) -> str:
        """Return unique identifier for this component."""
        return "control_service"

    def _get_component_type(self) -> str:
        """Return component type."""
        return "service"

    def _pre_async_cleanup(self) -> None:
        """Cleanup before async operations stop."""
        if self.trust_manager:
            try:
                log.info("%s Cleaning up Trust Manager...", self.log_identifier)
                self.trust_manager.cleanup(self.cancel_timer)
                log.info("%s Trust Manager cleanup complete", self.log_identifier)
            except Exception as e:
                log.error(
                    "%s Error during Trust Manager cleanup: %s", self.log_identifier, e
                )

    async def _async_setup_and_run(self) -> None:
        """Async initialization — delegates to base class for Trust Manager init."""
        await super()._async_setup_and_run()
