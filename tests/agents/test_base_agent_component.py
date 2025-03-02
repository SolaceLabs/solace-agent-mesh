"""Unit tests for the BaseAgentComponent class."""

import unittest
from unittest.mock import MagicMock, patch, call
import json
import time
import os

from src.agents.base_agent_component import BaseAgentComponent
from src.common.action_response import ActionResponse, ErrorInfo
from src.common.action import Action
from src.common.action_list import ActionList


class TestAction(Action):
    """Test action for unit tests."""
    
    def __init__(self, **kwargs):
        attributes = {
            "name": "test_action",
            "prompt_directive": "Test action for unit tests",
            "long_description": "This is a test action for unit tests",
            "params": [
                {
                    "name": "param1",
                    "desc": "Test parameter 1",
                    "required": True,
                    "type": "string"
                },
                {
                    "name": "param2",
                    "desc": "Test parameter 2",
                    "required": False,
                    "type": "integer"
                }
            ],
            "examples": [
                {
                    "param1": "test",
                    "param2": 42
                }
            ]
        }
        super().__init__(attributes, **kwargs)
    
    def invoke(self, params, meta=None):
        """Test action implementation."""
        if params.get("param1") == "error":
            raise ValueError("Test error")
        
        return ActionResponse(
            message=f"Test action executed with params: {params}",
            files=["test_file.txt"] if params.get("param1") == "with_file" else None
        )


class DummyTraceContext:
    """Dummy trace context for testing."""
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
    
    def progress(self, data=None, stage="progress"):
        pass


class TestBaseAgentComponent(unittest.TestCase):
    """Test cases for the BaseAgentComponent class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a concrete subclass of BaseAgentComponent for testing
        class TestAgent(BaseAgentComponent):
            actions = [TestAction]
            info = {
                "agent_name": "test_agent",
                "description": "Test agent for unit tests",
                "always_open": True,
                "custom_field": "custom_value"
            }
            
            def create_trace_context(self, operation, data=None, trace_level="INFO"):
                return DummyTraceContext()
        
        # Mock the connector and command control service
        self.mock_connector = MagicMock()
        self.mock_command_control = MagicMock()
        self.mock_connector.get_command_control_service.return_value = self.mock_command_control
        
        # Create an instance of the test agent
        self.agent = TestAgent(
            module_info={},
            connector=self.mock_connector,
            config={
                "component_name": "test_agent_component",
                "component_config": {
                    "registration_interval": 60
                }
            },
            flow_name="test_flow",
            component_index=0,
            index=0
        )
        
        # Mock the broker adapter for tracing
        self.mock_broker_adapter = MagicMock()
        if hasattr(self.agent, "tracing_system") and self.agent.tracing_system:
            self.agent.tracing_system.broker_adapter = self.mock_broker_adapter
        
        # Set up environment variable for testing
        os.environ["SOLACE_AGENT_MESH_NAMESPACE"] = "test/"
    
    def tearDown(self):
        """Clean up after tests."""
        if "SOLACE_AGENT_MESH_NAMESPACE" in os.environ:
            del os.environ["SOLACE_AGENT_MESH_NAMESPACE"]
    
    def test_initialization(self):
        """Test that the agent initializes correctly."""
        self.assertEqual(self.agent.info["agent_name"], "test_agent")
        self.assertEqual(self.agent.info["description"], "Test agent for unit tests")
        self.assertTrue(self.agent.info["always_open"])
        self.assertEqual(self.agent.info["custom_field"], "custom_value")
        self.assertEqual(self.agent.registration_interval, 60)
        
        # Check that action stats are initialized
        self.assertIn("test_action", self.agent.action_stats)
        self.assertEqual(self.agent.action_stats["test_action"]["total_invocations"], 0)
        
        # Check that the agent registered with command control
        self.mock_command_control.register_entity.assert_called_once()
    
    def test_get_agent_summary(self):
        """Test getting the agent summary."""
        summary = self.agent.get_agent_summary()
        self.assertEqual(summary["agent_name"], "test_agent")
        self.assertEqual(summary["description"], "Test agent for unit tests")
        self.assertTrue(summary["always_open"])
        self.assertIn("actions", summary)
    
    @patch("src.services.file_service.FileService")
    @patch("src.services.middleware_service.middleware_service.MiddlewareService")
    def test_invoke_successful(self, mock_middleware_service_class, mock_file_service_class):
        """Test successful action invocation."""
        # Set up mocks
        mock_file_service = MagicMock()
        mock_file_service_class.return_value = mock_file_service
        mock_file_service.resolve_all_resolvable_urls.return_value = {"param1": "test", "param2": 42}
        
        mock_middleware_service = MagicMock()
        mock_middleware_service_class.return_value = mock_middleware_service
        mock_middleware_service.get.return_value = lambda user_props, action: True
        
        # Create a message with session ID
        mock_message = MagicMock()
        mock_message.get_user_properties.return_value = {"session_id": "test_session"}
        
        # Invoke the action
        data = {
            "action_name": "test_action",
            "action_params": {"param1": "test", "param2": 42},
            "action_list_id": "test_list",
            "action_idx": 0
        }
        
        result = self.agent.invoke(mock_message, data)
        
        # Check the result
        self.assertIsInstance(result, dict)
        self.assertIn("payload", result)
        self.assertIn("topic", result)
        self.assertEqual(result["topic"], "test/solace-agent-mesh/v1/actionResponse/agent/test_agent/test_action")
        
        # Check that stats were updated
        self.assertEqual(self.agent.action_stats["test_action"]["total_invocations"], 1)
        self.assertEqual(self.agent.action_stats["test_action"]["successful_invocations"], 1)
        self.assertEqual(self.agent.action_stats["test_action"]["failed_invocations"], 0)
        self.assertIsNotNone(self.agent.action_stats["test_action"]["last_execution_time_ms"])
    
    @patch("src.services.file_service.FileService")
    @patch("src.services.middleware_service.middleware_service.MiddlewareService")
    def test_invoke_with_file(self, mock_middleware_service_class, mock_file_service_class):
        """Test action invocation that returns a file."""
        # Set up mocks
        mock_file_service = MagicMock()
        mock_file_service_class.return_value = mock_file_service
        mock_file_service.resolve_all_resolvable_urls.return_value = {"param1": "with_file", "param2": 42}
        
        mock_middleware_service = MagicMock()
        mock_middleware_service_class.return_value = mock_middleware_service
        mock_middleware_service.get.return_value = lambda user_props, action: True
        
        # Create a message with session ID
        mock_message = MagicMock()
        mock_message.get_user_properties.return_value = {"session_id": "test_session"}
        
        # Invoke the action
        data = {
            "action_name": "test_action",
            "action_params": {"param1": "with_file", "param2": 42},
            "action_list_id": "test_list",
            "action_idx": 0
        }
        
        result = self.agent.invoke(mock_message, data)
        
        # Check the result
        self.assertIsInstance(result, dict)
        self.assertIn("payload", result)
        self.assertIn("files", result["payload"])
        self.assertEqual(result["payload"]["files"], ["test_file.txt"])
    
    @patch("src.services.file_service.FileService")
    @patch("src.services.middleware_service.middleware_service.MiddlewareService")
    def test_invoke_error(self, mock_middleware_service_class, mock_file_service_class):
        """Test action invocation that raises an error."""
        # Set up mocks
        mock_file_service = MagicMock()
        mock_file_service_class.return_value = mock_file_service
        mock_file_service.resolve_all_resolvable_urls.return_value = {"param1": "error", "param2": 42}
        
        mock_middleware_service = MagicMock()
        mock_middleware_service_class.return_value = mock_middleware_service
        mock_middleware_service.get.return_value = lambda user_props, action: True
        
        # Create a message with session ID
        mock_message = MagicMock()
        mock_message.get_user_properties.return_value = {"session_id": "test_session"}
        
        # Invoke the action
        data = {
            "action_name": "test_action",
            "action_params": {"param1": "error", "param2": 42},
            "action_list_id": "test_list",
            "action_idx": 0
        }
        
        result = self.agent.invoke(mock_message, data)
        
        # Check the result
        self.assertIsInstance(result, dict)
        self.assertIn("payload", result)
        self.assertIn("message", result["payload"])
        self.assertIn("error_info", result["payload"])
        self.assertIn("Test error", result["payload"]["message"])
        
        # Check that stats were updated
        self.assertEqual(self.agent.action_stats["test_action"]["total_invocations"], 1)
        self.assertEqual(self.agent.action_stats["test_action"]["successful_invocations"], 0)
        self.assertEqual(self.agent.action_stats["test_action"]["failed_invocations"], 1)
        self.assertIsNotNone(self.agent.action_stats["test_action"]["last_error"])
    
    @patch("src.services.file_service.FileService")
    @patch("src.services.middleware_service.middleware_service.MiddlewareService")
    def test_invoke_unauthorized(self, mock_middleware_service_class, mock_file_service_class):
        """Test action invocation that is unauthorized."""
        # Set up mocks
        mock_file_service = MagicMock()
        mock_file_service_class.return_value = mock_file_service
        mock_file_service.resolve_all_resolvable_urls.return_value = {"param1": "test", "param2": 42}
        
        mock_middleware_service = MagicMock()
        mock_middleware_service_class.return_value = mock_middleware_service
        mock_middleware_service.get.return_value = lambda user_props, action: False
        
        # Create a message with session ID
        mock_message = MagicMock()
        mock_message.get_user_properties.return_value = {"session_id": "test_session"}
        
        # Invoke the action
        data = {
            "action_name": "test_action",
            "action_params": {"param1": "test", "param2": 42},
            "action_list_id": "test_list",
            "action_idx": 0
        }
        
        result = self.agent.invoke(mock_message, data)
        
        # Check the result
        self.assertIsInstance(result, dict)
        self.assertIn("payload", result)
        self.assertIn("message", result["payload"])
        self.assertIn("Unauthorized", result["payload"]["message"])
        
        # Check that stats were updated
        self.assertEqual(self.agent.action_stats["test_action"]["total_invocations"], 1)
        self.assertEqual(self.agent.action_stats["test_action"]["successful_invocations"], 0)
        self.assertEqual(self.agent.action_stats["test_action"]["failed_invocations"], 1)
        self.assertEqual(self.agent.action_stats["test_action"]["last_error"], "Unauthorized access")
    
    def test_handle_timer_event(self):
        """Test handling timer events for registration."""
        # Mock the send_message method
        self.agent.send_message = MagicMock()
        self.agent.add_timer = MagicMock()
        
        # Call the timer event handler
        self.agent.handle_timer_event(None)
        
        # Check that a message was sent
        self.agent.send_message.assert_called_once()
        sent_message = self.agent.send_message.call_args[0][0]
        self.assertEqual(sent_message.get_topic(), "test/solace-agent-mesh/v1/register/agent/test_agent")
        
        # Check that the timer was rescheduled
        self.agent.add_timer.assert_called_once_with(60000, "agent_registration")
    
    def test_update_action_stats(self):
        """Test updating action statistics."""
        # Test successful action
        start_time = time.time() - 0.1  # 100ms ago
        self.agent._update_action_stats("test_action", True, start_time)
        
        stats = self.agent.action_stats["test_action"]
        self.assertEqual(stats["total_invocations"], 1)
        self.assertEqual(stats["successful_invocations"], 1)
        self.assertEqual(stats["failed_invocations"], 0)
        self.assertGreaterEqual(stats["last_execution_time_ms"], 100)  # At least 100ms
        self.assertIsNone(stats["last_error"])
        
        # Test failed action
        start_time = time.time() - 0.2  # 200ms ago
        self.agent._update_action_stats("test_action", False, start_time, "Test error")
        
        stats = self.agent.action_stats["test_action"]
        self.assertEqual(stats["total_invocations"], 2)
        self.assertEqual(stats["successful_invocations"], 1)
        self.assertEqual(stats["failed_invocations"], 1)
        self.assertGreaterEqual(stats["last_execution_time_ms"], 200)  # At least 200ms
        self.assertEqual(stats["last_error"], "Test error")
        
        # Test non-existent action
        start_time = time.time()
        self.agent._update_action_stats("non_existent_action", True, start_time)
        
        self.assertIn("non_existent_action", self.agent.action_stats)
        stats = self.agent.action_stats["non_existent_action"]
        self.assertEqual(stats["total_invocations"], 1)
    
    def test_get_metrics(self):
        """Test getting metrics."""
        # Add some stats
        self.agent.action_stats["test_action"] = {
            "total_invocations": 10,
            "successful_invocations": 7,
            "failed_invocations": 3,
            "average_execution_time_ms": 150,
            "last_execution_time_ms": 200,
            "last_error": "Test error",
            "last_invoked_at": time.time()
        }
        
        metrics = self.agent.get_metrics()
        
        self.assertEqual(metrics["total_action_invocations"], 10)
        self.assertEqual(metrics["successful_action_invocations"], 7)
        self.assertEqual(metrics["failed_action_invocations"], 3)
        self.assertEqual(metrics["average_action_execution_time"], 150)
        self.assertEqual(metrics["action_count"], 1)
    
    def test_command_control_endpoints(self):
        """Test getting command control endpoints."""
        endpoints = self.agent._get_command_control_endpoints()
        
        # Check that we have the expected endpoints
        endpoint_paths = [endpoint["path"] for endpoint in endpoints]
        self.assertIn("/agents/test_agent", endpoint_paths)
        self.assertIn("/agents/test_agent/actions", endpoint_paths)
        self.assertIn("/agents/test_agent/stats", endpoint_paths)
        self.assertIn("/agents/test_agent/config", endpoint_paths)
        self.assertIn("/agents/test_agent/actions/test_action", endpoint_paths)
        self.assertIn("/agents/test_agent/actions/test_action/stats", endpoint_paths)
    
    def test_command_control_configuration(self):
        """Test getting command control configuration."""
        config = self.agent._get_command_control_configuration()
        
        # Check the structure
        self.assertIn("current_config", config)
        self.assertIn("mutable_paths", config)
        self.assertIn("config_schema", config)
        
        # Check the current config
        current_config = config["current_config"]
        self.assertIn("agent", current_config)
        self.assertIn("component", current_config)
        
        # Check the agent config
        agent_config = current_config["agent"]
        self.assertEqual(agent_config["agent_name"], "test_agent")
        self.assertEqual(agent_config["description"], "Test agent for unit tests")
        self.assertTrue(agent_config["always_open"])
        self.assertEqual(agent_config["custom_field"], "custom_value")
        
        # Check mutable paths
        mutable_paths = config["mutable_paths"]
        self.assertIn("agent.description", mutable_paths)
        self.assertIn("agent.always_open", mutable_paths)
        self.assertIn("agent.custom_field", mutable_paths)
        
        # Check schema
        schema = config["config_schema"]
        self.assertIn("properties", schema)
        self.assertIn("agent", schema["properties"])
        self.assertIn("properties", schema["properties"]["agent"])
        self.assertIn("custom_field", schema["properties"]["agent"]["properties"])
    
    def test_handle_get_agent_info(self):
        """Test handling GET requests for agent info."""
        result = self.agent._handle_get_agent_info()
        
        self.assertEqual(result["agent_name"], "test_agent")
        self.assertEqual(result["description"], "Test agent for unit tests")
        self.assertTrue(result["always_open"])
        self.assertIn("actions", result)
    
    def test_handle_update_agent_config(self):
        """Test handling PUT requests to update agent config."""
        # Test with valid data
        result = self.agent._handle_update_agent_config(body={
            "description": "Updated description",
            "always_open": False
        })
        
        self.assertTrue(result["success"])
        self.assertEqual(self.agent.info["description"], "Updated description")
        self.assertFalse(self.agent.info["always_open"])
        
        # Test with empty data
        result = self.agent._handle_update_agent_config(body={})
        
        self.assertFalse(result["success"])
        
        # Test with None data
        result = self.agent._handle_update_agent_config(body=None)
        
        self.assertFalse(result["success"])
    
    def test_handle_patch_agent_config(self):
        """Test handling PATCH requests to update specific agent config fields."""
        # Test with valid data
        result = self.agent._handle_patch_agent_config(body={
            "description": "Patched description",
            "custom_field": "patched_value"
        })
        
        self.assertTrue(result["success"])
        self.assertEqual(self.agent.info["description"], "Patched description")
        self.assertEqual(self.agent.info["custom_field"], "patched_value")
        self.assertEqual(len(result["updated_fields"]), 2)
        
        # Test with invalid field
        result = self.agent._handle_patch_agent_config(body={
            "nonexistent_field": "value"
        })
        
        self.assertFalse(result["success"])
        self.assertEqual(len(result["updated_fields"]), 0)
        
        # Test with empty data
        result = self.agent._handle_patch_agent_config(body={})
        
        self.assertFalse(result["success"])
        self.assertEqual(len(result["updated_fields"]), 0)
        
        # Test with None data
        result = self.agent._handle_patch_agent_config(body=None)
        
        self.assertFalse(result["success"])
        self.assertEqual(len(result["updated_fields"]), 0)
    
    def test_handle_get_agent_config(self):
        """Test handling GET requests for agent configuration."""
        result = self.agent._handle_get_agent_config()
        
        self.assertIn("agent", result)
        self.assertIn("component", result)
        self.assertEqual(result["agent"]["agent_name"], "test_agent")
        self.assertEqual(result["agent"]["custom_field"], "custom_value")
    
    def test_handle_update_full_agent_config(self):
        """Test handling PUT requests to update full agent configuration."""
        # Test with valid data
        result = self.agent._handle_update_full_agent_config(body={
            "agent": {
                "description": "Fully updated description",
                "always_open": False,
                "custom_field": "fully_updated_value"
            },
            "component": {
                "registration_interval": 120
            }
        })
        
        self.assertTrue(result["success"])
        self.assertEqual(self.agent.info["description"], "Fully updated description")
        self.assertFalse(self.agent.info["always_open"])
        self.assertEqual(self.agent.info["custom_field"], "fully_updated_value")
        self.assertEqual(self.agent.component_config["registration_interval"], 120)
        
        # Test with empty data
        result = self.agent._handle_update_full_agent_config(body={})
        
        self.assertFalse(result["success"])
        
        # Test with None data
        result = self.agent._handle_update_full_agent_config(body=None)
        
        self.assertFalse(result["success"])
    
    def test_handle_get_agent_actions(self):
        """Test handling GET requests for agent actions."""
        result = self.agent._handle_get_agent_actions()
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "test_action")
        self.assertEqual(result[0]["description"], "This is a test action for unit tests")
    
    def test_handle_get_action_info(self):
        """Test handling GET requests for action information."""
        # Test with valid action
        result = self.agent._handle_get_action_info(action_name="test_action")
        
        self.assertEqual(result["name"], "test_action")
        self.assertEqual(result["description"], "This is a test action for unit tests")
        self.assertIn("params", result)
        self.assertIn("examples", result)
        
        # Test with invalid action
        result = self.agent._handle_get_action_info(action_name="nonexistent_action")
        
        self.assertIn("error", result)
    
    def test_handle_get_action_stats(self):
        """Test handling GET requests for action statistics."""
        # Add some stats
        self.agent.action_stats["test_action"] = {
            "total_invocations": 5,
            "successful_invocations": 3,
            "failed_invocations": 2,
            "average_execution_time_ms": 100,
            "last_execution_time_ms": 150,
            "last_error": "Test error",
            "last_invoked_at": time.time()
        }
        
        # Test getting all stats
        result = self.agent._handle_get_action_stats()
        
        self.assertIn("test_action", result)
        self.assertEqual(result["test_action"]["total_invocations"], 5)
        
        # Test getting stats for specific action
        result = self.agent._handle_get_action_stats(query_params={"action_name": "test_action"})
        
        self.assertIn("test_action", result)
        self.assertEqual(result["test_action"]["total_invocations"], 5)
        
        # Test getting stats for nonexistent action
        result = self.agent._handle_get_action_stats(query_params={"action_name": "nonexistent_action"})
        
        self.assertIn("error", result)
    
    def test_handle_get_action_stats_by_name(self):
        """Test handling GET requests for statistics for a specific action."""
        # Add some stats
        self.agent.action_stats["test_action"] = {
            "total_invocations": 5,
            "successful_invocations": 3,
            "failed_invocations": 2,
            "average_execution_time_ms": 100,
            "last_execution_time_ms": 150,
            "last_error": "Test error",
            "last_invoked_at": time.time()
        }
        
        # Test with valid action
        result = self.agent._handle_get_action_stats_by_name(action_name="test_action")
        
        self.assertEqual(result["total_invocations"], 5)
        self.assertEqual(result["successful_invocations"], 3)
        self.assertEqual(result["failed_invocations"], 2)
        
        # Test with invalid action
        result = self.agent._handle_get_action_stats_by_name(action_name="nonexistent_action")
        
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
