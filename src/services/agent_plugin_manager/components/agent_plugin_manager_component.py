"""Component that manages agent plugins."""

import os
import logging
from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.message import Message
from ..agent_plugin_manager import AgentPluginManager

log = logging.getLogger(__name__)

info = {
    "class_name": "AgentPluginManagerComponent",
    "description": "Component that manages agent plugins",
    "config_parameters": [
        {
            "name": "module_directory",
            "required": False,
            "description": "Directory where modules are stored",
            "default": "src",
        },
        {
            "name": "agents_definition_file",
            "required": False,
            "description": "Path to the YAML file containing agent definitions",
            "default": "configs/agents.yaml",
        },
        {
            "name": "auto_create",
            "required": False,
            "description": "Whether to automatically create agents on initialization",
            "default": True,
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
    "output_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

class AgentPluginManagerComponent(ComponentBase):
    """
    Component that manages agent plugins.
    
    This component initializes the AgentPluginManager and creates agents
    based on the configuration.
    """
    def __init__(self, child_info=None, **kwargs):
        """
        Initialize the component.
        
        Args:
            child_info: Child component info
            **kwargs: Additional arguments
        """
        super().__init__(child_info or info, **kwargs)
        #self.connector = kwargs.get("connector")
        self.init()
        
    def init(self):
        """Initialize the component with configuration parameters."""
        #self.connector = connector
        
        # Get configuration
        module_directory = self.get_config("module_directory")
        agents_definition_file = self.get_config("agents_definition_file")
        auto_create = self.get_config("auto_create")
        
        log.info(f"Initializing AgentPluginManagerComponent with module_directory={module_directory}, "
                 f"agents_definition_file={agents_definition_file}, auto_create={auto_create}")
        
        try:
            # Initialize the AgentPluginManager
            self.agent_manager = AgentPluginManager(
                connector=self.connector,
                module_directory=module_directory,
                agents_definition_file=agents_definition_file,
                auto_create=auto_create
            )
            
            log.info(f"Initialized AgentPluginManagerComponent with {len(self.agent_manager.running_apps)} agents")
        except Exception as e:
            log.error(f"Failed to initialize AgentPluginManager: {e}")
            # Re-raise the exception to ensure the component fails to initialize
            raise
        
    def process(self, message: Message) -> Message:
        """
        Process incoming messages.
        
        This component doesn't actually process messages in the traditional sense.
        It's mainly used for initialization and management.
        
        Args:
            message: The incoming message
            
        Returns:
            The same message, unmodified
        """
        # Just pass the message through
        return message
        
    def cleanup(self):
        """Clean up resources."""
        log.info("Cleaning up AgentPluginManagerComponent")
        if hasattr(self, 'agent_manager'):
            try:
                self.agent_manager.stop_all_agents()
                log.info("Successfully stopped all agents")
            except Exception as e:
                log.error(f"Error stopping agents: {e}")