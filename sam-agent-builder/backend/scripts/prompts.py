NUMBER_OF_TEST_CASES_PER_ACTION = 1


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
    action_file_content, error_message, example_action_files=None
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
