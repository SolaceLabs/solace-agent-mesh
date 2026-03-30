"""Workflow configuration fixtures for integration tests.

This module contains all workflow app_info configurations.
Extracted from the main integration conftest to improve maintainability.

Note: These are extracted inline from the shared_solace_connector fixture.
They will be imported back into the main conftest and used in the app_infos list.
"""
import pytest


def get_simple_workflow_config():
    """Simple 2-node workflow for basic testing."""
    return {
        "name": "TestSimpleWorkflowApp",
        "app_module": "solace_agent_mesh.workflow.app",
        "broker": {"dev_mode": True},
        "app_config": {
            "namespace": "test_namespace",
            "name": "SimpleTestWorkflow",
            "display_name": "Simple Test Workflow",
            "artifact_scope": "namespace",
            "workflow": {
                "description": "A simple 2-node workflow for testing",
                "input_schema": {
                    "type": "object",
                    "properties": {"input_text": {"type": "string"}},
                    "required": ["input_text"]
                },
                "output_schema": {
                    "type": "object",
                    "properties": {"final_result": {"type": "string"}},
                    "required": ["final_result"]
                },
                "nodes": [
                    {
                        "id": "step_1",
                        "type": "agent",
                        "agent_name": "TestPeerAgentA",
                        "input": {"task_description": "{{workflow.input.input_text}}"}
                    },
                    {
                        "id": "step_2",
                        "type": "agent",
                        "agent_name": "TestPeerAgentB",
                        "depends_on": ["step_1"],
                        "input": {"task_description": "Process the output from step 1"}
                    }
                ],
                "output_mapping": {"final_result": "{{step_2.output}}"}
            },
            "session_service": {"type": "memory", "default_behavior": "RUN_BASED"},
            "artifact_service": {"type": "test_in_memory"},
            "agent_card_publishing": {"interval_seconds": 1},
            "agent_discovery": {"enabled": True},
            "auto_summarization": {"enabled": False, "compaction_percentage": 0.25},
        },
    }


def get_structured_workflow_config():
    """Workflow with structured input/output schemas for validation testing."""
    return {
        "name": "TestStructuredWorkflowApp",
        "app_module": "solace_agent_mesh.workflow.app",
        "broker": {"dev_mode": True},
        "app_config": {
            "namespace": "test_namespace",
            "name": "StructuredTestWorkflow",
            "display_name": "Structured Test Workflow with Validation",
            "artifact_scope": "namespace",
            "workflow": {
                "description": "A workflow with structured input/output schemas for validation testing",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "customer_name": {"type": "string"},
                        "order_id": {"type": "string"},
                        "amount": {"type": "integer"}
                    },
                    "required": ["customer_name", "order_id", "amount"]
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "customer_name": {"type": "string"},
                        "order_id": {"type": "string"},
                        "amount": {"type": "integer"},
                        "status": {"type": "string"},
                        "processed": {"type": "boolean"}
                    },
                    "required": ["customer_name", "order_id", "amount", "status", "processed"]
                },
                "nodes": [
                    {
                        "id": "validate_order",
                        "type": "agent",
                        "agent_name": "TestPeerAgentA",
                        "input": {
                            "customer_name": "{{workflow.input.customer_name}}",
                            "order_id": "{{workflow.input.order_id}}",
                            "amount": "{{workflow.input.amount}}"
                        },
                        "input_schema_override": {
                            "type": "object",
                            "properties": {
                                "customer_name": {"type": "string"},
                                "order_id": {"type": "string"},
                                "amount": {"type": "integer"}
                            },
                            "required": ["customer_name", "order_id", "amount"]
                        },
                        "output_schema_override": {
                            "type": "object",
                            "properties": {
                                "customer_name": {"type": "string"},
                                "order_id": {"type": "string"},
                                "amount": {"type": "integer"},
                                "status": {"type": "string"}
                            },
                            "required": ["customer_name", "order_id", "amount", "status"]
                        }
                    },
                    {
                        "id": "process_order",
                        "type": "agent",
                        "agent_name": "TestPeerAgentB",
                        "depends_on": ["validate_order"],
                        "input": {
                            "customer_name": "{{validate_order.output.customer_name}}",
                            "order_id": "{{validate_order.output.order_id}}",
                            "amount": "{{validate_order.output.amount}}",
                            "status": "{{validate_order.output.status}}"
                        },
                        "input_schema_override": {
                            "type": "object",
                            "properties": {
                                "customer_name": {"type": "string"},
                                "order_id": {"type": "string"},
                                "amount": {"type": "integer"},
                                "status": {"type": "string"}
                            },
                            "required": ["customer_name", "order_id", "amount", "status"]
                        },
                        "output_schema_override": {
                            "type": "object",
                            "properties": {
                                "customer_name": {"type": "string"},
                                "order_id": {"type": "string"},
                                "amount": {"type": "integer"},
                                "status": {"type": "string"},
                                "processed": {"type": "boolean"}
                            },
                            "required": ["customer_name", "order_id", "amount", "status", "processed"]
                        }
                    }
                ],
                "output_mapping": {
                    "customer_name": "{{process_order.output.customer_name}}",
                    "order_id": "{{process_order.output.order_id}}",
                    "amount": "{{process_order.output.amount}}",
                    "status": "{{process_order.output.status}}",
                    "processed": "{{process_order.output.processed}}"
                }
            },
            "session_service": {"type": "memory", "default_behavior": "RUN_BASED"},
            "artifact_service": {"type": "test_in_memory"},
            "agent_card_publishing": {"interval_seconds": 1},
            "agent_discovery": {"enabled": True},
            "auto_summarization": {"enabled": False, "compaction_percentage": 0.25},
        },
    }


def get_conditional_workflow_config():
    """Workflow with conditional branching based on status."""
    return {
        "name": "TestConditionalWorkflowApp",
        "app_module": "solace_agent_mesh.workflow.app",
        "broker": {"dev_mode": True},
        "app_config": {
            "namespace": "test_namespace",
            "name": "ConditionalTestWorkflow",
            "display_name": "Conditional Test Workflow",
            "artifact_scope": "namespace",
            "workflow": {
                "description": "A workflow with conditional branching based on status",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "input_text": {"type": "string"},
                        "should_succeed": {"type": "boolean"},
                    },
                    "required": ["input_text", "should_succeed"],
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "result": {"type": "string"},
                        "path_taken": {"type": "string"},
                    },
                },
                "nodes": [
                    {
                        "id": "check_status",
                        "type": "agent",
                        "agent_name": "TestPeerAgentA",
                        "input": {
                            "task": "Check status",
                            "should_succeed": "{{workflow.input.should_succeed}}",
                        },
                    },
                    {
                        "id": "branch",
                        "type": "switch",
                        "cases": [
                            {
                                "condition": "'{{check_status.output.status}}' == 'success'",
                                "node": "success_path",
                            },
                        ],
                        "default": "failure_path",
                        "depends_on": ["check_status"],
                    },
                    {
                        "id": "success_path",
                        "type": "agent",
                        "agent_name": "TestPeerAgentB",
                        "depends_on": ["branch"],
                        "input": {"task": "Handle success"},
                    },
                    {
                        "id": "failure_path",
                        "type": "agent",
                        "agent_name": "TestPeerAgentC",
                        "depends_on": ["branch"],
                        "input": {"task": "Handle failure"},
                    },
                ],
                "output_mapping": {
                    "result": {
                        "coalesce": [
                            "{{success_path.output.result}}",
                            "{{failure_path.output.result}}",
                        ]
                    },
                    "path_taken": {
                        "coalesce": [
                            "{{success_path.output.path}}",
                            "{{failure_path.output.path}}",
                        ]
                    },
                },
            },
            "session_service": {"type": "memory", "default_behavior": "RUN_BASED"},
            "artifact_service": {"type": "test_in_memory"},
            "agent_card_publishing": {"interval_seconds": 1},
            "agent_discovery": {"enabled": True},
            "auto_summarization": {"enabled": False, "compaction_percentage": 0.25},
        },
    }


def get_map_workflow_config():
    """Workflow that iterates over a list of items."""
    return {
        "name": "TestMapWorkflowApp",
        "app_module": "solace_agent_mesh.workflow.app",
        "broker": {"dev_mode": True},
        "app_config": {
            "namespace": "test_namespace",
            "name": "MapTestWorkflow",
            "display_name": "Map Test Workflow",
            "artifact_scope": "namespace",
            "workflow": {
                "description": "A workflow that iterates over a list of items",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["items"],
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "results": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                    },
                },
                "nodes": [
                    {
                        "id": "process_items",
                        "type": "map",
                        "node": "process_single_item",
                        "items": "{{workflow.input.items}}",
                    },
                    {
                        "id": "process_single_item",
                        "type": "agent",
                        "agent_name": "TestPeerAgentA",
                        "input": {
                            "item": "{{_map_item}}",
                            "index": "{{_map_index}}",
                        },
                    },
                ],
                "output_mapping": {
                    "results": "{{process_items.output}}",
                },
            },
            "session_service": {"type": "memory", "default_behavior": "RUN_BASED"},
            "artifact_service": {"type": "test_in_memory"},
            "agent_card_publishing": {"interval_seconds": 1},
            "agent_discovery": {"enabled": True},
            "auto_summarization": {"enabled": False, "compaction_percentage": 0.25},
        },
    }


def get_switch_workflow_config():
    """Workflow with switch (multi-way) branching."""
    return {
        "name": "TestSwitchWorkflowApp",
        "app_module": "solace_agent_mesh.workflow.app",
        "broker": {"dev_mode": True},
        "app_config": {
            "namespace": "test_namespace",
            "name": "SwitchTestWorkflow",
            "display_name": "Switch Test Workflow",
            "artifact_scope": "namespace",
            "workflow": {
                "description": "A workflow with switch (multi-way) branching",
                "input_schema": {
                    "type": "object",
                    "properties": {"action": {"type": "string"}},
                    "required": ["action"],
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "result": {"type": "string"},
                        "action_taken": {"type": "string"},
                    },
                },
                "nodes": [
                    {
                        "id": "route_action",
                        "type": "switch",
                        "cases": [
                            {
                                "condition": "'{{workflow.input.action}}' == 'create'",
                                "node": "create_handler",
                            },
                            {
                                "condition": "'{{workflow.input.action}}' == 'update'",
                                "node": "update_handler",
                            },
                            {
                                "condition": "'{{workflow.input.action}}' == 'delete'",
                                "node": "delete_handler",
                            },
                        ],
                        "default": "default_handler",
                    },
                    {
                        "id": "create_handler",
                        "type": "agent",
                        "agent_name": "TestPeerAgentA",
                        "depends_on": ["route_action"],
                        "input": {"task": "Create resource"},
                    },
                    {
                        "id": "update_handler",
                        "type": "agent",
                        "agent_name": "TestPeerAgentB",
                        "depends_on": ["route_action"],
                        "input": {"task": "Update resource"},
                    },
                    {
                        "id": "delete_handler",
                        "type": "agent",
                        "agent_name": "TestPeerAgentC",
                        "depends_on": ["route_action"],
                        "input": {"task": "Delete resource"},
                    },
                    {
                        "id": "default_handler",
                        "type": "agent",
                        "agent_name": "TestPeerAgentA",
                        "depends_on": ["route_action"],
                        "input": {"task": "Handle unknown action"},
                    },
                ],
                "output_mapping": {
                    "result": {
                        "coalesce": [
                            "{{create_handler.output.result}}",
                            "{{update_handler.output.result}}",
                            "{{delete_handler.output.result}}",
                            "{{default_handler.output.result}}",
                        ]
                    },
                    "action_taken": {
                        "coalesce": [
                            "{{create_handler.output.action}}",
                            "{{update_handler.output.action}}",
                            "{{delete_handler.output.action}}",
                            "{{default_handler.output.action}}",
                        ]
                    },
                },
            },
            "session_service": {"type": "memory", "default_behavior": "RUN_BASED"},
            "artifact_service": {"type": "test_in_memory"},
            "agent_card_publishing": {"interval_seconds": 1},
            "agent_discovery": {"enabled": True},
            "auto_summarization": {"enabled": False, "compaction_percentage": 0.25},
        },
    }


def get_loop_workflow_config():
    """Workflow with loop iteration."""
    return {
        "name": "TestLoopWorkflowApp",
        "app_module": "solace_agent_mesh.workflow.app",
        "broker": {"dev_mode": True},
        "app_config": {
            "namespace": "test_namespace",
            "name": "LoopTestWorkflow",
            "display_name": "Loop Test Workflow",
            "artifact_scope": "namespace",
            "workflow": {
                "description": "A workflow with loop iteration",
                "input_schema": {
                    "type": "object",
                    "properties": {"max_count": {"type": "integer"}},
                    "required": ["max_count"],
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "final_count": {"type": "integer"},
                        "iterations": {"type": "integer"},
                    },
                },
                "nodes": [
                    {
                        "id": "count_loop",
                        "type": "loop",
                        "node": "increment_counter",
                        "condition": "{{increment_counter.output.count}} < {{workflow.input.max_count}}",
                        "max_iterations": 10,
                    },
                    {
                        "id": "increment_counter",
                        "type": "agent",
                        "agent_name": "TestPeerAgentA",
                        "input": {
                            "task": "Increment counter",
                            "current_iteration": "{{_loop_iteration}}",
                        },
                    },
                ],
                "output_mapping": {
                    "final_count": "{{increment_counter.output.count}}",
                    "iterations": "{{count_loop.output.iterations_completed}}",
                },
            },
            "session_service": {"type": "memory", "default_behavior": "RUN_BASED"},
            "artifact_service": {"type": "test_in_memory"},
            "agent_card_publishing": {"interval_seconds": 1},
            "agent_discovery": {"enabled": True},
            "auto_summarization": {"enabled": False, "compaction_percentage": 0.25},
        },
    }


def get_instruction_workflow_config():
    """Workflow to test the instruction field on agent nodes."""
    return {
        "name": "TestInstructionWorkflowApp",
        "app_module": "solace_agent_mesh.workflow.app",
        "broker": {"dev_mode": True},
        "app_config": {
            "namespace": "test_namespace",
            "name": "InstructionTestWorkflow",
            "display_name": "Instruction Test Workflow",
            "artifact_scope": "namespace",
            "workflow": {
                "description": "A workflow to test the instruction field on agent nodes",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "input_text": {"type": "string"},
                        "context": {"type": "string"},
                    },
                    "required": ["input_text", "context"],
                },
                "output_schema": {
                    "type": "object",
                    "properties": {"result": {"type": "string"}},
                },
                "nodes": [
                    {
                        "id": "process_with_instruction",
                        "type": "agent",
                        "agent_name": "TestPeerAgentA",
                        "instruction": "STATIC_MARKER_123 - Context from workflow input: {{workflow.input.context}}",
                        "input": {"task": "{{workflow.input.input_text}}"},
                    },
                ],
                "output_mapping": {"result": "{{process_with_instruction.output.result}}"},
            },
            "session_service": {"type": "memory", "default_behavior": "RUN_BASED"},
            "artifact_service": {"type": "test_in_memory"},
            "agent_card_publishing": {"interval_seconds": 1},
            "agent_discovery": {"enabled": True},
            "auto_summarization": {"enabled": False, "compaction_percentage": 0.25},
        },
    }


def get_subworkflow_invoke_config():
    """Workflow that invokes another workflow as a sub-workflow."""
    return {
        "name": "TestSubWorkflowInvokeApp",
        "app_module": "solace_agent_mesh.workflow.app",
        "broker": {"dev_mode": True},
        "app_config": {
            "namespace": "test_namespace",
            "name": "SubWorkflowInvokeTestWorkflow",
            "display_name": "Sub-Workflow Invoke Test Workflow",
            "artifact_scope": "namespace",
            "workflow": {
                "description": "A workflow that invokes another workflow as a sub-workflow",
                "input_schema": {
                    "type": "object",
                    "properties": {"input_text": {"type": "string"}},
                    "required": ["input_text"],
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "final_result": {"type": "string"},
                        "from_parent": {"type": "string"},
                    },
                },
                "nodes": [
                    {
                        "id": "prepare_data",
                        "type": "agent",
                        "agent_name": "TestPeerAgentA",
                        "input": {"task": "Prepare data for sub-workflow: {{workflow.input.input_text}}"},
                    },
                    {
                        "id": "invoke_sub_workflow",
                        "type": "workflow",
                        "workflow_name": "SimpleTestWorkflow",
                        "depends_on": ["prepare_data"],
                        "input": {"input_text": "{{prepare_data.output.processed_data}}"},
                    },
                    {
                        "id": "finalize",
                        "type": "agent",
                        "agent_name": "TestPeerAgentB",
                        "depends_on": ["invoke_sub_workflow"],
                        "input": {"sub_workflow_result": "{{invoke_sub_workflow.output.final_result}}"},
                    },
                ],
                "output_mapping": {
                    "final_result": "{{finalize.output.result}}",
                    "from_parent": "{{prepare_data.output.parent_marker}}",
                },
            },
            "session_service": {"type": "memory", "default_behavior": "RUN_BASED"},
            "artifact_service": {"type": "test_in_memory"},
            "agent_card_publishing": {"interval_seconds": 1},
            "agent_discovery": {"enabled": True},
            "auto_summarization": {"enabled": False, "compaction_percentage": 0.25},
        },
    }


def get_recursive_workflow_config():
    """Workflow that tries to invoke itself (should fail)."""
    return {
        "name": "TestRecursiveWorkflowApp",
        "app_module": "solace_agent_mesh.workflow.app",
        "broker": {"dev_mode": True},
        "app_config": {
            "namespace": "test_namespace",
            "name": "RecursiveTestWorkflow",
            "display_name": "Recursive Test Workflow (for testing recursion prevention)",
            "artifact_scope": "namespace",
            "workflow": {
                "description": "A workflow that tries to invoke itself (should fail)",
                "nodes": [
                    {
                        "id": "prepare",
                        "type": "agent",
                        "agent_name": "TestPeerAgentA",
                    },
                    {
                        "id": "recursive_call",
                        "type": "workflow",
                        "workflow_name": "RecursiveTestWorkflow",
                        "depends_on": ["prepare"],
                    },
                ],
                "output_mapping": {"result": "{{recursive_call.output}}"},
            },
            "session_service": {"type": "memory", "default_behavior": "RUN_BASED"},
            "artifact_service": {"type": "test_in_memory"},
            "agent_card_publishing": {"interval_seconds": 1},
            "agent_discovery": {"enabled": True},
            "auto_summarization": {"enabled": False, "compaction_percentage": 0.25},
        },
    }


def get_a2a_proxy_config(test_a2a_agent_server_harness):
    """A2A proxy configuration for proxying external A2A agents."""
    return {
        "name": "TestA2AProxyApp",
        "app_module": "solace_agent_mesh.agent.proxies.a2a.app",
        "broker": {"dev_mode": True},
        "app_config": {
            "namespace": "test_namespace",
            "proxied_agents": [
                {
                    "name": "TestAgent_Proxied",
                    "url": test_a2a_agent_server_harness.url,
                    "request_timeout_seconds": 3,
                },
                {
                    "name": "TestAgent_Proxied_NoConvert",
                    "url": test_a2a_agent_server_harness.url,
                    "request_timeout_seconds": 3,
                    "convert_progress_updates": False,
                }
            ],
            "artifact_service": {"type": "test_in_memory"},
            "discovery_interval_seconds": 1,
        },
    }

