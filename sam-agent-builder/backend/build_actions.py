#given a file name without the .py extension of an action, this function will overwrite it with code for that action
from helpers import make_llm_api_call, get_agent_file

def output_action_file(agent_name,file_name, action_name, action_description, action_return_description, configs_added):
    action_file = get_agent_file(agent_name,"agent_action" ,file_name)
    SYSTEM_PROMPT = """
    You are an expert Python developer creating action files for the Solace Agent Mesh framework.

    # PURPOSE
    Action files define capabilities that agents can perform. Each action file:
    - Contains a single Action class
    - Defines parameters, behavior, and authorization scopes
    - Provides an implementation of the action's functionality
    - Can use agent configuration via self.get_config() or kwargs.get("config_fn")("config_name")

    # ACTION FILE STRUCTURE
    1. A docstring describing the action
    2. Necessary imports
    3. A class that extends Action and implements:
    - __init__(): Sets up action metadata, parameters, and scopes
    - invoke(): Handles the action request and calls business logic
    - Additional helper methods as needed

    # YOUR TASK
    Create a complete, well-documented action file for the specified action with:
    - Proper imports and class structure
    - Clear docstrings and comments
    - Appropriate error handling
    - Proper parameter validation
    - Sensible return values via ActionResponse

    Most of the boilerplate code will already be provided. You need to fill in the blanks with the action's logic.

    # OUTPUT FORMAT
    Your response must be ONLY a JSON object with a single field called "file_content" containing the complete Python code as a string:
    ```json
    {
    "file_content": "\"\"\"Action description\"\"\"\n\nfrom solace_ai_connector.common.log import log..."
    }" \
    "" \
    "" \
    """

    SYSTEM_PROMPT += f"""
ACTION DETAILS TO BE IMPLEMENTED
File Name: {file_name}
Action Name: {action_name}
Action Description: {action_description}
Expected Return: {action_return_description}
Current action file to be edited: {action_file}
The configs that were added are: {configs_added}

You don't need to use all the configs, only use the ones that are absolutel required or supported

EXAMPLES OF ACTIONS
Here are examples of well-implemented actions to guide your implementation:

Example 1: Sample Action Template
\"\"\"Action description\"\"\"

from solace_ai_connector.common.log import log


from solace_agent_mesh.common.action import Action
from solace_agent_mesh.common.action_response import ActionResponse

# To import from a local file, like this file, use a relative path from the test
# For example, to load this class, use:
#   from test.actions.sample_action import SampleAction


class SampleAction(Action):
    def __init__(self, **kwargs):
        super().__init__(
            {{
                "name": "sample_action",
                "prompt_directive": ("detailed description of the action. " "examples, chain of thought, etc." "details for parameters"),
                "params": [
                    {{
                        "name": "sampleParam",
                        "desc": "Description of the parameter",
                        "type": "type of parameter (string, int, etc.)",
                    }}
                ],
                "required_scopes": ["test:sample_action:read"],
            }},
            **kwargs,
        )

    def invoke(self, params, meta={{}}) -> ActionResponse:
        log.debug("Doing sample action: %s", params["sampleParam"])
        return self.do_action(params["sampleParam"])

    def do_action(self, sample) -> ActionResponse:
        sample += " Action performed"
        return ActionResponse(message=sample)

Example 2: City to Coordinates Action
\"\"\"Action for converting city names to geographic coordinates.\"\"\"

from typing import Dict, Any
import yaml
from solace_agent_mesh.common.action import Action
from solace_agent_mesh.common.action_response import ActionResponse, ErrorInfo

from ..services.geocoding_service import MapsCoGeocodingService


class CityToCoordinates(Action):
    \"\"\"Convert city names to geographic coordinates.\"\"\"

    def __init__(self, **kwargs):
        \"\"\"Initialize the action.\"\"\"
        super().__init__(
            {{
                "name": "city_to_coordinates",
                "prompt_directive": (
                    "Convert a city name to its geographic coordinates. "
                    "If multiple matches are found, all possibilities will be returned."
                ),
                "params": [
                    {{
                        "name": "city",
                        "desc": "Location to look up. Can be a city name (e.g., 'Paris'), city and country (e.g., 'Paris, France'), or full address. More specific inputs will return more precise results.",
                        "type": "string",
                        "required": True,
                    }}
                ],
                "required_scopes": ["<agent_name>:city_to_coordinates:execute"],
            }},
            **kwargs
        )
        geocoding_api_key = kwargs.get("config_fn")("geocoding_api_key")
        self.geocoding_service = MapsCoGeocodingService(api_key=geocoding_api_key)

    def invoke(self, params: Dict[str, Any], meta: Dict[str, Any] = None) -> ActionResponse:
        \"\"\"Execute the city to coordinates conversion.
        
        Args:
            params: Must contain 'city' parameter
            meta: Optional metadata
            
        Returns:
            ActionResponse containing the coordinates or error information
        \"\"\"
        try:
            city = params.get("city")
            if not city:
                raise ValueError("City parameter is required")

            locations = self.geocoding_service.geocode(city)
            
            # Format the results
            results = []
            for loc in locations:
                result = {{
                    "latitude": loc.latitude,
                    "longitude": loc.longitude,
                    "display_name": loc.display_name
                }}
                if loc.country:
                    result["country"] = loc.country
                if loc.state:
                    result["state"] = loc.state
                if loc.city:
                    result["city"] = loc.city
                results.append(result)

            if len(results) == 1:
                message = f"Found coordinates for {{city}}:\\n\\n{{yaml.dump(results)}}"
            else:
                message = f"Found {{len(results)}} possible matches for {{city}}:\\n\\n{{yaml.dump(results)}}"

            return ActionResponse(message=message)

        except Exception as e:
            return ActionResponse(
                message=f"Error looking up coordinates: {{str(e)}}",
                error_info=ErrorInfo(str(e))
            )

Example 3: Sentiment Analysis Action
from typing import Dict, Any
import yaml
from solace_agent_mesh.common.action import Action
from solace_agent_mesh.common.action_response import ActionResponse, ErrorInfo
import json

SYSTEM_PROMPT = (
    "Analyze the sentiment of the message and return whether it's positive, negative, or neutral. "
    "You should only respond with a JSON value with 2 keys: 'sentiment' and 'confidence'. "
    "The sentiment should be one of 'positive', 'negative', or 'neutral'. "
    "The confidence should be a float value between 0 and 1."
)

class SentimentAnalysisAction(Action):
    def __init__(self, **kwargs):
        super().__init__(
            {{
                "name": "sentiment_analysis",
                "prompt_directive": "Analyze the sentiment of the message and return an analysis indicating whether it's positive, negative, or neutral.",
                "params": [
                    {{
                        "name": "message",
                        "desc": "The message to analyze",
                        "type": "string",
                    }}
                ],
                "required_scopes": ["message_analyzer:sentiment_analysis:execute"],
            }},
            **kwargs,
        )

    def invoke(self, params, meta={{}}) -> ActionResponse:
        msg = params.get("message")
        log.debug("Analyzing the message: %s", msg)
        return self.analyze_message(msg)

    def analyze_message(self, message) -> ActionResponse:
        agent = self.get_agent()

        user_msg = f"<message>{{message}}</message>"

        message = [
            {{
                "role": "system",
                "content": SYSTEM_PROMPT,
            }},
            {{
                "role": "user",
                "content": user_msg,
            }},
        ]

        try:
            response = agent.do_llm_service_request(message)
            content = response.get("content")
            analysis = json.loads(content)
            log.debug("Sentiment: %s, Confidence: %s", analysis["sentiment"], analysis["confidence"])
            return ActionResponse(message=content) # Message should be of type string, converting to JSON was just an example
        except Exception as e:
            log.error("Error in sentiment analysis: %s", e)
            return ActionResponse(message="error: Error in sentiment analysis")

HELPFUL TIPS:
Use self.get_config("config_name") to access configurations
Use ActionResponse to return results; it can include:
message: Text response
error_info: Error details via ErrorInfo
files: File attachments
Scope names usually follow the pattern: agent_name:action_name:operation
Use helper methods for complex logic
Access agent methods via self.get_agent()

    # OUTPUT FORMAT
    Your response must be ONLY a JSON object with a single field called "file_content" containing the complete Python code as a string:
    ```json
    {{
    "file_content": "\"\"\"Action description\"\"\"\n\nfrom solace_ai_connector.common.log import log..."
    }}" \
"""
    
    response = make_llm_api_call(SYSTEM_PROMPT)

    return response