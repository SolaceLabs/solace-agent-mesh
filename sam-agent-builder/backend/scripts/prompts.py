NUMBER_OF_TEST_CASES_PER_ACTION = 1


def create_agent_prompt(agent_name, agent_description):
    return f"""
You are tasked with creating a new agent named "{agent_name}" for an AI system. This agent will be described as: "{agent_description}".

Your job is to develop this agent by:

1. Refining the agent description to be clear, concise, and informative for the system. The description should explain the agent's purpose, and capabilities.

2. Creating a list of actions this agent should be able to perform. Try to limit the amount of actions to the core functionalities. Usually agents contain 1 to 3 core actions. Each action should:
   - Be named in PascalCase format (e.g., GetUserData, ProcessPayment)
   - Directly relate to the agent's core functionality
   - Represent a discrete, meaningful operation

3. For each action, provide:
   - A detailed description explaining what the action does
   - Required parameters with their data types and purpose, do not include double quotes in descriptions
   - Expected output format and content

4. Ensure the actions collectively cover the full range of functionality needed for the agent to fulfill its purpose.

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
