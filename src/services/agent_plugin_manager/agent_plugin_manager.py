"""Agent Plugin Manager for dynamically creating and managing agent applications."""

import os
import re
import yaml
import importlib
import importlib.util
import subprocess
import logging
import tempfile
from typing import Dict, List, Tuple, Any, Optional

import solace_ai_connector.main
from cli.config import Config

# Set up logging
log = logging.getLogger(__name__)

class AgentPluginManager:
    """
    Agent Plugin Manager for dynamically creating and managing agent applications.
    
    This class handles the dynamic creation and management of agent applications
    based on a configuration file. It can install plugins, load flow templates,
    substitute placeholders, and create apps using the connector's create_internal_app method.
    """
    
    def __init__(self, connector, module_directory: str = "src",
                 agents_definition_file: str = None, auto_create: bool = True):
        """
        Initialize the Agent Plugin Manager
        
        Args:
            connector: Instance of SolaceAiConnector
            module_directory: Directory where modules are stored (default: "src")
            agents_definition_file: Path to the YAML file containing agent definitions
                                   (if None, will be determined from config or defaults)
            auto_create: Whether to automatically create agents on initialization (default: True)
        """
        self.connector = connector
        self.module_directory = module_directory
        self.running_apps = []  # List of (agent_name, app) tuples
        
        # Determine the agents definition file path
        self.agents_definition_file = self._get_agents_definition_file_path(agents_definition_file)
        
        log.info(f"Initialized Agent Plugin Manager with definition file: {self.agents_definition_file}")
        
        # Automatically create agents if enabled
        if auto_create:
            try:
                self.create_agents()
            except Exception as e:
                log.error(f"Failed to automatically create agents: {e}")
        
    def create_agents(self) -> None:
        """
        Create agents based on the configuration in the definition file
        
        Raises:
            FileNotFoundError: If the agents definition file is not found
            ValueError: If the agents definition file is invalid
        """
        log.info(f"Creating agents from definition file: {self.agents_definition_file}")
        
        if not os.path.exists(self.agents_definition_file):
            log.error(f"Agents definition file not found: {self.agents_definition_file}")
            raise FileNotFoundError(f"Agents definition file not found: {self.agents_definition_file}")
            
        with open(self.agents_definition_file, 'r') as f:
            try:
                config = yaml.safe_load(f)
                log.debug(f"Loaded config from {self.agents_definition_file}")
            except yaml.YAMLError as e:
                log.error(f"Invalid YAML in {self.agents_definition_file}: {e}")
                raise ValueError(f"Invalid YAML in agents definition file: {self.agents_definition_file}")
            
        if 'agents' not in config:
            log.error("Invalid agents definition file: 'agents' key not found")
            raise ValueError("Invalid agents definition file: 'agents' key not found")
            
        for agent_config in config['agents']:
            name = agent_config.get('name')
            plugin_url = agent_config.get('plugin')
            user_config = agent_config.get('config', {})
            env_vars = agent_config.get('env-vars', {})
            
            if not name or not plugin_url:
                log.error(f"Invalid agent configuration: name and plugin are required")
                raise ValueError(f"Invalid agent configuration: name and plugin are required")
                
            log.info(f"Creating agent {name} from plugin {plugin_url}")
            self.create_agent(name, plugin_url, user_config, env_vars)
            
        log.info(f"Finished creating agents from definition file")
            
    def create_agent(self, name: str, plugin_url: str, user_config: Dict, env_vars: Dict = None) -> Any:
        """
        Create a single agent
        
        Args:
            name: Name of the agent
            plugin_url: URL or path to the plugin
            user_config: User-provided configuration for the agent
            env_vars: Environment variables to set before running the agent
            
        Returns:
            The created app
            
        Raises:
            ValueError: If the plugin cannot be installed or the flow template cannot be loaded
        """
        log.info(f"Creating agent: {name}")
        
        # Install the plugin if needed
        plugin_name = self.install_plugin(plugin_url)
        
        # Load the flow template as text and get the file path
        template_content, template_file_path = self.load_agent_flow_template(plugin_name)
        
        # Process the flow template
        flow_config = self.process_flow_template(template_content, name, plugin_name, user_config, env_vars, template_file_path)
        
        # Create the app using the connector
        app = self.connector.create_internal_app(name, flow_config.get('apps', [])[0].get('flows', []))
        
        # Add to running apps
        self.running_apps.append((name, app))
        
        log.info(f"Successfully created and started agent: {name}")
        
        return app
        
    def install_plugin(self, plugin_url: str) -> str:
        """
        Install a plugin if it's not already installed
        
        Args:
            plugin_url: URL or path to the plugin
            
        Returns:
            The name of the installed plugin
            
        Raises:
            ValueError: If the plugin cannot be installed
        """
        # Extract plugin name from URL
        plugin_name = self._extract_plugin_name(plugin_url)
        
        log.info(f"Checking if plugin {plugin_name} is installed")
        
        # Check if the plugin is already installed
        try:
            importlib.import_module(plugin_name)
            log.info(f"Plugin {plugin_name} is already installed")
            return plugin_name
        except ImportError:
            log.info(f"Plugin {plugin_name} is not installed, installing now")
            
            try:
                # Install the plugin using pip
                # For Git URLs, we need to prefix with "git+"
                if plugin_url.startswith('https://github.com/') or plugin_url.startswith('https://gitlab.com/'):
                    install_url = f"git+{plugin_url}"
                else:
                    install_url = plugin_url
                    
                # Find the path to pip
                pip_path = subprocess.check_output(['which', 'pip3']).strip().decode('utf-8')
                if not pip_path:
                    raise ValueError("pip3 not found in PATH")
                log.info(f"Using pip path: {pip_path}")
                # Install the plugin
                log.info(f"Installing plugin from {install_url}")
                subprocess.check_call(['pip3', 'install', install_url])
                log.info(f"Successfully installed plugin {plugin_name}")
                return plugin_name
            except subprocess.CalledProcessError as e:
                log.error(f"Failed to install plugin {plugin_name}: {e}")
                raise ValueError(f"Failed to install plugin {plugin_name}: {e}")
            
    def _extract_plugin_name(self, plugin_url: str) -> str:
        """
        Extract the plugin name from a URL
        
        Args:
            plugin_url: URL or path to the plugin
            
        Returns:
            The name of the plugin
        """
        log.debug(f"Extracting plugin name from URL: {plugin_url}")
        
        # Handle GitHub URLs with subdirectory
        if '#subdirectory=' in plugin_url:
            base_url, subdirectory = plugin_url.split('#subdirectory=')
            log.debug(f"Extracted plugin name from subdirectory: {subdirectory}")
            return subdirectory
            
        # Handle simple GitHub URLs
        if plugin_url.startswith('https://github.com/'):
            parts = plugin_url.split('/')
            plugin_name = parts[-1]
            log.debug(f"Extracted plugin name from GitHub URL: {plugin_name}")
            return plugin_name
            
        # Handle local paths
        if os.path.exists(plugin_url):
            plugin_name = os.path.basename(plugin_url)
            log.debug(f"Extracted plugin name from local path: {plugin_name}")
            return plugin_name
            
        # Default: use the URL as is
        log.debug(f"Using URL as plugin name: {plugin_url}")
        return plugin_url
        
    def load_agent_flow_template(self, plugin_name: str) -> Tuple[str, str]:
        """
        Load the flow template from the plugin as text
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            A tuple containing the flow template content as text and the path to the template file
            
        Raises:
            ValueError: If the flow template cannot be loaded
        """
        log.info(f"Loading flow template for plugin: {plugin_name}")
        
        # Replace all hyphens with underscores in the plugin name
        plugin_name = plugin_name.replace('-', '_')

        # Find the plugin's configs/agents directory
        plugin_spec = importlib.util.find_spec(plugin_name)
        if not plugin_spec or not plugin_spec.submodule_search_locations:
            log.error(f"Plugin {plugin_name} not found")
            raise ValueError(f"Plugin {plugin_name} not found")
            
        plugin_path = plugin_spec.submodule_search_locations[0]
        agent_config_path = os.path.join(plugin_path, 'configs', 'agents')
        
        log.debug(f"Looking for flow templates in: {agent_config_path}")
        
        # Look for flow files in the directory
        if not os.path.exists(agent_config_path):
            log.error(f"Agent configs directory not found in plugin {plugin_name}")
            raise ValueError(f"Agent configs directory not found in plugin {plugin_name}")
            
        # Get the first YAML file in the directory
        yaml_files = [f for f in os.listdir(agent_config_path) if f.endswith('.yaml')]
        if not yaml_files:
            log.error(f"No agent flow files found in plugin {plugin_name}")
            raise ValueError(f"No agent flow files found in plugin {plugin_name}")
            
        # Load the flow template as text
        flow_file = os.path.join(agent_config_path, yaml_files[0])
        log.info(f"Loading flow template from: {flow_file}")
        
        try:
            with open(flow_file, 'r') as f:
                template_content = f.read()
                
            log.debug(f"Successfully loaded flow template as text from {flow_file}")
            return template_content, flow_file
        except Exception as e:
            log.error(f"Failed to load flow template from {flow_file}: {e}")
            raise ValueError(f"Failed to load flow template from {flow_file}: {e}")
        
    def process_flow_template(self, template_content: str, agent_name: str, plugin_name: str, user_config: Dict, env_vars: Dict = None, original_file_path: str = None) -> Dict:
        """
        Process the flow template by substituting placeholders, applying user config, and setting environment variables
        
        Args:
            template_content: The flow template content as text
            agent_name: Name of the agent
            plugin_name: Name of the plugin
            user_config: User-provided configuration for the agent
            env_vars: Environment variables to set
            original_file_path: Path to the original template file
            
        Returns:
            The processed flow configuration as a dictionary
        """
        log.info(f"Processing flow template for agent: {agent_name}")
        
        # 1. Substitute placeholders in the template
        processed_content = self.substitute_placeholders_in_text(template_content, agent_name, plugin_name)
        
        # 2. Set environment variables if provided
        if env_vars:
            self._set_environment_variables(agent_name, env_vars)

        # 3. Substitute environment variables in the template
        processed_content = self.substitute_env_vars_in_text(processed_content)
        
        # 4. Apply user configuration to the template content
        processed_content = self._apply_user_config_to_template(processed_content, user_config)
        
        # 5. Write the processed content to a temporary file and load it using solace_ai_connector.main.load_config
        try:
            # Create a temporary file with the processed content
            temp_file_path = self._create_temp_file_with_content(processed_content, original_file_path or "temp_config.yaml")
            
            try:
                # Load the configuration using solace_ai_connector.main.load_config
                flow_config = solace_ai_connector.main.load_config(temp_file_path)
                log.debug(f"Successfully loaded flow template using solace_ai_connector.main.load_config")
            finally:
                # Clean up the temporary file
                try:
                    os.unlink(temp_file_path)
                    os.rmdir(os.path.dirname(temp_file_path))
                    log.debug(f"Cleaned up temporary file: {temp_file_path}")
                except Exception as e:
                    log.warning(f"Failed to clean up temporary file {temp_file_path}: {e}")
        except Exception as e:
            log.error(f"Failed to load flow template: {e}")
            raise ValueError(f"Failed to load flow template: {e}")
        
        return flow_config
        
    def substitute_placeholders_in_text(self, template_content: str, agent_name: str, plugin_name: str) -> str:
        """
        Substitute placeholders in the template content
        
        Args:
            template_content: The template content as text
            agent_name: Name of the agent
            plugin_name: Name of the plugin
            
        Returns:
            The template content with placeholders substituted
        """
        log.info(f"Substituting placeholders in template for agent: {agent_name}")
        
        # Create snake_case and SNAKE_CASE versions of the name
        snake_case_name = agent_name.replace('-', '_').lower()
        snake_upper_case_name = snake_case_name.upper()
        
        # Format the module directory using the plugin name
        module_directory = f"{plugin_name.replace('-', '_')}.src"
        
        log.debug(f"Substituting {{{{SNAKE_CASE_NAME}}}} with {snake_case_name}")
        log.debug(f"Substituting {{{{SNAKE_UPPER_CASE_NAME}}}} with {snake_upper_case_name}")
        log.debug(f"Substituting {{{{MODULE_DIRECTORY}}}} with {module_directory}")
        
        # Substitute placeholders
        content = template_content.replace('{{SNAKE_CASE_NAME}}', snake_case_name)
        content = content.replace('{{SNAKE_UPPER_CASE_NAME}}', snake_upper_case_name)
        content = content.replace('{{MODULE_DIRECTORY}}', module_directory)
        
        return content
        
    def substitute_env_vars_in_text(self, template_content: str) -> str:
        """
        Substitute environment variables in the template content
        
        Args:
            template_content: The template content as text
            
        Returns:
            The template content with environment variables substituted
        """
        log.info(f"Substituting environment variables in template")
        
        # Regular expression to match ${VAR_NAME} or ${VAR_NAME, default_value}
        pattern = r'\${([^,}]+)(?:,\s*([^}]+))?}'
        
        def replace_env_var(match):
            var_name = match.group(1).strip()
            default_value = match.group(2).strip() if match.group(2) else ''
            
            # Get the value from environment variables or use the default
            value = os.environ.get(var_name, default_value)
            log.debug(f"Substituting ${{{var_name}}} with {value}")
            return value
        
        # Replace all environment variables in the template
        content = re.sub(pattern, replace_env_var, template_content)
        
        return content
        
    def _create_temp_file_with_content(self, content: str, original_filename: str) -> str:
        """
        Create a temporary file with the given content and a similar filename to the original.
        
        Args:
            content: The content to write to the file
            original_filename: The original filename to base the temporary filename on
            
        Returns:
            The path to the temporary file
        """
        # Extract the filename from the original path
        filename = os.path.basename(original_filename)
        
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        
        # Create the file path in the temporary directory
        temp_path = os.path.join(temp_dir, filename)
        
        # Write the content to the file
        with open(temp_path, 'w') as f:
            f.write(content)
            
        log.debug(f"Created temporary file: {temp_path}")
        
        return temp_path
        
    def _apply_user_config_to_template(self, template_content: str, user_config: Dict) -> str:
        """
        Apply user configuration to the template content.
        
        Args:
            template_content: The template content as text
            user_config: User-provided configuration for the agent
            
        Returns:
            The template content with user configuration applied
        """
        log.info(f"Applying user configuration to template content")
        
        # Parse the template content as YAML
        try:
            flow_config = yaml.safe_load(template_content)
            log.debug(f"Successfully parsed template content as YAML")
        except Exception as e:
            log.error(f"Failed to parse template content as YAML: {e}")
            raise ValueError(f"Failed to parse template content as YAML: {e}")
        
        # Apply user configuration to the agent component
        if 'flows' in flow_config and isinstance(flow_config['flows'], list) and flow_config['flows']:
            first_flow = flow_config['flows'][0]
            if 'components' in first_flow and len(first_flow['components']) >= 2:
                agent_component = first_flow['components'][1]
                
                log.debug(f"Found agent component: {agent_component.get('component_name')}")
                
                # Update the component config with user config
                if 'component_config' not in agent_component:
                    agent_component['component_config'] = {}
                    
                agent_component['component_config'].update(user_config)
                log.debug("Updated component config with user config")
            else:
                log.warning("Could not find agent component in flow components, skipping user config application")
        else:
            log.warning(f"Could not find flow list in flow config, skipping user config application")
        
        # Convert back to YAML
        return yaml.dump(flow_config)
        
    def list_agents(self) -> List[Dict]:
        """
        List all running agents
        
        Returns:
            List of dictionaries containing information about each agent
        """
        log.info(f"Listing all running agents")
        return [{'name': name, 'app': app} for name, app in self.running_apps]
        
    def stop_agent(self, agent_name: str) -> bool:
        """
        Stop a running agent
        
        Args:
            agent_name: Name of the agent to stop
            
        Returns:
            True if the agent was stopped, False otherwise
        """
        log.info(f"Stopping agent: {agent_name}")
        
        for i, (name, app) in enumerate(self.running_apps):
            if name == agent_name:
                app.cleanup()
                self.running_apps.pop(i)
                log.info(f"Successfully stopped agent: {agent_name}")
                return True
                
        log.warning(f"Agent {agent_name} not found, cannot stop")
        return False
        
    def stop_all_agents(self) -> None:
        """
        Stop all running agents
        """
        log.info(f"Stopping all agents")
        
        for name, app in self.running_apps:
            log.info(f"Stopping agent: {name}")
            app.cleanup()
            
        self.running_apps.clear()
        log.info(f"All agents stopped")
        
    def _set_environment_variables(self, agent_name: str, env_vars: Dict) -> None:
        """
        Set environment variables for an agent
        
        Args:
            agent_name: Name of the agent
            env_vars: Dictionary of environment variables to set
        """
        log.info(f"Setting environment variables for agent: {agent_name}")
        
        for key, value in env_vars.items():
            log.debug(f"Setting environment variable {key}={value}")
            os.environ[key] = str(value)
            
        log.info(f"Successfully set {len(env_vars)} environment variables for agent: {agent_name}")
        
    def _get_agents_definition_file_path(self, provided_path: str = None) -> str:
        """
        Determine the path to the agents definition file
        
        The path is determined in the following order of precedence:
        1. Path provided in the constructor
        2. Path from environment variable AGENT_DEFINITION_FILE
        3. Path from Solace Agent Mesh config file
        4. Default path: configs/agents.yaml
        
        Args:
            provided_path: Path provided in the constructor
            
        Returns:
            The path to the agents definition file
        """
        # 1. Use the path provided in the constructor if available
        if provided_path:
            log.info(f"Using provided agents definition file path: {provided_path}")
            return provided_path
            
        # 2. Check for environment variable
        env_path = os.environ.get("AGENT_DEFINITION_FILE")
        if env_path:
            log.info(f"Using agents definition file path from environment variable: {env_path}")
            return env_path
            
        # 3. Check for path in Solace Agent Mesh config file
        try:
            config_path = self._get_path_from_config()
            if config_path:
                log.info(f"Using agents definition file path from config: {config_path}")
                return config_path
        except Exception as e:
            log.debug(f"Failed to get agents definition file path from config: {e}")
            
        # 4. Use default path
        default_path = "configs/agents.yaml"
        log.info(f"Using default agents definition file path: {default_path}")
        return default_path
        
    def _get_path_from_config(self) -> str:
        """
        Get the agents definition file path from the Solace Agent Mesh config
        
        Returns:
            The path from the config, or None if not found
        """
        try:
            config = Config.get_config()
            return config.get("solace_agent_mesh", {}).get("runtime", {}).get("agent_plugin_manager", {}).get("definition_file")
        except Exception as e:
            log.debug(f"Error accessing config: {e}")
            return None