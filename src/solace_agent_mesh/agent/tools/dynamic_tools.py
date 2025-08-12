"""
Dynamic tool implementations for the Solace Agent Mesh framework.
This module provides handlers for dynamically configured tools like REST API tools.
"""

from typing import Dict, Any, List, Optional
from .tool_definition import BuiltinTool
from solace_ai_connector.common.log import log
from abc import abstractmethod

@abstractmethod
def initialize_rest_api_tools(component, config: Dict[str, Any]) -> List[BuiltinTool]:
    """
    Initialize REST API tools from configuration.
        
    Args:
        component: The agent component.
        config: The configuration for the REST API tools.
            
    Returns:
        A list of created BuiltinTool instances.
    """
    raise NotImplementedError
