"""Tool for converting city names to timezone information."""

from typing import Dict, Any, Optional
from timezonefinder import TimezoneFinder
import pytz
import yaml
from google.adk.tools import ToolContext
from solace_ai_connector.common.log import log

from .services import MapsCoGeocodingService


async def city_to_timezone(
    city: str,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Converts a city name to its timezone information, including current UTC offset and DST status.

    Args:
        city (str): The name of the city to look up.
    """
    plugin_name = "sam-geo-information"
    log_identifier = f"[{plugin_name}:city_to_timezone]"
    log.info(f"{log_identifier} Received city: '{city}'")

    if not tool_config:
        return {"status": "error", "message": "Tool configuration is missing."}

    try:
        geocoding_api_key = tool_config.get("geocoding_api_key")
        geocoding_service = MapsCoGeocodingService(api_key=geocoding_api_key)
        timezone_finder = TimezoneFinder()

        locations = await geocoding_service.geocode(city)
        if not locations:
            raise ValueError(f"No locations found for city: {city}")

        results = []
        for loc in locations:
            timezone_str = timezone_finder.timezone_at(
                lat=loc.latitude, lng=loc.longitude
            )
            if not timezone_str:
                continue

            timezone = pytz.timezone(timezone_str)
            now = pytz.datetime.datetime.now(timezone)

            result = {
                "location": loc.display_name,
                "timezone": timezone_str,
                "utc_offset": now.strftime("%z"),
                "dst_active": bool(now.dst()),
                "current_time": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
            }
            results.append(result)

        if not results:
            raise ValueError(
                f"Could not determine timezone for any matching location: {city}"
            )

        message = f"Found timezone information for {len(results)} possible match(es) for {city}:\n\n{yaml.dump(results)}"

        return {"status": "success", "message": message, "results": results}

    except Exception as e:
        log.exception(f"{log_identifier} Error looking up timezone: {e}")
        return {"status": "error", "message": f"Error looking up timezone: {str(e)}"}
