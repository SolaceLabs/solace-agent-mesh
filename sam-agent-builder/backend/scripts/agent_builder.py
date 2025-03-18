import sys
import os

# Add the project root to the path
solace_agent_mesh = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.append(solace_agent_mesh)

from helpers import make_llm_api_call
from scripts.prompts import create_agent_prompt

def build_agent(agent_name, agent_description):
    #prompt = create_agent_prompt(agent_name, agent_description)
 #   response = make_llm_api_call(prompt)
    #print(response)
    return ""

if __name__ == "__main__":
    build_agent("health-expert", "I want to build an agent that provides health-related information.")