"""
Utility functions for handling placeholders in declarative test YAML files.
"""

import re
from typing import Any, Dict


def substitute_placeholders(data: Any, context: Dict[str, str]) -> Any:
    """
    Recursively substitute placeholders in test data with actual values.
    
    Placeholders use the format: {{PLACEHOLDER_NAME}}
    
    Args:
        data: The data structure (dict, list, str, etc.) to process
        context: Dictionary mapping placeholder names to their values
        
    Returns:
        The data with all placeholders replaced
        
    Example:
        context = {"STATIC_FILE_SERVER_URL": "http://localhost:8089"}
        data = "Fetch from {{STATIC_FILE_SERVER_URL}}/sample.json"
        result = substitute_placeholders(data, context)
        # result: "Fetch from http://localhost:8089/sample.json"
    """
    if isinstance(data, str):
        # Replace all placeholders in the string
        result = data
        for placeholder, value in context.items():
            pattern = r'\{\{' + re.escape(placeholder) + r'\}\}'
            result = re.sub(pattern, value, result)
        return result
    
    elif isinstance(data, dict):
        # Recursively process dictionary values
        return {key: substitute_placeholders(value, context) for key, value in data.items()}
    
    elif isinstance(data, list):
        # Recursively process list items
        return [substitute_placeholders(item, context) for item in data]
    
    else:
        # Return other types unchanged (int, bool, None, etc.)
        return data


def create_test_context(test_static_file_server=None, test_llm_server=None) -> Dict[str, str]:
    """
    Create a context dictionary with all available placeholder values.
    
    Args:
        test_static_file_server: TestStaticFileServer fixture instance
        test_llm_server: TestLLMServer fixture instance
        
    Returns:
        Dictionary mapping placeholder names to their values
    """
    context = {}
    
    if test_static_file_server:
        context["STATIC_FILE_SERVER_URL"] = test_static_file_server.url
    
    if test_llm_server:
        context["LLM_SERVER_URL"] = test_llm_server.url
    
    return context
