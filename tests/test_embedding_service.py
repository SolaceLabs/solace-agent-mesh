import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from cli.commands.init.ai_provider_step import ai_provider_step
from cli.commands.init.create_config_file_step import create_config_file_step
from cli.commands.build import build_solace_agent_mesh


class TestEmbeddingService(unittest.TestCase):
    def setUp(self):
        # Create a temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Clean up the temporary file and directory
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)

    def test_ai_provider_step_embedding_enabled(self):
        """Test that when embedding service is enabled, the AI provider step correctly asks for embedding configuration"""
        options = {}
        default_options = {
            # LLM options required by ai_provider_step
            "llm_endpoint_url": "https://api.example.com/llm",
            "llm_api_key": "test-llm-key",
            "llm_model_name": "test-llm-model",
            # Embedding options
            "embedding_service_enabled": True,
            "embedding_endpoint_url": "https://api.example.com",
            "embedding_api_key": "test-key",
            "embedding_model_name": "test-model",
        }
        
        # Mock the ask_if_not_provided function
        with patch('cli.commands.init.ai_provider_step.ask_if_not_provided') as mock_ask:
            # Configure the mock to set values in the options dictionary
            def side_effect(options_dict, key, prompt, default, none_interactive, hide_input=False):
                options_dict[key] = default
                return default
            
            mock_ask.side_effect = side_effect
            
            # Call the function
            ai_provider_step(options, default_options, True, lambda x: None)
            
            # Check that the embedding service is enabled
            self.assertTrue(options["embedding_service_enabled"])
            
            # Check that the embedding configuration is set
            self.assertEqual(options["embedding_endpoint_url"], "https://api.example.com")
            self.assertEqual(options["embedding_api_key"], "test-key")
            self.assertEqual(options["embedding_model_name"], "test-model")

    def test_ai_provider_step_embedding_disabled(self):
        """Test that when embedding service is disabled, the AI provider step does not ask for embedding configuration"""
        options = {}
        default_options = {
            # LLM options required by ai_provider_step
            "llm_endpoint_url": "https://api.example.com/llm",
            "llm_api_key": "test-llm-key",
            "llm_model_name": "test-llm-model",
            # Embedding options
            "embedding_service_enabled": False,
            "embedding_endpoint_url": "https://api.example.com",
            "embedding_api_key": "test-key",
            "embedding_model_name": "test-model",
        }
        
        # Mock the ask_if_not_provided function
        with patch('cli.commands.init.ai_provider_step.ask_if_not_provided') as mock_ask:
            # Configure the mock to set values in the options dictionary
            def side_effect(options_dict, key, prompt, default, none_interactive, hide_input=False):
                options_dict[key] = default
                return default
            
            mock_ask.side_effect = side_effect
            
            # Call the function
            ai_provider_step(options, default_options, True, lambda x: None)
            
            # Check that the embedding service is disabled
            self.assertFalse(options["embedding_service_enabled"])
            
            # Check that the embedding configuration is empty
            self.assertEqual(options["embedding_endpoint_url"], "")
            self.assertEqual(options["embedding_api_key"], "")
            self.assertEqual(options["embedding_model_name"], "")

    def test_create_config_file_step_embedding_enabled(self):
        """Test that when embedding service is enabled, the create_config_file_step correctly sets the embedding service configuration"""
        options = {
            "embedding_service_enabled": True,
            "config_dir": "configs",
            "module_dir": "modules",
            "env_file": ".env",
            "build_dir": "build",
        }
        default_options = {}
        
        # Mock the Config class
        with patch('cli.commands.init.create_config_file_step.Config') as mock_config:
            # Mock the get_default_config method to return a config with a services section
            mock_config.get_default_config.return_value = {
                "solace_agent_mesh": {
                    "built_in": {
                        "agents": [],
                        "services": [
                            {
                                "name": "embedding",
                                "enabled": False
                            }
                        ]
                    },
                    "build": {}
                }
            }
            
            # Mock the write_config method
            mock_config.write_config = MagicMock()
            
            # Mock the click.get_current_context method
            with patch('cli.commands.init.create_config_file_step.click.get_current_context') as mock_context:
                mock_context.return_value = MagicMock()
                mock_context.return_value.obj = {'solace_agent_mesh': {}}
                
                # Call the function
                create_config_file_step(options, default_options, True, lambda x: None)
                
                # Get the config that was passed to write_config
                config = mock_config.write_config.call_args[0][0]
                
                # Check that the embedding service is enabled in the config
                services = config["solace_agent_mesh"]["built_in"]["services"]
                embedding_service = next((s for s in services if s["name"] == "embedding"), None)
                self.assertIsNotNone(embedding_service)
                self.assertTrue(embedding_service["enabled"])

    def test_create_config_file_step_embedding_disabled(self):
        """Test that when embedding service is disabled, the create_config_file_step correctly sets the embedding service configuration"""
        options = {
            "embedding_service_enabled": False,
            "config_dir": "configs",
            "module_dir": "modules",
            "env_file": ".env",
            "build_dir": "build",
        }
        default_options = {}
        
        # Mock the Config class
        with patch('cli.commands.init.create_config_file_step.Config') as mock_config:
            # Mock the get_default_config method to return a config with a services section
            mock_config.get_default_config.return_value = {
                "solace_agent_mesh": {
                    "built_in": {
                        "agents": [],
                        "services": [
                            {
                                "name": "embedding",
                                "enabled": True
                            }
                        ]
                    },
                    "build": {}
                }
            }
            
            # Mock the write_config method
            mock_config.write_config = MagicMock()
            
            # Mock the click.get_current_context method
            with patch('cli.commands.init.create_config_file_step.click.get_current_context') as mock_context:
                mock_context.return_value = MagicMock()
                mock_context.return_value.obj = {'solace_agent_mesh': {}}
                
                # Call the function
                create_config_file_step(options, default_options, True, lambda x: None)
                
                # Get the config that was passed to write_config
                config = mock_config.write_config.call_args[0][0]
                
                # Check that the embedding service is disabled in the config
                services = config["solace_agent_mesh"]["built_in"]["services"]
                embedding_service = next((s for s in services if s["name"] == "embedding"), None)
                self.assertIsNotNone(embedding_service)
                self.assertFalse(embedding_service["enabled"])

    def test_build_solace_agent_mesh_embedding_enabled(self):
        """Test that when embedding service is enabled, the build process includes the embedding service"""
        config = {
            "built_in": {
                "services": [
                    {
                        "name": "embedding",
                        "enabled": True
                    }
                ]
            }
        }
        
        # Mock the necessary functions and classes
        with patch('cli.commands.build.os.path.join') as mock_join, \
             patch('cli.commands.build.os.listdir') as mock_listdir, \
             patch('cli.commands.build.open', create=True) as mock_open, \
             patch('cli.commands.build.apply_document_parsers') as mock_apply_parsers:
            
            # Mock os.path.join to return predictable paths
            mock_join.side_effect = lambda *args: '/'.join(args)
            
            # Mock os.listdir to return a list of files including service_embedding.yaml
            mock_listdir.return_value = ['service_embedding.yaml', 'other_file.yaml']
            
            # Mock open to return a file-like object
            mock_file = MagicMock()
            mock_file.__enter__.return_value.read.return_value = "content"
            mock_open.return_value = mock_file
            
            # Mock apply_document_parsers to return the content unchanged
            mock_apply_parsers.side_effect = lambda content, parsers: content
            
            # Create a mock abort function
            mock_abort = MagicMock()
            
            # Call the function
            build_solace_agent_mesh(config, self.temp_dir, mock_abort, [])
            
            # Check that service_embedding.yaml was processed (not skipped)
            mock_open.assert_any_call('/'.join([self.temp_dir, 'service_embedding.yaml']), 'w', encoding='utf-8')

    def test_build_solace_agent_mesh_embedding_disabled(self):
        """Test that when embedding service is disabled, the build process skips the embedding service"""
        config = {
            "built_in": {
                "services": [
                    {
                        "name": "embedding",
                        "enabled": False
                    }
                ]
            }
        }
        
        # Mock the necessary functions and classes
        with patch('cli.commands.build.os.path.join') as mock_join, \
             patch('cli.commands.build.os.listdir') as mock_listdir, \
             patch('cli.commands.build.open', create=True) as mock_open, \
             patch('cli.commands.build.apply_document_parsers') as mock_apply_parsers, \
             patch('cli.commands.build.click.echo') as mock_echo:
            
            # Mock os.path.join to return predictable paths
            mock_join.side_effect = lambda *args: '/'.join(args)
            
            # Mock os.listdir to return a list of files including service_embedding.yaml
            mock_listdir.return_value = ['service_embedding.yaml', 'other_file.yaml']
            
            # Mock open to return a file-like object
            mock_file = MagicMock()
            mock_file.__enter__.return_value.read.return_value = "content"
            mock_open.return_value = mock_file
            
            # Mock apply_document_parsers to return the content unchanged
            mock_apply_parsers.side_effect = lambda content, parsers: content
            
            # Create a mock abort function
            mock_abort = MagicMock()
            
            # Call the function
            build_solace_agent_mesh(config, self.temp_dir, mock_abort, [])
            
            # Check that service_embedding.yaml was not processed (skipped)
            for call in mock_open.call_args_list:
                self.assertNotEqual(call[0][0], '/'.join([self.temp_dir, 'service_embedding.yaml']))
            
            # Check that the skip message was echoed
            mock_echo.assert_any_call("Skipping embedding service as it is disabled.")

    def test_build_solace_agent_mesh_backward_compatibility(self):
        """Test that for backward compatibility, if the services section doesn't exist, the embedding service is included"""
        config = {
            "built_in": {
                # No services section
            }
        }
        
        # Mock the necessary functions and classes
        with patch('cli.commands.build.os.path.join') as mock_join, \
             patch('cli.commands.build.os.listdir') as mock_listdir, \
             patch('cli.commands.build.open', create=True) as mock_open, \
             patch('cli.commands.build.apply_document_parsers') as mock_apply_parsers:
            
            # Mock os.path.join to return predictable paths
            mock_join.side_effect = lambda *args: '/'.join(args)
            
            # Mock os.listdir to return a list of files including service_embedding.yaml
            mock_listdir.return_value = ['service_embedding.yaml', 'other_file.yaml']
            
            # Mock open to return a file-like object
            mock_file = MagicMock()
            mock_file.__enter__.return_value.read.return_value = "content"
            mock_open.return_value = mock_file
            
            # Mock apply_document_parsers to return the content unchanged
            mock_apply_parsers.side_effect = lambda content, parsers: content
            
            # Create a mock abort function
            mock_abort = MagicMock()
            
            # Call the function
            build_solace_agent_mesh(config, self.temp_dir, mock_abort, [])
            
            # Check that service_embedding.yaml was processed (not skipped)
            mock_open.assert_any_call('/'.join([self.temp_dir, 'service_embedding.yaml']), 'w', encoding='utf-8')


if __name__ == "__main__":
    unittest.main()