"""
A2A Message Validator for integration tests.
Patches message publishing methods to intercept and validate A2A messages.
"""

import functools
import json
import importlib.resources
from typing import Any, Dict, List
from unittest.mock import patch

import pytest
from jsonschema import Draft7Validator, RefResolver, ValidationError



METHOD_TO_SCHEMA_MAP = {
    "message/send": "SendMessageRequest",
    "message/stream": "SendStreamingMessageRequest",
    "tasks/get": "GetTaskRequest",
    "tasks/cancel": "CancelTaskRequest",
    "tasks/pushNotificationConfig/set": "SetTaskPushNotificationConfigRequest",
    "tasks/pushNotificationConfig/get": "GetTaskPushNotificationConfigRequest",
    "tasks/pushNotificationConfig/list": "ListTaskPushNotificationConfigRequest",
    "tasks/pushNotificationConfig/delete": "DeleteTaskPushNotificationConfigRequest",
    "tasks/resubscribe": "TaskResubscriptionRequest",
    "agent/getAuthenticatedExtendedCard": "GetAuthenticatedExtendedCardRequest",
}


class A2AMessageValidator:
    """
    Intercepts and validates A2A messages published by SAM components against the
    official a2a.json schema.
    """

    def __init__(self):
        self._patched_targets: List[Dict[str, Any]] = []
        self.active = False
        self.schema = self._load_schema()
        self.validator = self._create_validator(self.schema)

    def _load_schema(self) -> Dict[str, Any]:
        """Loads the A2A JSON schema from the installed package."""
        try:
            # Use importlib.resources to find the schema file within the package.
            # This works whether the package is installed or in editable mode.
            with importlib.resources.path(
                "solace_agent_mesh.common.a2a_spec", "a2a.json"
            ) as schema_path:
                with open(schema_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (ModuleNotFoundError, FileNotFoundError):
            pytest.fail(
                "A2A Validator: Schema file 'a2a.json' not found in package "
                "'solace_agent_mesh.common.a2a_spec'. "
                "Ensure the package is installed correctly or run 'scripts/sync_a2a_schema.py'."
            )
        except json.JSONDecodeError as e:
            pytest.fail(f"A2A Validator: Failed to parse schema file: {e}")

    def _create_validator(self, schema: Dict[str, Any]) -> Draft7Validator:
        """Creates a jsonschema validator with a resolver for local $refs."""
        resolver = RefResolver.from_schema(schema)
        return Draft7Validator(schema, resolver=resolver)

    def activate(self, components_to_patch: List[Any]):
        """
        Activates the validator by patching message publishing methods on components.

        Args:
            components_to_patch: A list of component instances.
                                 It will patch 'publish_a2a_message' on TestGatewayComponent instances
                                 and '_publish_a2a_message' on SamAgentComponent instances.
        """
        if self.active:
            self.deactivate()
        from solace_agent_mesh.agent.sac.component import SamAgentComponent
        from sam_test_infrastructure.gateway_interface.component import (
            TestGatewayComponent,
        )
        from solace_agent_mesh.agent.proxies.base.component import BaseProxyComponent

        for component_instance in components_to_patch:
            method_name_to_patch = None
            is_sam_agent_component = isinstance(component_instance, SamAgentComponent)
            is_test_gateway_component = isinstance(
                component_instance, TestGatewayComponent
            )
            is_base_proxy_component = isinstance(component_instance, BaseProxyComponent)

            if is_sam_agent_component or is_base_proxy_component:
                method_name_to_patch = "_publish_a2a_message"
            elif is_test_gateway_component:
                method_name_to_patch = "publish_a2a_message"
            else:
                print(
                    f"A2AMessageValidator: Warning - Component {type(component_instance)} is not a recognized type for patching."
                )
                continue

            if not hasattr(component_instance, method_name_to_patch):
                print(
                    f"A2AMessageValidator: Warning - Component {type(component_instance)} has no method {method_name_to_patch}"
                )
                continue

            original_method = getattr(component_instance, method_name_to_patch)

            def side_effect_with_validation(
                original_method_ref,
                component_instance_at_patch_time,
                current_method_name,
                *args,
                **kwargs,
            ):
                return_value = original_method_ref(*args, **kwargs)

                payload_to_validate = None
                topic_to_validate = None
                source_info = f"Patched {component_instance_at_patch_time.__class__.__name__}.{current_method_name}"

                if current_method_name == "_publish_a2a_message":
                    payload_to_validate = kwargs.get("payload")
                    topic_to_validate = kwargs.get("topic")
                    if payload_to_validate is None or topic_to_validate is None:
                        if len(args) >= 2:
                            payload_to_validate = args[0]
                            topic_to_validate = args[1]
                        else:
                            pytest.fail(
                                f"A2A Validator: Incorrect args/kwargs for {source_info}. Expected payload, topic. Got args: {args}, kwargs: {kwargs}"
                            )
                elif current_method_name == "publish_a2a_message":
                    topic_to_validate = kwargs.get("topic")
                    payload_to_validate = kwargs.get("payload")
                    if payload_to_validate is None or topic_to_validate is None:
                        if len(args) >= 2:
                            topic_to_validate = args[0]
                            payload_to_validate = args[1]
                        else:
                            pytest.fail(
                                f"A2A Validator: Incorrect args/kwargs for {source_info}. Expected topic, payload. Got args: {args}, kwargs: {kwargs}"
                            )

                if payload_to_validate is not None and topic_to_validate is not None:
                    self.validate_message(
                        payload_to_validate, topic_to_validate, source_info
                    )
                else:
                    print(
                        f"A2AMessageValidator: Warning - Could not extract payload/topic from {source_info} call. Args: {args}, Kwargs: {kwargs}"
                    )

                return return_value

            try:
                patcher = patch.object(
                    component_instance, method_name_to_patch, autospec=True
                )
                mock_method = patcher.start()
                bound_side_effect = functools.partial(
                    side_effect_with_validation,
                    original_method,
                    component_instance,
                    method_name_to_patch,
                )
                mock_method.side_effect = bound_side_effect

                self._patched_targets.append(
                    {
                        "patcher": patcher,
                        "component": component_instance,
                        "method_name": method_name_to_patch,
                    }
                )
            except Exception as e:
                print(
                    f"A2AMessageValidator: Failed to patch {method_name_to_patch} on {component_instance}: {e}"
                )
                self.deactivate()
                raise

        if self._patched_targets:
            self.active = True
            print(
                f"A2AMessageValidator: Activated. Monitoring {len(self._patched_targets)} methods."
            )

    def deactivate(self):
        """Deactivates the validator by stopping all active patches."""
        for patch_info in self._patched_targets:
            try:
                patch_info["patcher"].stop()
            except RuntimeError:
                pass
        self._patched_targets = []
        self.active = False
        print("A2AMessageValidator: Deactivated.")

    def validate_message(
        self, payload: Dict, topic: str, source_info: str = "Unknown source"
    ):
        """
        Validates a single A2A message payload against the official a2a.json schema.
        Fails the test immediately using pytest.fail() if validation errors occur.
        """
        if "/discovery/agentcards" in topic:
            return

        schema_to_use = None
        is_request = "method" in payload

        try:
            if is_request:
                method = payload.get("method")
                schema_name = METHOD_TO_SCHEMA_MAP.get(method)
                if schema_name and schema_name in self.schema["definitions"]:
                    schema_to_use = self.schema["definitions"][schema_name]
                else:
                    # Fallback to generic request if specific one not found
                    schema_to_use = self.schema["definitions"]["JSONRPCRequest"]
            else:
                # For responses, try to find a specific schema based on the result 'kind'.
                schema_to_use = self.schema["definitions"]["JSONRPCResponse"]  # Default
                result = payload.get("result")
                if isinstance(result, dict):
                    kind = result.get("kind")
                    if kind == "task":
                        schema_to_use = self.schema["definitions"][
                            "GetTaskSuccessResponse"
                        ]
                    elif kind == "message":
                        schema_to_use = self.schema["definitions"][
                            "SendMessageSuccessResponse"
                        ]
                    elif kind in ["status-update", "artifact-update"]:
                        schema_to_use = self.schema["definitions"][
                            "SendStreamingMessageSuccessResponse"
                        ]

            self.validator.check_schema(schema_to_use)
            self.validator.validate(payload, schema_to_use)

            # The JSON-RPC spec states that 'result' and 'error' MUST NOT coexist.
            # The generated schema might use 'anyOf' which doesn't enforce this.
            # We add an explicit check here to ensure compliance.
            if not is_request and "result" in payload and "error" in payload:
                raise ValidationError(
                    "'result' and 'error' are mutually exclusive and cannot be present in the same response.",
                    validator="dependencies",
                    validator_value={"result": ["error"], "error": ["result"]},
                    instance=payload,
                    schema=schema_to_use,
                )

        except ValidationError as e:
            pytest.fail(
                f"A2A Schema Validation Error from {source_info} on topic '{topic}':\n"
                f"Message: {e.message}\n"
                f"Path: {list(e.path)}\n"
                f"Validator: {e.validator} = {e.validator_value}\n"
                f"Payload: {json.dumps(payload, indent=2)}"
            )
        except Exception as e:
            pytest.fail(
                f"A2A Validation Error (Structure) from {source_info} on topic '{topic}': {e}\n"
                f"Payload: {json.dumps(payload, indent=2)}"
            )

        print(
            f"A2AMessageValidator: Successfully validated message from {source_info} on topic '{topic}' (ID: {payload.get('id')})"
        )
