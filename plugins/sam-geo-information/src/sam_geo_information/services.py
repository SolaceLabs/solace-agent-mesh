"""Services for handling geocoding and weather operations."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict
import asyncio
import requests

from .requests_session import requests_session_manager


@dataclass
class GeoLocation:
    """Represents a geographic location."""

    latitude: float
    longitude: float
    display_name: str
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    timezone: Optional[str] = None


class Units(Enum):
    """Supported unit systems."""

    METRIC = "metric"
    IMPERIAL = "imperial"


@dataclass
class WeatherData:
    """Weather data container."""

    temperature: float
    feels_like: float
    humidity: float
    wind_speed: float
    precipitation: float
    cloud_cover: int
    pressure: float
    units: Units
    description: str
    timestamp: datetime


class MapsCoGeocodingService:
    """Geocoding service implementation using geocode.maps.co."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Maps.co geocoding service."""
        self.base_url = "https://geocode.maps.co/search"
        self.api_key = api_key
        self.session = requests_session_manager.get_session()

    async def geocode(self, location: str) -> List[GeoLocation]:
        """Asynchronously convert a location string to geographic coordinates."""
        try:
            params = {"q": location}
            if self.api_key:
                params["api_key"] = self.api_key

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None, lambda: self.session.get(self.base_url, params=params, timeout=10)
            )
            response.raise_for_status()
            results = response.json()

            if not results:
                raise ValueError(f"No results found for location: {location}")

            locations = []
            for result in results:
                locations.append(
                    GeoLocation(
                        latitude=float(result["lat"]),
                        longitude=float(result["lon"]),
                        display_name=result["display_name"],
                        country=result.get("address", {}).get("country"),
                        state=result.get("address", {}).get("state"),
                        city=result.get("address", {}).get("city"),
                    )
                )
            return locations

        except requests.RequestException as e:
            raise ValueError(f"Geocoding request failed: {str(e)}") from e
        except (KeyError, ValueError) as e:
            raise ValueError(f"Error parsing geocoding response: {str(e)}") from e


class OpenMeteoWeatherService:
    """Weather service implementation using Open-Meteo API."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Open-Meteo weather service."""
        self.base_url = "https://api.open-meteo.com/v1"
        self.api_key = api_key
        self.session = requests_session_manager.get_session()

    def _generate_description(self, current: Dict, units: Units) -> str:
        """Generate a human-readable weather description."""
        temp_unit = "°F" if units == Units.IMPERIAL else "°C"
        speed_unit = "mph" if units == Units.IMPERIAL else "km/h"

        return (
            f"Temperature: {current['temperature_2m']}{temp_unit}, "
            f"Feels like: {current['apparent_temperature']}{temp_unit}, "
            f"Wind: {current['wind_speed_10m']}{speed_unit}, "
            f"Humidity: {current['relative_humidity_2m']}%"
        )

    def _generate_daily_description(self, daily: Dict, index: int, units: Units) -> str:
        """Generate a human-readable daily forecast description."""
        temp_unit = "°F" if units == Units.IMPERIAL else "°C"
        precip_unit = "in" if units == Units.IMPERIAL else "mm"

        return (
            f"High: {daily['temperature_2m_max'][index]}{temp_unit}, "
            f"Low: {daily['temperature_2m_min'][index]}{temp_unit}, "
            f"Precipitation: {daily['precipitation_sum'][index]}{precip_unit}"
        )

    async def get_current_weather(
        self, latitude: float, longitude: float, units: Units = Units.METRIC
    ) -> WeatherData:
        """Asynchronously get current weather from Open-Meteo."""
        try:
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "current": [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "precipitation",
                    "cloud_cover",
                    "pressure_msl",
                    "wind_speed_10m",
                ],
                "wind_speed_unit": "mph" if units == Units.IMPERIAL else "kmh",
                "temperature_unit": (
                    "fahrenheit" if units == Units.IMPERIAL else "celsius"
                ),
                "precipitation_unit": "inch" if units == Units.IMPERIAL else "mm",
            }
            if self.api_key:
                params["apikey"] = self.api_key

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.session.get(
                    f"{self.base_url}/forecast", params=params, timeout=10
                ),
            )
            response.raise_for_status()
            data = response.json()

            current = data.get("current", {})
            if not current:
                raise ValueError("No current weather data available")

            return WeatherData(
                temperature=current["temperature_2m"],
                feels_like=current["apparent_temperature"],
                humidity=current["relative_humidity_2m"],
                wind_speed=current["wind_speed_10m"],
                precipitation=current["precipitation"],
                cloud_cover=current["cloud_cover"],
                pressure=current["pressure_msl"],
                units=units,
                description=self._generate_description(current, units),
                timestamp=datetime.fromisoformat(current["time"]),
            )

        except requests.RequestException as e:
            raise ValueError(f"Weather request failed: {str(e)}") from e
        except (KeyError, ValueError) as e:
            raise ValueError(f"Error parsing weather response: {str(e)}") from e

    async def get_forecast(
        self,
        latitude: float,
        longitude: float,
        days: int = 7,
        units: Units = Units.METRIC,
    ) -> List[WeatherData]:
        """Asynchronously get weather forecast from Open-Meteo."""
        try:
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "daily": [
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "apparent_temperature_max",
                    "precipitation_sum",
                    "wind_speed_10m_max",
                    "relative_humidity_2m_max",
                ],
                "wind_speed_unit": "mph" if units == Units.IMPERIAL else "kmh",
                "temperature_unit": (
                    "fahrenheit" if units == Units.IMPERIAL else "celsius"
                ),
                "precipitation_unit": "inch" if units == Units.IMPERIAL else "mm",
                "forecast_days": min(days, 16),
            }
            if self.api_key:
                params["apikey"] = self.api_key

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.session.get(
                    f"{self.base_url}/forecast", params=params, timeout=10
                ),
            )
            response.raise_for_status()
            data = response.json()

            daily = data.get("daily", {})
            if not daily:
                raise ValueError("No forecast data available")

            forecast = []
            for i in range(len(daily["time"])):
                forecast.append(
                    WeatherData(
                        temperature=(
                            daily["temperature_2m_max"][i]
                            + daily["temperature_2m_min"][i]
                        )
                        / 2,
                        feels_like=daily["apparent_temperature_max"][i],
                        humidity=daily["relative_humidity_2m_max"][i],
                        wind_speed=daily["wind_speed_10m_max"][i],
                        precipitation=daily["precipitation_sum"][i],
                        cloud_cover=0,
                        pressure=0,
                        units=units,
                        description=self._generate_daily_description(daily, i, units),
                        timestamp=datetime.fromisoformat(daily["time"][i]),
                    )
                )
            return forecast

        except requests.RequestException as e:
            raise ValueError(f"Forecast request failed: {str(e)}") from e
        except (KeyError, ValueError) as e:
            raise ValueError(f"Error parsing forecast response: {str(e)}") from e
