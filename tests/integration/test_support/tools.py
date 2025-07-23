from typing import Dict, Any, Optional
from google.adk.tools import ToolContext


async def get_weather_tool(
    location: str,
    unit: Optional[str] = "celsius",
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    A mock weather tool for testing.
    """
    print(f"[TestTool:get_weather_tool] Called with location: {location}, unit: {unit}")
    if location.lower() == "london":
        return {"temperature": "22", "unit": unit or "celsius", "condition": "sunny"}
    elif location.lower() == "paris":
        return {"temperature": "25", "unit": unit or "celsius", "condition": "lovely"}
    else:
        return {
            "temperature": "unknown",
            "unit": unit or "celsius",
            "condition": "unknown",
        }
