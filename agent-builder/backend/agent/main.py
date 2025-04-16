import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(root_dir)

from cli.commands.add.agent import add_agent_command

from common import prompt_llm
from .agent_prompt import get_agent_prompt
from .parser import parse_agent_xml
from .utils import generate_agent_file_content

def init_agent(agent_data):
    print("Creating agent...")
    create_agent_template(agent_data['name'])
    return create_agent_file(agent_data)

def create_agent_template(agent_name):
    print("Creating agent template...")
    # Create a default config when not in CLI context
    config = {
        "solace_agent_mesh": {
            "config_directory": os.path.join(root_dir, "configs"),
            "modules_directory": os.path.join(root_dir, "modules"),
        }
    }
    return add_agent_command(agent_name, config)

def create_agent_file(agent_data):
    print("Creating agent file...")
    agent_prompt = get_agent_prompt(agent_data)
    agent_xml = prompt_llm(agent_prompt)
    agent_dict = parse_agent_xml(agent_xml)
    agent_file_content = generate_agent_file_content(agent_dict)

    # Overwrite the agent template file
    agent_file_path = os.path.join(root_dir, "modules", "agents", agent_dict['name'], f"{agent_dict['name']}_agent_component.py")

    if os.path.exists(agent_file_path):
        with open(agent_file_path, "w") as f:
            f.write(agent_file_content)
    else:
        print(f"Agent file not found: {agent_file_path}")
    # Return the agent dictionary
    return agent_dict