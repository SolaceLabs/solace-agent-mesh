import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(root_dir)

from common import prompt_llm
from .configs_prompt import get_configs_prompt
from .parser import parse_configs_json

def init_configs(agent_dict, api_key):
    print("Initializing configurations...")
    api_key_required = bool(api_key)
    configs_file_path = os.path.join(root_dir, "configs", "agents", f"{agent_dict['name']}.yaml")
    configs_prompt = get_configs_prompt(agent_dict, api_key_required, configs_file_path)
    configs_raw_content = prompt_llm(configs_prompt)
    # print(f"\nConfigs Raw Content: {configs_raw_content}\n")
    configs_dict = parse_configs_json(configs_raw_content)
    # print(f"\nFile Content: {configs_dict['file_content']}\n")
    # print(f"\nconfigs_added: {configs_dict['configs_added']}\n")
    # print(f"\napi_key_name: {configs_dict['api_key_name']}\n")
    # Overwrite the configs file
    configs_file_path = os.path.join(root_dir, "configs", "agents", f"{agent_dict['name']}.yaml")
    if os.path.exists(configs_file_path):
        with open(configs_file_path, "w") as f:
            f.write(configs_dict["file_content"])
    else:
        print(f"Configs file not found: {configs_file_path}")

    # Update environment variables
    if api_key_required:
        append_env_file(configs_dict["api_key_name"], api_key)

    return configs_dict['configs_added']

def append_env_file(env_var_name, env_var_value):
    print("Appending to .env file...")
    env_file_path = os.path.join(root_dir, ".env")
    
    # Check if the .env file exists
    if not os.path.exists(env_file_path):
        print(f".env file not found: {env_file_path}")
        raise FileNotFoundError(f".env file not found: {env_file_path}")
    
    # Check if env variable already exists
    with open(env_file_path, "r") as f:
        env_content = f.read()
        if "API_KEY" in env_content:
            print("API_KEY already exists in .env file.")
            return
    
    # Append the API_KEY variable to the .env file
    with open(env_file_path, "a") as f:
        f.write(f"\n{env_var_name}={env_var_value}\n")

    print(f"Appended {env_var_name} to .env file.")
    return