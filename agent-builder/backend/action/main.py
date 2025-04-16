import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(root_dir)

from common import prompt_llm
from .action_prompt import get_action_prompt

def init_actions(agent_dict, configs_added, api_description):
    print("Initializing actions...")
    delete_action_template(agent_dict['name'])
    # Create action files
    for action in agent_dict['actions']:
        # Create the action file
        create_action_file(agent_dict['name'], action, configs_added, api_description)
    return

def delete_action_template(agent_name):
    print("Deleting action template...")
    sample_action_file_path = os.path.join(root_dir, "modules", "agents", agent_name, "actions", "sample_action.py")
    if os.path.exists(sample_action_file_path):
        os.remove(sample_action_file_path)
        print(f"Deleted action template file: {sample_action_file_path}")
    else:
        print(f"Action sample file not found: {sample_action_file_path}")
    return

def create_action_file(agent_name, action_dict, configs_added, api_description):
    print("Creating action file...")
    action_prompt = get_action_prompt(agent_name, action_dict, configs_added, api_description)
    action_file_raw_content = prompt_llm(action_prompt)
    action_file_content = parse_action_content(action_file_raw_content)

    # Check the action file path
    snake_case_action_name = "".join(
        ["_" + c.lower() if c.isupper() else c for c in action_dict['name']]
    ).lstrip("_")
    action_file_path = os.path.join(root_dir, "modules", "agents", agent_name, "actions", f"{snake_case_action_name}.py")
    

    # Overwrite the action template file
    with open(action_file_path, "w") as f:
        f.write(action_file_content)
    return

def parse_action_content(action_content):
    print("Parsing action content...")
    # Remove leading and trailing triple backticks and any language identifier
    if action_content.startswith("```"):
        first_newline = action_content.find("\n")
        if first_newline != -1:
            action_content = action_content[first_newline + 1:]
    if action_content.endswith("```"):
        last_newline = action_content.rfind("\n")
        if last_newline != -1:
            action_content = action_content[:last_newline]
    return action_content