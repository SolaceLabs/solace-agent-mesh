"""Tool for converting city names to geographic coordinates."""

from typing import Dict, Any, Optional
import yaml
from google.adk.tools import ToolContext
from solace_ai_connector.common.log import log

from .services import MapsCoGeocodingService


async def city_to_coordinates(
    city: str,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Converts a city name to its geographic coordinates.
    If multiple matches are found, all possibilities will be returned.

    Args:
        city (str): The name of the city to look up.
    """
    plugin_name = "sam-geo-information"
    log_identifier = f"[{plugin_name}:city_to_coordinates]"
    log.info(f"{log_identifier} Received city: '{city}'")

    if not tool_config:
        return {"status": "error", "message": "Tool configuration is missing."}

    try:
        geocoding_api_key = tool_config.get("geocoding_api_key")
        geocoding_service = MapsCoGeocodingService(api_key=geocoding_api_key)

        locations = await geocoding_service.geocode(city)

        results = []
        for loc in locations:
            result = {
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "display_name": loc.display_name,
            }
            if loc.country:
                result["country"] = loc.country
            if loc.state:
                result["state"] = loc.state
            if loc.city:
                result["city"] = loc.city
            results.append(result)

        if not results:
            return {
                "status": "not_found",
                "message": f"No coordinates found for '{city}'.",
            }

        message = f"Found {len(results)} possible match(es) for {city}:\n\n{yaml.dump(results)}"

        return {"status": "success", "message": message, "results": results}

    except Exception as e:
        log.exception(f"{log_identifier} Error looking up coordinates: {e}")
        return {"status": "error", "message": f"Error looking up coordinates: {str(e)}"}
