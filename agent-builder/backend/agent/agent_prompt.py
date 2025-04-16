
def get_agent_prompt(agent_data):
    prompt = f"""
You are tasked with creating a new agent named "{agent_data['name']}" for an AI system. This agent will be described as: "{agent_data['description']}".\n"""
    
    # Add agent description
    prompt += DEFAULT_AGENT_DESCRIPTION_PROMPT

    # Add API details if provided
    if agent_data.get("api_key"):
        prompt += f"""
5. The agent requires an API, be sure to model the actions based on the part of the API that was passed in or asked for.
API Details: {agent_data['api_description']}\n"""
        
    # Add a format for the agent
    prompt += DEFAULT_AGENT_RESPONSE_FORMAT_INSTRUCTIONS

    return prompt


DEFAULT_AGENT_DESCRIPTION_PROMPT = """
Your job is to develop this agent by:

1. Refining the agent description to be clear, concise, and informative for the system. The description should explain the agent's purpose, and capabilities.
Do not use any quotation marks in the description.

2. Creating a list of actions this agent should be able to perform. The actions are what is exposed to the user, 
as such they must only be operations that a user would ask for, if there are steps required to do the action
this would all the part of the same action with helpers so not two seperate actions
internal helper functions should not be an individual action. 
CAREFULLY CONSIDER IF THE ACTION IS SOMETHING THE USER WOULD ASK FOR OR IS IT SOMETHING THAT IS REQUIRED TO DO THE ACTION.
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
"""

DEFAULT_AGENT_RESPONSE_FORMAT_INSTRUCTIONS = """
Do not include any other text, symbols or quotes in the response.
Format your response as an XML document with the following structure:

<agent>
  <name>The agent name in snake case (e.g., snake_case, stock_price)</name>
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