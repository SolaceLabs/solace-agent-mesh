# Solace Agent Mesh - Geographic Information Plugin

A plugin for the Solace Agent Mesh (SAM) that provides comprehensive geographic information services including location lookup, timezone data, and weather information.

## Features

This plugin provides the following tools to be used by a Solace Agent:

-   **`city_to_coordinates`**: Converts a city name to its geographic coordinates (latitude and longitude).
-   **`city_to_timezone`**: Looks up timezone information for a given city, including UTC offset and Daylight Saving Time (DST) status.
-   **`get_weather`**: Retrieves the current weather conditions and an optional multi-day forecast for a specific location.
  
## Installation
To install the SAM Geographic Information plugin, run the following command in your SAM project directory:

```bash
solace-agent-mesh plugin add <your-new-component-name> --plugin sam-geo-information
```
This will create a new component configuration at `configs/plugins/<your-new-component-name-kebab-case>.yaml`.


## Configuration

To use this plugin, you need to configure an agent to use its tools. In your agent's `config.yaml` file, add the following sections:

**Tool Definitions:** In the `tools` list, add entries for each of the geographic information tools you want the agent to use.

    ```yaml
    tools:
      - tool_type: python
        component_module: sam_geo_information
        function_name: city_to_coordinates
        tool_config:
          geocoding_api_key: ${GEOCODING_API_KEY}

      - tool_type: python
        component_module: sam_geo_information
        function_name: city_to_timezone
        tool_config:
          geocoding_api_key: ${GEOCODING_API_KEY}

      - tool_type: python
        component_module: sam_geo_information
        function_name: get_weather
        tool_config:
          geocoding_api_key: ${GEOCODING_API_KEY}
          weather_api_key: ${WEATHER_API_KEY}
    ```

Provide the necessary API keys as environment variables:
```bash
export GEOCODING_API_KEY="your_geocoding_api_key"
export WEATHER_API_KEY="your_weather_api_key"
```

## Usage Example

Once configured, you can interact with an agent using natural language prompts. The agent's LLM will automatically select the appropriate tool based on your request.

**Example Prompts:**

-   *"What are the coordinates of Ottawa?"*
-   *"What is the current time and timezone in Tokyo?"*
-   *"Give me the weather forecast for the next 3 days in London, UK."*

## APIs Used

This plugin utilizes the following external services:

-   **Geocoding:** [geocode.maps.co](https://geocode.maps.co/) - A free geocoding service. Sign up for an API key for higher request volumes.
-   **Weather:** [Open-Meteo](https://open-meteo.com/) - A free weather forecast API for non-commercial use. A commercial license is available.