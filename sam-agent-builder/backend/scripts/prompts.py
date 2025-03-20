NUMBER_OF_TEST_CASES_PER_ACTION = 1
EXAMPLES = """
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
            {
                "name": "sample_action",
                "prompt_directive": ("detailed description of the action. " "examples, chain of thought, etc." "details for parameters"),
                "params": [
                    {
                        "name": "sampleParam",
                        "desc": "Description of the parameter",
                        "type": "type of parameter (string, int, etc.)",
                    }
                ],
                "required_scopes": ["test:sample_action:read"],
            },
            **kwargs,
        )
    def invoke(self, params, meta={}) -> ActionResponse:
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
            {
                "name": "city_to_coordinates",
                "prompt_directive": (
                    "Convert a city name to its geographic coordinates. "
                    "If multiple matches are found, all possibilities will be returned."
                ),
                "params": [
                    {
                        "name": "city",
                        "desc": "Location to look up. Can be a city name (e.g., 'Paris'), city and country (e.g., 'Paris, France'), or full address. More specific inputs will return more precise results.",
                        "type": "string",
                        "required": True,
                    }
                ],
                "required_scopes": ["<agent_name>:city_to_coordinates:execute"],
            },
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
                result = {
                    "latitude": loc.latitude,
                    "longitude": loc.longitude,
                    "display_name": loc.display_name
                }
                if loc.country:
                    result["country"] = loc.country
                if loc.state:
                    result["state"] = loc.state
                if loc.city:
                    result["city"] = loc.city
                results.append(result)
            if len(results) == 1:
                message = f"Found coordinates for {city}:\\n\\n{yaml.dump(results)}"
            else:
                message = f"Found {len(results)} possible matches for {city}:\\n\\n{yaml.dump(results)}"
            return ActionResponse(message=message)
        except Exception as e:
            return ActionResponse(
                message=f"Error looking up coordinates: {str(e)}",
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
            {
                "name": "sentiment_analysis",
                "prompt_directive": "Analyze the sentiment of the message and return an analysis indicating whether it's positive, negative, or neutral.",
                "params": [
                    {
                        "name": "message",
                        "desc": "The message to analyze",
                        "type": "string",
                    }
                ],
                "required_scopes": ["message_analyzer:sentiment_analysis:execute"],
            },
            **kwargs,
        )
    def invoke(self, params, meta={}) -> ActionResponse:
        msg = params.get("message")
        log.debug("Analyzing the message: %s", msg)
        return self.analyze_message(msg)
    def analyze_message(self, message) -> ActionResponse:
        agent = self.get_agent()
        user_msg = f"<message>{message}</message>"
        message = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_msg,
            },
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
"""

def create_agent_prompt(
    agent_name, agent_description, is_api_required, api_description
):
    return f"""
You are tasked with creating a new agent named "{agent_name}" for an AI system. This agent will be described as: "{agent_description}".

Your job is to develop this agent by:

1. Refining the agent description to be clear, concise, and informative for the system. The description should explain the agent's purpose, and capabilities.
Do not use any quotation marks in the description.

2. Creating a list of actions this agent should be able to perform. The actions are what is exposed to the user, 
as such they must only be operations that a user would ask for, if there are steps required to do the action
this would all the part of the same action with helpers so not two seperate actions
internal helper functions should not be an individual action. CAREFULLY CONSIDER IF THE ACTION IS SOMETHING THE USER WOULD ASK FOR OR IS IT SOMETHING 
THAT IS REQUIRED TO DO THE ACTION.
 Try to limit the amount of actions to the core functionalities. 
 Usually agents contain 1 to 3 core actions. Each action should:
   - Be named in PascalCase format (e.g., GetUserData, ProcessPayment)
   - Directly relate to the agent's core functionality that will be exposed to the user
   - Represent a discrete, meaningful operation

3. For each action, provide:
   - A detailed description explaining what the action does
   - Required parameters with their data types and purpose, do not include double quotes in descriptions
   - Expected output format and content

4. Ensure the actions collectively cover the full range of functionality needed for the agent to fulfill its purpose.

5.If an API is required for the agent to function, these are 
the details passed in by the user. If the user passes
in API details then be sure to model the actions based on the part of the API that was passed in or asked for.
Should an API be used: {is_api_required}
API Details: {api_description}
Format your response as an XML document with the following structure:

<agent>
  <name>{agent_name}</name>
  <description>Your refined description here</description>
  
  <actions>
    <action>
      <name>ActionName1</name>
      <description>Detailed explanation of what the action does</description>
      <parameters>
        <parameter>
          <name>param1</name>
          <type>string/number/boolean/etc</type>
          <description>Description of this parameter</description>
        </parameter>
        <parameter>
          <name>param2</name>
          <type>string/number/boolean/etc</type>
          <description>Description of this parameter</description>
        </parameter>
      </parameters>
      <returns>Description of what the action returns</returns>
    </action>
    
    <action>
      <name>ActionName2</name>
      <description>Detailed explanation of what the action does</description>
      <parameters>
        <parameter>
          <name>param1</name>
          <type>string/number/boolean/etc</type>
          <description>Description of this parameter</description>
        </parameter>
      </parameters>
      <returns>Description of what the action returns</returns>
    </action>
  </actions>
</agent>
"""


def create_test_cases_prompt(agent_name, agent_description, actions):
    prompt = f"""
# Agent Test Case Generator

## Agent Information
- Agent Name: {agent_name}
- Agent Description: {agent_description}

## Available Actions
"""
    for action in actions:
        prompt += f"""
- Action Name: {action["name"]}
- Action Description: {action["description"]}
- Action Expected Output: {action["returns"]}
"""
    prompt += f"""
## Test Case Requirements
1. Create {NUMBER_OF_TEST_CASES_PER_ACTION} test cases for each action in the agent
2. Each test case should:
   - Have a clear, descriptive title
   - Include a realistic user query that would trigger the action
   - Describe the expected output/response
   - The expected output should be not be overly detailed, it should simply not return any issues or unrelated responses
3. Test cases should only cover basic functionalities (happy path)

## Output Format
Generate a single XML file containing all test cases with the following structure:
<test_cases>
  <agent name="{agent_name}">
    <action name="[action_name]">
      <test_case id="1" title="[descriptive_title]">
        <user_query>[sample_user_query]</user_query>
        <invoke_action>
          <agent_name>{agent_name}</agent_name>
          <action_name>[action_name]</action_name>
        </invoke_action>
        <expected_output>
          <status>success</status>
          <description>[brief description of expected successful output, should simply not return any issues or unrelated responses]</description>
        </expected_output>
      </test_case>
      <!-- Additional test cases for this action -->
    </action>
    <!-- Additional actions -->
  </agent>
</test_cases>

## Example XML Structure
Here's an example of what the output should look like:
<test_cases>
  <agent name="weather_agent">
    <action name="get_weather">
      <test_case id="1" title="Basic City Weather Query">
        <user_query>What's the weather like in Seattle right now?</user_query>
        <invoke_action>
          <agent_name>weather_agent</agent_name>
          <action_name>get_weather</action_name>
        </invoke_action>
        <expected_output>
          <status>success</status>
          <description>Current temperature or weather conditions for Seattle.</description>
        </expected_output>
      </test_case>
    </action>
  </agent>
</test_cases>
"""

    return prompt


def create_action_file_correcter_prompt(
    action_file_content, error_message, example_action_files=EXAMPLES
):
    return f"""
# Code Error Correction Assistant

## Context
You are an expert code debugging assistant. You've been provided with:
1. A file containing code with an error
2. The error message produced when running this code
3. Example files showing correct implementations

## Your Task
Analyze the code and error message, then provide a corrected version of the file that resolves the error.

## Input
- *File with Error*:
{action_file_content}

- *Error Message*:
{error_message}

- *Example Files*:
{example_action_files}

## Guidelines
1. First, identify the exact location and nature of the error based on the error message.
2. Analyze the problematic code section carefully.
3. Reference the example files to understand the correct implementation patterns.
4. Make minimal changes necessary to fix the error while preserving the original functionality.
5. If multiple solutions are possible, choose the one that best aligns with the coding style in the examples.

## Output Format
Your response should contain ONLY the complete corrected file content, with no additional explanations, comments, or formatting.
The output NEEDS to include the whole file content, not just the corrected part.
"""
