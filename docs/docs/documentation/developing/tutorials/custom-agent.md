---
title: Build Your Own Agent
sidebar_position: 5
---

# Build Your Own Agent

This tutorial shows you how to build a sophisticated weather agent using the Agent Mesh framework. Learn how to integrate with external APIs, manage resources properly, and create production-ready agents.

## Overview

Our weather agent will demonstrate:
- External API integration (OpenWeatherMap)
- Professional service layer architecture
- Multiple sophisticated tools
- Proper lifecycle management
- Error handling and validation
- Artifact creation and management

## Prerequisites

Before starting this tutorial, make sure you have:
- Read the [Create Agent](../create-agents.md) tutorial
- An OpenWeatherMap API key (free at [openweathermap.org](https://openweathermap.org/api))
- Basic understanding of Python async/await
- Familiarity with HTTP APIs

## Planning the Weather Agent

Our weather agent will have the following capabilities:

1. **Get Current Weather**: Fetch current weather conditions for a specified location
2. **Get Weather Forecast**: Retrieve a multi-day weather forecast
3. **Save Weather Reports**: Store weather data as artifacts

The agent will demonstrate:
- External API integration
- Error handling and validation
- Configuration management
- Artifact creation
- Resource lifecycle management

## Step 1: Project Structure

Run the following command to create a new custom agent:

```bash
sam add agent --gui
```

:::tip
You can create an agent either by using the `sam add agent` command or by creating a new plugin of type agent, `sam plugin create my-hello-agent --type agent`. 

For information and recommendations about these options, see [`Agent or Plugin: Which To use?`](../../components/plugins.md#agent-or-plugin-which-to-use).

For an example of plugin agents, see the [Create Agents](../create-agents.md#creating-your-first-agent-step-by-step) guide.
:::

Follow the steps on the GUI to create a new agent named "Weather Agent". We can update the tools/skills section directly in the configuration file later.

:::warning[Important Notice]
This tutorial is intentionally comprehensive to demonstrate the full flexibility and advanced features available in Agent Mesh agents. For most straightforward use cases, you only need a simple Python function and a corresponding reference in your YAML configuration file.

<details>
<summary>Simple Weather Agent Example</summary>

After going through the add agent wizard from `sam add agent --gui`, create the following file under `src/weather_agent/tools.py` directory:

```py
# src/weather_agent/tools.py
import httpx
from typing import Any, Dict, Optional
from google.adk.tools import ToolContext
from solace_ai_connector.common.log import log


async def get_current_weather(
    location: str,
    units: str = "metric",
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Get current weather conditions for a specified location.
    
    Args:
        location: City name, state, and country (for example, "New York, NY, US")
        units: Temperature units - "metric" (Celsius), "imperial" (Fahrenheit), or "kelvin"
    """
    log.info("[GetCurrentWeather] Getting current weather for: %s", location)
    base_url = "https://api.openweathermap.org/data/2.5"
    api_key = tool_config.get("api_key") if tool_config else None

    url = f"{base_url}/weather"
    params = {
        "q": location,
        "appid": api_key,
        "units": units
    }

    try:
        # Fetch weather data
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            weather_data = response.json()
        
        result = {
            "status": "success",
            "location": location,
            "units": units,
            "data": weather_data
        }
        return result
    
    except Exception as e:
        log.error(f"[GetCurrentWeather] Error getting weather: {e}")
        return {
            "status": "error",
            "message": f"Weather service error: {str(e)}"
        }


async def get_weather_forecast(
    location: str,
    days: int = 5,
    units: str = "metric",
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Get weather forecast for a specified location.
    
    Args:
        location: City name, state, and country
        days: Number of days for forecast (1-5)
        units: Temperature units
    """
    log.info("[GetWeatherForecast] Getting %d-day forecast for: %s", days, location)
    base_url = "https://api.openweathermap.org/data/2.5"
    api_key = tool_config.get("api_key") if tool_config else None

    url = f"{base_url}/forecast"
    params = {
        "q": location,
        "appid": api_key,
        "units": units,
        "cnt": min(days * 8, 40) 
    }

    try:
        # Fetch forecast data
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            forecast_data = response.json()

        result = {
            "status": "success",
            "location": forecast_data["location"],
            "days": days,
            "units": units,
            "data": forecast_data
        }
        return result
    except Exception as e:
        log.error(f"[GetWeatherForecast] Error getting forecast: {e}")
        return {
            "status": "error",
            "message": f"Weather service error: {str(e)}"
        }

```
And update the weather agent config file's tool section under `configs/agent/weather-agent.yaml` as follows:

```yaml
      # Tools configuration
      tools:
        # Current weather tool
        - tool_type: python
          component_module: "src.weather_agent.tools"
          component_base_path: .
          function_name: "get_current_weather"
          tool_description: "Get current weather conditions for a specified location"
          tool_config:
            api_key: ${OPENWEATHER_API_KEY}

        # Weather forecast tool
        - tool_type: python
          component_module: "src.weather_agent.tools"
          function_name: "get_weather_forecast"
          component_base_path: .
          tool_description: "Get weather forecast for up to 5 days for a specified location"
          tool_config:
            api_key: ${OPENWEATHER_API_KEY}

```

For better discoverability, update the [agent card](../../components/agents.md#agent-card) section in the same YAML file as follows:
```yaml
      # Agent card
      agent_card:
        description: "Professional weather agent providing current conditions, forecasts, and weather comparisons"
        defaultInputModes: ["text"]
        defaultOutputModes: ["text"]
        skills:
          - id: "get_current_weather"
            name: "Get Current Weather"
            description: "Retrieve current weather conditions for any location worldwide"
          - id: "get_weather_forecast"
            name: "Get Weather Forecast"
            description: "Provide detailed weather forecasts up to 5 days ahead"
```

To run the agent, you can continue following documentation from [Step 6](#step-6-environment-setup) of this tutorial.
</details>

Other concepts mentioned in this page such as lifecycle, services, artifacts are just to showcase more advanced patterns.
:::

Create the directory structure for the weather agent:

```
sam-project/
├── src/
│   └── weather_agent/
│       ├── __init__.py
│       ├── tools.py
│       ├── lifecycle.py
│       └── services/
│           ├── __init__.py
│           └── weather_service.py
├── configs
│   └── shared_config.yaml
│   └── agents/
│       └── weather_agent.yaml
...
```
:::tip
In Agent Mesh, you can create an agent either by using the `sam add agent` command or by creating a new plugin of type agent, `sam plugin create your-agent --type agent`. 

This tutorial uses the `sam add agent` command to create a new agent named "Weather Agent", for an example of creating a custom agent plugin, see the [Create Agents](../create-agents.md) tutorial.

:::

## Step 2: Weather Service Implementation

First, create a service class to handle weather API interactions:

**`src/weather_agent/services/weather_service.py`:**

```python
"""
Weather service for interacting with external weather APIs.
"""

import aiohttp
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from solace_ai_connector.common.log import log


class WeatherService:
    """Service for fetching weather data from external APIs."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.openweathermap.org/data/2.5"):
        self.api_key = api_key
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.log_identifier = "[WeatherService]"
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an HTTP session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
            log.info(f"{self.log_identifier} HTTP session closed")
    
    async def get_current_weather(self, location: str, units: str = "metric") -> Dict[str, Any]:
        """
        Get current weather for a location.
        
        Args:
            location: City name, state code, and country code (for example, "London,UK")
            units: Temperature units (metric, imperial, kelvin)
        
        Returns:
            Dictionary containing current weather data
        """
        log.info(f"{self.log_identifier} Fetching current weather for: {location}")
        
        session = await self._get_session()
        url = f"{self.base_url}/weather"
        params = {
            "q": location,
            "appid": self.api_key,
            "units": units
        }
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    log.info(f"{self.log_identifier} Successfully fetched weather for {location}")
                    return self._format_current_weather(data)
                elif response.status == 404:
                    raise ValueError(f"Location '{location}' not found")
                else:
                    error_data = await response.json()
                    raise Exception(f"Weather API error: {error_data.get('message', 'Unknown error')}")
        
        except aiohttp.ClientError as e:
            log.error(f"{self.log_identifier} Network error fetching weather: {e}")
            raise Exception(f"Network error: {str(e)}")
    
    async def get_weather_forecast(self, location: str, days: int = 5, units: str = "metric") -> Dict[str, Any]:
        """
        Get weather forecast for a location.
        
        Args:
            location: City name, state code, and country code
            days: Number of days for forecast (1-5)
            units: Temperature units
        
        Returns:
            Dictionary containing forecast data
        """
        log.info(f"{self.log_identifier} Fetching {days}-day forecast for: {location}")
        
        session = await self._get_session()
        url = f"{self.base_url}/forecast"
        params = {
            "q": location,
            "appid": self.api_key,
            "units": units,
            "cnt": min(days * 8, 40)  # API returns 3-hour intervals, max 40 entries
        }
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    log.info(f"{self.log_identifier} Successfully fetched forecast for {location}")
                    return self._format_forecast_data(data, days)
                elif response.status == 404:
                    raise ValueError(f"Location '{location}' not found")
                else:
                    error_data = await response.json()
                    raise Exception(f"Weather API error: {error_data.get('message', 'Unknown error')}")
        
        except aiohttp.ClientError as e:
            log.error(f"{self.log_identifier} Network error fetching forecast: {e}")
            raise Exception(f"Network error: {str(e)}")
    
    def _format_current_weather(self, data: Dict) -> Dict[str, Any]:
        """Format current weather data for consistent output."""
        return {
            "location": f"{data['name']}, {data['sys']['country']}",
            "temperature": data['main']['temp'],
            "feels_like": data['main']['feels_like'],
            "humidity": data['main']['humidity'],
            "pressure": data['main']['pressure'],
            "description": data['weather'][0]['description'].title(),
            "wind_speed": data.get('wind', {}).get('speed', 0),
            "wind_direction": data.get('wind', {}).get('deg', 0),
            "visibility": data.get('visibility', 0) / 1000,  # Convert to km
            "timestamp": datetime.fromtimestamp(data['dt']).isoformat(),
            "sunrise": datetime.fromtimestamp(data['sys']['sunrise']).isoformat(),
            "sunset": datetime.fromtimestamp(data['sys']['sunset']).isoformat()
        }
    
    def _format_forecast_data(self, data: Dict, days: int) -> Dict[str, Any]:
        """Format forecast data for consistent output."""
        forecasts = []
        current_date = None
        daily_data = []
        
        for item in data['list'][:days * 8]:
            forecast_date = datetime.fromtimestamp(item['dt']).date()
            
            if current_date != forecast_date:
                if daily_data:
                    forecasts.append(self._aggregate_daily_forecast(daily_data))
                current_date = forecast_date
                daily_data = []
            
            daily_data.append(item)
        
        # Add the last day's data
        if daily_data:
            forecasts.append(self._aggregate_daily_forecast(daily_data))
        
        return {
            "location": f"{data['city']['name']}, {data['city']['country']}",
            "forecasts": forecasts[:days]
        }
    
    def _aggregate_daily_forecast(self, daily_data: List[Dict]) -> Dict[str, Any]:
        """Aggregate 3-hour forecasts into daily summary."""
        if not daily_data:
            return {}
        
        # Get temperatures for min/max calculation
        temps = [item['main']['temp'] for item in daily_data]
        
        # Use the forecast closest to noon for general conditions
        noon_forecast = min(daily_data, key=lambda x: abs(
            datetime.fromtimestamp(x['dt']).hour - 12
        ))
        
        return {
            "date": datetime.fromtimestamp(daily_data[0]['dt']).date().isoformat(),
            "temperature_min": min(temps),
            "temperature_max": max(temps),
            "description": noon_forecast['weather'][0]['description'].title(),
            "humidity": noon_forecast['main']['humidity'],
            "wind_speed": noon_forecast.get('wind', {}).get('speed', 0),
            "precipitation_probability": noon_forecast.get('pop', 0) * 100
        }
```

## Step 3: Weather Tools Implementation

Now create the tool functions:

**`src/weather_agent/tools.py`:**

```python
"""
Weather agent tools for fetching and processing weather data.
"""

import json
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from google.adk.tools import ToolContext
from solace_ai_connector.common.log import log
from solace_agent_mesh.agent.utils.artifact_helpers import save_artifact_with_metadata

async def get_current_weather(
    location: str,
    units: str = "metric",
    save_to_file: bool = False,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Get current weather conditions for a specified location.
    
    Args:
        location: City name, state, and country (for example, "New York, NY, US")
        units: Temperature units - "metric" (Celsius), "imperial" (Fahrenheit), or "kelvin"
        save_to_file: Whether to save the weather report as an artifact
    
    Returns:
        Dictionary containing current weather information
    """
    log_identifier = "[GetCurrentWeather]"
    log.info(f"{log_identifier} Getting current weather for: {location}")
    
    if not tool_context:
        return {
            "status": "error",
            "message": "Tool context is required for weather operations"
        }
    
    try:
        # Get weather service from agent state
        host_component = getattr(tool_context._invocation_context, "agent", None)
        if host_component:
            host_component = getattr(host_component, "host_component", None)
        
        if not host_component:
            return {
                "status": "error",
                "message": "Could not access agent host component"
            }
        
        weather_service = host_component.get_agent_specific_state("weather_service")
        if not weather_service:
            return {
                "status": "error",
                "message": "Weather service not initialized"
            }
        
        # Fetch weather data
        weather_data = await weather_service.get_current_weather(location, units)
        
        # Create human-readable summary
        summary = _create_weather_summary(weather_data)
        
        result = {
            "status": "success",
            "location": weather_data["location"],
            "summary": summary,
            "data": weather_data
        }
        
        # Save to artifact if requested
        if save_to_file:
            artifact_result = await _save_weather_artifact(
                weather_data, f"current_weather_{location}", tool_context
            )
            result["artifact"] = artifact_result
        
        log.info(f"{log_identifier} Successfully retrieved weather for {location}")
        return result
    
    except ValueError as e:
        log.warning(f"{log_identifier} Invalid location: {e}")
        return {
            "status": "error",
            "message": f"Location error: {str(e)}"
        }
    except Exception as e:
        log.error(f"{log_identifier} Error getting weather: {e}")
        return {
            "status": "error",
            "message": f"Weather service error: {str(e)}"
        }


async def get_weather_forecast(
    location: str,
    days: int = 5,
    units: str = "metric",
    save_to_file: bool = False,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Get weather forecast for a specified location.
    
    Args:
        location: City name, state, and country
        days: Number of days for forecast (1-5)
        units: Temperature units
        save_to_file: Whether to save the forecast as an artifact
    
    Returns:
        Dictionary containing weather forecast information
    """
    log_identifier = "[GetWeatherForecast]"
    log.info(f"{log_identifier} Getting {days}-day forecast for: {location}")
    
    if not tool_context:
        return {
            "status": "error",
            "message": "Tool context is required for weather operations"
        }
    
    # Validate days parameter
    if not 1 <= days <= 5:
        return {
            "status": "error",
            "message": "Days must be between 1 and 5"
        }
    
    try:
        # Get weather service from agent state
        host_component = getattr(tool_context._invocation_context, "agent", None)
        if host_component:
            host_component = getattr(host_component, "host_component", None)
        
        if not host_component:
            return {
                "status": "error",
                "message": "Could not access agent host component"
            }
        
        weather_service = host_component.get_agent_specific_state("weather_service")
        if not weather_service:
            return {
                "status": "error",
                "message": "Weather service not initialized"
            }
        
        # Fetch forecast data
        forecast_data = await weather_service.get_weather_forecast(location, days, units)
        
        # Create human-readable summary
        summary = _create_forecast_summary(forecast_data)
        
        result = {
            "status": "success",
            "location": forecast_data["location"],
            "summary": summary,
            "data": forecast_data
        }
        
        # Save to artifact if requested
        if save_to_file:
            artifact_result = await _save_weather_artifact(
                forecast_data, f"forecast_{location}_{days}day", tool_context
            )
            result["artifact"] = artifact_result
        
        log.info(f"{log_identifier} Successfully retrieved forecast for {location}")
        return result
    
    except ValueError as e:
        log.warning(f"{log_identifier} Invalid location: {e}")
        return {
            "status": "error",
            "message": f"Location error: {str(e)}"
        }
    except Exception as e:
        log.error(f"{log_identifier} Error getting forecast: {e}")
        return {
            "status": "error",
            "message": f"Weather service error: {str(e)}"
        }


def _create_weather_summary(weather_data: Dict[str, Any]) -> str:
    """Create a human-readable weather summary."""
    temp_unit = "°C"  # Assuming metric units for summary
    
    summary = f"Current weather in {weather_data['location']}:\n"
    summary += f"• Temperature: {weather_data['temperature']}{temp_unit} (feels like {weather_data['feels_like']}{temp_unit})\n"
    summary += f"• Conditions: {weather_data['description']}\n"
    summary += f"• Humidity: {weather_data['humidity']}%\n"
    summary += f"• Wind: {weather_data['wind_speed']} m/s\n"
    summary += f"• Visibility: {weather_data['visibility']} km"
    
    return summary


def _create_forecast_summary(forecast_data: Dict[str, Any]) -> str:
    """Create a human-readable forecast summary."""
    summary = f"Weather forecast for {forecast_data['location']}:\n\n"
    
    for forecast in forecast_data['forecasts']:
        date = datetime.fromisoformat(forecast['date']).strftime('%A, %B %d')
        summary += f"• {date}: {forecast['description']}\n"
        summary += f"  High: {forecast['temperature_max']:.1f}°C, Low: {forecast['temperature_min']:.1f}°C\n"
        if forecast['precipitation_probability'] > 0:
            summary += f"  Precipitation: {forecast['precipitation_probability']:.0f}% chance\n"
        summary += "\n"
    
    return summary.strip()


async def _save_weather_artifact(
    weather_data: Dict[str, Any],
    filename_base: str,
    tool_context: ToolContext
) -> Dict[str, Any]:
    """Save weather data as an artifact."""
    try:
        # Prepare content
        content = json.dumps(weather_data, indent=2, default=str)
        timestamp = datetime.now(timezone.utc)
        filename = f"{filename_base}_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        
        # Save artifact
        artifact_service = tool_context._invocation_context.artifact_service
        result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=tool_context._invocation_context.app_name,
            user_id=tool_context._invocation_context.user_id,
            session_id=tool_context._invocation_context.session.id,
            filename=filename,
            content_bytes=content.encode('utf-8'),
            mime_type="application/json",
            metadata_dict={
                "description": "Weather data report",
                "source": "Weather Agent"
            },
            timestamp=timestamp
        )
        
        return {
            "filename": filename,
            "status": result.get("status", "success")
        }
    
    except Exception as e:
        log.error(f"[WeatherArtifact] Error saving artifact: {e}")
        return {
            "status": "error",
            "message": f"Failed to save artifact: {str(e)}"
        }
```

## Step 4: Lifecycle Functions

Create the lifecycle management:

**`src/weather_agent/lifecycle.py`:**

```python
"""
Lifecycle functions for the Weather Agent.
"""

from typing import Any
import asyncio
from pydantic import BaseModel, Field, SecretStr
from solace_ai_connector.common.log import log
from .services.weather_service import WeatherService


class WeatherAgentInitConfig(BaseModel):
    """
    Configuration model for Weather Agent initialization.
    """
    api_key: SecretStr = Field(description="OpenWeatherMap API key")
    base_url: str = Field(
        default="https://api.openweathermap.org/data/2.5",
        description="Weather API base URL"
    )
    startup_message: str = Field(
        default="Weather Agent is ready to provide weather information!",
        description="Message to log on startup"
    )


def initialize_weather_agent(host_component: Any, init_config: WeatherAgentInitConfig):
    """
    Initialize the Weather Agent with weather service.
    
    Args:
        host_component: The agent host component
        init_config: Validated initialization configuration
    """
    log_identifier = f"[{host_component.agent_name}:init]"
    log.info(f"{log_identifier} Starting Weather Agent initialization...")
    
    try:
        # Initialize weather service
        weather_service = WeatherService(
            api_key=init_config.api_key.get_secret_value(),
            base_url=init_config.base_url
        )
        
        # Store service in agent state
        host_component.set_agent_specific_state("weather_service", weather_service)
        
        # Log startup message
        log.info(f"{log_identifier} {init_config.startup_message}")
        
        # Store initialization metadata
        host_component.set_agent_specific_state("initialized_at", "2024-01-01T00:00:00Z")
        host_component.set_agent_specific_state("weather_requests_count", 0)
        
        log.info(f"{log_identifier} Weather Agent initialization completed successfully")
    
    except Exception as e:
        log.error(f"{log_identifier} Failed to initialize Weather Agent: {e}")
        raise


def cleanup_weather_agent(host_component: Any):
    """
    Clean up Weather Agent resources.
    
    Args:
        host_component: The agent host component
    """
    log_identifier = f"[{host_component.agent_name}:cleanup]"
    log.info(f"{log_identifier} Starting Weather Agent cleanup...")

    async def cleanup_async(host_component: Any):
        try:
            # Get and close weather service
            weather_service = host_component.get_agent_specific_state("weather_service")
            if weather_service:
                await weather_service.close()
                log.info(f"{log_identifier} Weather service closed successfully")
            
            # Log final statistics
            request_count = host_component.get_agent_specific_state("weather_requests_count", 0)
            log.info(f"{log_identifier} Agent processed {request_count} weather requests during its lifetime")
            
            log.info(f"{log_identifier} Weather Agent cleanup completed")
        
        except Exception as e:
            log.error(f"{log_identifier} Error during cleanup: {e}")
    
    # run cleanup in the event loop
    loop = asyncio.get_event_loop()
    loop.run_until_complete(cleanup_async(host_component))
    log.info(f"{log_identifier} Weather Agent cleanup completed successfully")
```

## Step 5: Agent Configuration

Create the comprehensive YAML configuration:

```yaml
# Weather Agent Configuration
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: weather-agent.log

!include ../shared_config.yaml

apps:
  - name: weather-agent
    # Broker configuration
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: "${NAMESPACE}"
      agent_name: "WeatherAgent"
      display_name: "Weather Information Agent"
      supports_streaming: true
      
      # LLM model configuration
      model: *general_model
      
      # Agent instructions
      instruction: |
        You are a professional weather agent that provides accurate, up-to-date weather information.
        
        Your capabilities include:
        1. Getting current weather conditions for any location worldwide
        2. Providing detailed weather forecasts up to 5 days
        3. Saving weather reports as files for future reference
        
        Guidelines:
        - Always specify the location clearly when providing weather information
        - Include relevant details like temperature, conditions, humidity, and wind
        - Offer to save weather reports when providing detailed information
        - Be helpful in suggesting appropriate clothing or activities based on weather
        - If a location is ambiguous, ask for clarification (city, state/province, country)
        
        When users ask about weather, use the appropriate tools to fetch real-time data.
        Present information in a clear, organized manner that's easy to understand.
      
      # Lifecycle functions
      agent_init_function:
        module: "src.weather_agent.lifecycle"
        name: "initialize_weather_agent"
        base_path: .
        config:
          api_key: ${OPENWEATHER_API_KEY}
          base_url: "https://api.openweathermap.org/data/2.5"
          startup_message: "Weather Agent is ready to provide weather information!"
      
      agent_cleanup_function:
        module: "src.weather_agent.lifecycle"
        base_path: .
        name: "cleanup_weather_agent"
      
      # Tools configuration
      tools:
        # Current weather tool
        - tool_type: python
          component_module: "src.weather_agent.tools"
          component_base_path: .
          function_name: "get_current_weather"
          tool_description: "Get current weather conditions for a specified location"
        
        # Weather forecast tool
        - tool_type: python
          component_module: "src.weather_agent.tools"
          component_base_path: .
          function_name: "get_weather_forecast"
          tool_description: "Get weather forecast for up to 5 days for a specified location"
        
        # Built-in artifact tools for file operations
        - tool_type: builtin-group
          group_name: "artifact_management"
    
      session_service: *default_session_service
      artifact_service: *default_artifact_service

      artifact_handling_mode: "reference"
      enable_embed_resolution: true
      enable_artifact_content_instruction: true
      # Agent card
      agent_card:
        description: "Professional weather agent providing current conditions, forecasts, and weather comparisons"
        defaultInputModes: ["text"]
        defaultOutputModes: ["text", "file"]
        skills:
          - id: "get_current_weather"
            name: "Get Current Weather"
            description: "Retrieve current weather conditions for any location worldwide"
          - id: "get_weather_forecast"
            name: "Get Weather Forecast"
            description: "Provide detailed weather forecasts up to 5 days ahead"
      
      agent_card_publishing:
        interval_seconds: 30

      agent_discovery:
        enabled: false

      inter_agent_communication:
        allow_list: []
        request_timeout_seconds: 30
```

For more details on agent cards, see the [Agent Card Concepts](../../components/agents.md#agent-card) documentation.

## Step 6: Environment Setup

Before running your weather agent, you'll need to:

1. **Get an OpenWeatherMap API key**:
   - Sign up at [OpenWeatherMap](https://openweathermap.org/api)
   - Get your free API key

2. **Set environment variables**:
   ```bash
   export OPENWEATHER_API_KEY="your_api_key_here"
   # Other environment variables as needed
   ```

## Step 7: Running the Agent

To start the agent, it is preferred to build the plugin and then install it with your agent name. But for debugging or isolated development testing, you can run your agent from the `src` directory directly using the Agent Mesh CLI.

Start your weather agent for development purposes run:

```bash
sam run
```

- To solely run the agent, use `sam run configs/agents/weather_agent.yaml`

## Step 8: Testing the Weather Agent

You can test your weather agent with these example requests:

**Current Weather:**
> "What's the current weather in New York City?"

**Weather Forecast:**
> "Can you give me a 5-day forecast for London, UK and save it to a file?"

**Weather with File Save:**
> "Get the current weather for Tokyo, Japan and save the report"

## Key Features Demonstrated

### 1. External API Integration
- Proper HTTP session management
- Error handling for network issues
- API response transformation

### 2. Resource Management
- Lifecycle functions for initialization and cleanup
- Shared service instances across tool calls
- Proper resource disposal

### 3. Configuration Management
- Pydantic models for type-safe configuration
- Environment variable integration
- Flexible tool configuration

### 4. Error Handling
- Comprehensive exception handling
- User-friendly error messages
- Logging for debugging

### 5. Artifact Management
- Saving structured data as files
- Metadata enrichment
- File format handling
