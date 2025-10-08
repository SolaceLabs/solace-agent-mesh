"""
This __init__.py file ensures that all built-in tool modules are imported
when the 'tools' package is loaded. This is crucial for the declarative
tool registration pattern, as it triggers the `tool_registry.register()`
calls within each tool module.
"""

from . import (
    audio_tools,
    builtin_artifact_tools,
    builtin_data_analysis_tools,
    dynamic_tool,
    general_agent_tools,
    image_tools,
    test_tools,
    web_tools,
)
