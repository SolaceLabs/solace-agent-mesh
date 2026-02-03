"""
Unit tests for WorkflowAppConfig class.

Tests that WorkflowAppConfig validates correctly and the 'name' field
is properly used as the primary workflow identifier.
"""

import pytest
from pydantic import ValidationError

from solace_agent_mesh.workflow.app import (
    WorkflowAppConfig,
    WorkflowDefinition,
    AgentNode,
)


class TestWorkflowAppConfigName:
    """Tests for WorkflowAppConfig 'name' field."""

    def test_workflow_app_config_with_name_field(self):
        """WorkflowAppConfig accepts 'name' field as the primary identifier."""
        config = WorkflowAppConfig(
            namespace="test_namespace",
            name="TestWorkflow",
            workflow=WorkflowDefinition(
                description="Test workflow",
                nodes=[
                    AgentNode(id="step1", type="agent", agent_name="Agent1"),
                ],
                output_mapping={"result": "{{step1.output}}"},
            ),
        )
        assert config.name == "TestWorkflow"
        assert config.agent_name == "TestWorkflow"

    def test_name_field_is_required(self):
        """WorkflowAppConfig requires 'name' field."""
        with pytest.raises(ValidationError) as excinfo:
            WorkflowAppConfig(
                namespace="test_namespace",
                workflow=WorkflowDefinition(
                    description="Test workflow",
                    nodes=[
                        AgentNode(id="step1", type="agent", agent_name="Agent1"),
                    ],
                    output_mapping={"result": "{{step1.output}}"},
                ),
            )
        assert "name" in str(excinfo.value).lower()

    def test_agent_name_auto_populated_from_name(self):
        """agent_name is automatically populated from name via validator."""
        config = WorkflowAppConfig(
            namespace="test_namespace",
            name="MyWorkflow",
            workflow=WorkflowDefinition(
                description="Test workflow",
                nodes=[
                    AgentNode(id="step1", type="agent", agent_name="Agent1"),
                ],
                output_mapping={"result": "{{step1.output}}"},
            ),
        )
        # Both should be equal after validator runs
        assert config.name == "MyWorkflow"
        assert config.agent_name == "MyWorkflow"


class TestWorkflowAppConfigValidation:
    """Tests for WorkflowAppConfig validation of workflow definitions."""

    def test_workflow_definition_validation(self):
        """Workflow definition is validated during config creation."""
        # Invalid workflow should fail validation
        with pytest.raises(ValidationError):
            WorkflowAppConfig(
                namespace="test_namespace",
                name="TestWorkflow",
                workflow=WorkflowDefinition(
                    description="Test workflow",
                    nodes=[
                        AgentNode(id="step1", type="agent", agent_name="Agent1"),
                        AgentNode(
                            id="step2",
                            type="agent",
                            agent_name="Agent2",
                            depends_on=["nonexistent"],  # Invalid dependency
                        ),
                    ],
                    output_mapping={"result": "{{step2.output}}"},
                ),
            )

    def test_workflow_config_with_custom_timeouts(self):
        """WorkflowAppConfig accepts custom timeout values."""
        config = WorkflowAppConfig(
            namespace="test_namespace",
            name="TimeoutWorkflow",
            workflow=WorkflowDefinition(
                description="Complete workflow",
                nodes=[
                    AgentNode(id="step1", type="agent", agent_name="Agent1"),
                ],
                output_mapping={"result": "{{step1.output}}"},
            ),
            max_workflow_execution_time_seconds=3600,
            default_node_timeout_seconds=600,
            node_cancellation_timeout_seconds=60,
            default_max_map_items=200,
        )
        assert config.max_workflow_execution_time_seconds == 3600
        assert config.default_node_timeout_seconds == 600
        assert config.node_cancellation_timeout_seconds == 60
        assert config.default_max_map_items == 200

    def test_workflow_config_with_default_timeouts(self):
        """WorkflowAppConfig uses sensible timeout defaults."""
        config = WorkflowAppConfig(
            namespace="test_namespace",
            name="DefaultTimeoutWorkflow",
            workflow=WorkflowDefinition(
                description="Test workflow",
                nodes=[
                    AgentNode(id="step1", type="agent", agent_name="Agent1"),
                ],
                output_mapping={"result": "{{step1.output}}"},
            ),
        )
        # Check defaults
        assert config.max_workflow_execution_time_seconds == 1800  # 30 minutes
        assert config.default_node_timeout_seconds == 300  # 5 minutes
        assert config.node_cancellation_timeout_seconds == 30
        assert config.default_max_map_items == 100


class TestWorkflowAppConfigFromDict:
    """Tests for creating WorkflowAppConfig from dictionaries."""

    def test_model_validate_with_dict(self):
        """WorkflowAppConfig can be created from dict via model_validate."""
        config_dict = {
            "namespace": "test_namespace",
            "name": "DictCreatedWorkflow",
            "workflow": {
                "description": "Test workflow",
                "nodes": [
                    {"id": "step1", "type": "agent", "agent_name": "Agent1"},
                ],
                "output_mapping": {"result": "{{step1.output}}"},
            },
        }
        config = WorkflowAppConfig.model_validate(config_dict)
        assert config.name == "DictCreatedWorkflow"
        assert config.agent_name == "DictCreatedWorkflow"
        assert config.namespace == "test_namespace"

    def test_model_validate_requires_name(self):
        """model_validate also requires 'name' field."""
        config_dict = {
            "namespace": "test_namespace",
            "workflow": {
                "description": "Test workflow",
                "nodes": [
                    {"id": "step1", "type": "agent", "agent_name": "Agent1"},
                ],
                "output_mapping": {"result": "{{step1.output}}"},
            },
        }
        with pytest.raises(ValidationError) as excinfo:
            WorkflowAppConfig.model_validate(config_dict)
        assert "name" in str(excinfo.value).lower()
