"""
A2A Message Validator for integration tests.
Patches message publishing methods to intercept and validate A2A messages.
"""

import functools
import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest
from jsonschema import Draft7Validator, RefResolver, ValidationError


# Define the path to the schema, assuming the script is run from the project root.
# This path needs to be correct relative to where pytest is executed.
SCHEMA_PATH = (
    Path.cwd() / "src" / "solace_agent_mesh" / "common" / "a2a_spec" / "a2a.json"
)


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
        """Loads the A2A JSON schema from file."""
        try:
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            pytest.fail(
                f"A2A Validator: Schema file not found at {SCHEMA_PATH}. "
                "Please run 'scripts/sync_a2a_schema.py' to download it."
            )
        except json.JSONDecodeError as e:
            pytest.fail(f"A2A Validator: Failed to parse schema file {SCHEMA_PATH}: {e}")

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
        Validates a single A2A message payload against the official a2a.json schema.
        Fails the test immediately using pytest.fail() if validation errors occur.
        """
        if "/discovery/agentcards" in topic:
            return

        schema_to_use = None
        is_request = "method" in payload

        try:
            if is_request:
                # For requests, we find the specific request definition
                method = payload.get("method")
                # Convert method name like 'tasks/get' to schema name 'GetTaskRequest'
                schema_name = "".join(
                    part.capitalize() for part in method.replace("/", " ").split(" ")
                )
                schema_name += "Request"
                if schema_name in self.schema["definitions"]:
                    schema_to_use = self.schema["definitions"][schema_name]
                else:
                    # Fallback to generic request if specific one not found
                    schema_to_use = self.schema["definitions"]["JSONRPCRequest"]
            else:
                # For responses, we validate against the generic response schema
                schema_to_use = self.schema["definitions"]["JSONRPCResponse"]

            self.validator.check_schema(schema_to_use)
            self.validator.validate(payload, schema_to_use)

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
