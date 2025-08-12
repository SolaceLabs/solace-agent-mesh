"""
A2A Message Validator for integration tests.
Patches message publishing methods to intercept and validate A2A messages.
"""

import functools
from typing import Any, Dict, List
from unittest.mock import patch
import pytest

from solace_agent_mesh.common.types import (
    JSONRPCResponse,
    Task,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    JSONRPCError,
    InternalError,
)


class A2AMessageValidator:
    """
    Intercepts and validates A2A messages published by SAM components.
    """

    def __init__(self):
        self._patched_targets: List[Dict[str, Any]] = []
        self.active = False

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

        for component_instance in components_to_patch:
            method_name_to_patch = None
            is_sam_agent_component = isinstance(component_instance, SamAgentComponent)
            is_test_gateway_component = isinstance(
                component_instance, TestGatewayComponent
            )

            if is_sam_agent_component:
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
        Validates a single A2A message payload and topic.
        Fails the test immediately using pytest.fail() if validation errors occur.
        """
        if "/discovery/agentcards" in topic:
            return

        try:
            if not isinstance(payload, dict):
                pytest.fail(
                    f"A2A Validation Error (JSON-RPC - Payload Type) from {source_info} on topic '{topic}': Payload is not a dict (type: {type(payload)}).\nPayload: {payload}"
                )

            jsonrpc_version = payload.get("jsonrpc")
            if jsonrpc_version != "2.0":
                pytest.fail(
                    f"A2A Validation Error (JSON-RPC - Version) from {source_info} on topic '{topic}': jsonrpc version is '{jsonrpc_version}', expected '2.0'.\nPayload: {payload}"
                )

            if "id" not in payload:
                pytest.fail(
                    f"A2A Validation Error (JSON-RPC - ID) from {source_info} on topic '{topic}': 'id' field is missing.\nPayload: {payload}"
                )

            has_result = "result" in payload and payload["result"] is not None
            has_error = "error" in payload and payload["error"] is not None
            has_method = "method" in payload and payload["method"] is not None

            if has_method:
                if has_result or has_error:
                    pytest.fail(
                        f"A2A Validation Error (JSON-RPC - Request Structure) from {source_info} on topic '{topic}': Request payload must not contain 'result' or 'error'.\nPayload: {payload}"
                    )
                if "params" not in payload:
                    pass
            elif has_result or has_error:
                if not (has_result ^ has_error):
                    err_msg = (
                        "must have either 'result' or 'error', but not both or neither"
                    )
                    if has_result and has_error:
                        err_msg = "must not have both 'result' and 'error'"
                    elif not has_result and not has_error:
                        err_msg = "must have either 'result' or 'error'"
                    pytest.fail(
                        f"A2A Validation Error (JSON-RPC - Response Structure) from {source_info} on topic '{topic}': Response payload {err_msg}.\nPayload: {payload}"
                    )
                JSONRPCResponse(**payload)
            else:
                pytest.fail(
                    f"A2A Validation Error (JSON-RPC - Unknown Structure) from {source_info} on topic '{topic}': Payload must contain 'method' (for requests) or 'result'/'error' (for responses).\nPayload: {payload}"
                )

        except Exception as e:
            pytest.fail(
                f"A2A Validation Error (JSON-RPC Structure) from {source_info} on topic '{topic}': {e}\nPayload: {str(payload)[:500]}..."
            )

        if payload.get("result"):
            result_data = payload["result"]
            if not isinstance(result_data, dict):
                pytest.fail(
                    f"A2A Validation Error (Result Type) from {source_info} on topic '{topic}': 'result' field is not a dictionary.\nResult: {result_data}"
                )

            possible_event_models = [
                Task,
                TaskStatusUpdateEvent,
                TaskArtifactUpdateEvent,
            ]
            validated_model = False
            for model_class in possible_event_models:
                try:
                    model_class(**result_data)
                    validated_model = True
                    break
                except Exception:
                    pass

            if not validated_model:
                pytest.fail(
                    f"A2A Validation Error (Result Model) from {source_info} on topic '{topic}': Result data does not match any known A2A event model (Task, TaskStatusUpdateEvent, TaskArtifactUpdateEvent).\nResult: {str(result_data)[:500]}..."
                )

        elif payload.get("error"):
            error_data = payload["error"]
            if not isinstance(error_data, dict):
                pytest.fail(
                    f"A2A Validation Error (Error Type) from {source_info} on topic '{topic}': 'error' field is not a dictionary.\nError: {error_data}"
                )
            try:
                try:
                    InternalError(**error_data)
                except Exception:
                    JSONRPCError(**error_data)
            except Exception as e:
                pytest.fail(
                    f"A2A Validation Error (Error Model) from {source_info} on topic '{topic}': Error data does not match JSONRPCError or InternalError model. Error: {e}\nError Data: {str(error_data)[:500]}..."
                )

        try:
            if not (isinstance(topic, str) and topic.strip()):
                pytest.fail(
                    f"A2A Validation Error (Topic - Empty/Type) from {source_info} for payload (id: {payload.get('id')}): Topic is not a non-empty string (got: '{topic}')."
                )
        except Exception as e:
            pytest.fail(
                f"A2A Validation Error (Topic Structure) from {source_info} for payload (id: {payload.get('id')}): {e}\nTopic: {topic}"
            )

        print(
            f"A2AMessageValidator: Successfully validated message from {source_info} on topic '{topic}' (ID: {payload.get('id')})"
        )
