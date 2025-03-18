

def create_agent_prompt(agent_name, agent_description):
    return f"""
You are tasked with creating a new agent named "{agent_name}" for an AI system. This agent will be described as: "{agent_description}".

Your job is to develop this agent by:

1. Refining the agent description to be clear, concise, and informative for the system. The description should explain the agent's purpose, capabilities, and appropriate use cases.

2. Creating a comprehensive list of actions this agent should be able to perform. Each action should:
   - Be named in PascalCase format (e.g., GetUserData, ProcessPayment)
   - Directly relate to the agent's core functionality
   - Represent a discrete, meaningful operation

3. For each action, provide:
   - A detailed description explaining what the action does
   - Required parameters with their data types and purpose
   - Expected output format and content
   - Any constraints, limitations, or edge cases to consider
   - Example usage scenarios

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
      <exampleUseCases>
        <useCase>Example use case 1</useCase>
        <useCase>Example use case 2</useCase>
      </exampleUseCases>
      <constraints>Any constraints or limitations to consider</constraints>
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
      <exampleUseCases>
        <useCase>Example use case 1</useCase>
      </exampleUseCases>
      <constraints>Any constraints or limitations to consider</constraints>
    </action>
  </actions>
  
  <implementationConsiderations>Any special considerations for implementing this agent</implementationConsiderations>
</agent>
"""