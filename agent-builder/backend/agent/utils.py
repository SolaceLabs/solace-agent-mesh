 

def generate_agent_file_content(agent_dict):
    """
    Generate the content of the agent file based on the agent dictionary.
    """
    # Convert agent name to Pascal case
    class_name = ''.join(word.capitalize() for word in agent_dict['name'].split('_')) + "AgentComponent"

    # Import list
    imports = []
    for action in agent_dict['actions']:
        snake_case_action_name = "".join(
            ["_" + c.lower() if c.isupper() else c for c in action['name']]
        ).lstrip("_")
        imports.append(f"from {agent_dict['name']}.actions.{snake_case_action_name} import {action['name']}")

    # Template for the agent file
    agent_file_template = f'''
"""The agent component for the {agent_dict['name']} agent."""

import os
import copy
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from solace_agent_mesh.agents.base_agent_component import (
    agent_info,
    BaseAgentComponent,
)

{chr(10).join(imports)}

info = copy.deepcopy(agent_info)
info["agent_name"] = "{agent_dict['name']}"
info["class_name"] = "{class_name}"
info["description"] = (
    "{agent_dict['description']}"
)

class {class_name}(BaseAgentComponent):
    info = info
    actions = [{", ".join([action['name'] for action in agent_dict['actions']])}]
'''
    return agent_file_template