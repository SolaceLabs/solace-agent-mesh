"""Tool for retrieving weather information for a location."""

from typing import Dict, Any, Optional
import yaml
from google.adk.tools import ToolContext
from solace_ai_connector.common.log import log

from .services import MapsCoGeocodingService, OpenMeteoWeatherService, Units


async def get_weather(
    location: str,
    units: str = "metric",
    forecast_days: int = 0,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Gets current weather conditions and optional forecast for a location.
    Supports both metric and imperial units.

    Args:
        location (str): The location to get weather for (can be a city name, address, etc.).
        units (str): The unit system to use ("metric" or "imperial"), default is "metric".
        forecast_days (int): Number of days to include in the forecast (0-16), default is 0 (current weather only).
    """
    plugin_name = "sam-geo-information"
    log_identifier = f"[{plugin_name}:get_weather]"
    log.info(
        f"{log_identifier} Received location: '{location}', units: {units}, forecast_days: {forecast_days}"
    )

    if not tool_config:
        return {"status": "error", "message": "Tool configuration is missing."}

    try:
        geocoding_api_key = tool_config.get("geocoding_api_key")
        weather_api_key = tool_config.get("weather_api_key")
        geocoding_service = MapsCoGeocodingService(api_key=geocoding_api_key)
        weather_service = OpenMeteoWeatherService(api_key=weather_api_key)

        if units.lower() not in ("metric", "imperial"):
            raise ValueError("Units must be either 'metric' or 'imperial'")
        units_enum = Units.METRIC if units.lower() == "metric" else Units.IMPERIAL

        if not 0 <= forecast_days <= 16:
            raise ValueError("Forecast days must be between 0 and 16")

        locations = await geocoding_service.geocode(location)
        if not locations:
            raise ValueError(f"No locations found for: {location}")

        loc = locations[0]

        current = await weather_service.get_current_weather(
            latitude=loc.latitude, longitude=loc.longitude, units=units_enum
        )

        result = {
            "location": loc.display_name,
            "current": {
                "temperature": current.temperature,
                "feels_like": current.feels_like,
                "humidity": current.humidity,
                "wind_speed": current.wind_speed,
                "precipitation": current.precipitation,
                "cloud_cover": current.cloud_cover,
                "pressure": current.pressure,
                "description": current.description,
                "timestamp": current.timestamp.isoformat(),
            },
            "units": units_enum.value,
        }

        if forecast_days > 0:
            forecast = await weather_service.get_forecast(
                latitude=loc.latitude,
                longitude=loc.longitude,
                days=forecast_days,
                units=units_enum,
            )

            result["forecast"] = [
                {
                    "temperature": day.temperature,
                    "feels_like": day.feels_like,
                    "humidity": day.humidity,
                    "wind_speed": day.wind_speed,
                    "precipitation": day.precipitation,
                    "description": day.description,
                    "timestamp": day.timestamp.isoformat(),
                }
                for day in forecast
            ]

        message = f"Weather information for {loc.display_name}:\n\n{yaml.dump(result)}"

        return {"status": "success", "message": message, "result": result}

    except Exception as e:
        log.exception(f"{log_identifier} Error getting weather information: {e}")
        return {
            "status": "error",
            "message": f"Error getting weather information: {str(e)}",
        }
