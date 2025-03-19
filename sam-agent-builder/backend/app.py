import sys
import os

# Add the project root to the path
solace_agent_mesh = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(solace_agent_mesh)

from flask import Flask, request, jsonify
from solace_agent_mesh.cli.commands.add.agent import add_agent_command
from helpers import (
    make_llm_api_call,
    parse_actions_from_global_context,
    parse_agent_from_global_context,
    add_filenames_to_action_list_and_create,
    parse_config_output,
)
from scripts.prompts import create_agent_prompt, create_test_cases_prompt
from scripts.file_utils import (
    create_agent_component,
    delete_sample_action_file,
    write_agent_file,
)
from build_actions import output_action_file

from build_config import build_config

# from solace_agent_mesh.cli.config import Config

app = Flask(__name__)
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})


@app.route("/api/create-agent", methods=["POST"])
def create_agent():
    """Create a new agent with the provided configuration."""
    data = request.json

    # Extract data from request
    agent_name = data.get("name")
    agent_description = data.get("description")
    api_key = data.get("apiKey")

    # Log the received data for now (would integrate with agent mesh later)
    # print(f"Creating agent: {agent_name}")
    # print(f"Description: {agent_description}")
    print(f"API Key provided: {'Yes' if api_key else 'No'}")
    print(f"API key: {api_key}")

    # Here we would actually create the agent in the agent mesh framework
    # For now, just return a success response

    # Create a default config when not in CLI context
    config = {
        "solace_agent_mesh": {
            "config_directory": os.path.join(os.getcwd(), "configs"),
            "modules_directory": os.path.join(os.getcwd(), "modules"),
        }
    }

    result = add_agent_command(agent_name, config)

    if result == 1:
        return (
            jsonify(
                {"success": False, "message": f"Failed to create agent '{agent_name}'"}
            ),
            500,
        )

    # Prompt LLM to get the agent format in XML
    #prompt is the global contextr
    prompt = create_agent_prompt(agent_name, agent_description)
    response = make_llm_api_call(prompt)

    # Parse XML response to dictionary
    action_dictionary = parse_actions_from_global_context(response)
    agent_dictionary = parse_agent_from_global_context(response)

    # Action(s) to be created
    imports = []
    action_names = []
    for action in action_dictionary:
        action_name = action["name"]
        action_names.append(action_name)
        # Convert action name to snake_case for file naming and action name
        snake_case_action = "".join(
            ["_" + c.lower() if c.isupper() else c for c in action_name]
        ).lstrip("_")
        imports.append(
            f"from {agent_name.replace('-','_')}.actions.{snake_case_action} import {action_name}"
        )

    print(f"agent description: {agent_dictionary}")
    # Create the new agent component
    create_agent_component(
        agent_name=agent_name.replace("-", "_"),
        actions=action_names,
        description=agent_dictionary["description"],
        imports=imports,
    )
    # Delete the sample action file
    delete_sample_action_file(agent_name.replace("-", "_"))

    # Create action files
    add_filenames_to_action_list_and_create(agent_name.replace("-", "_"), action_dictionary)

    #update the config file with any needed configurations
    is_api_key_required = True if api_key else False
    updated_config_file_raw = build_config(agent_name.replace("-", "_"), agent_dictionary, action_dictionary, is_api_key_required )

    updated_config_file_parsed = parse_config_output(updated_config_file_raw)

    print(f"Updated config file: {updated_config_file_parsed}")

    write_agent_file(agent_name.replace("-", "_"), "agent_config", updated_config_file_parsed["file_content"])

    configs_added = updated_config_file_parsed["configs_added"]

    #update action files
    for action in action_dictionary:
        action_name = action["name"]
        action_file_name = action["filename"]
        action_description = action["description"]
        action_return_description = action["returns"]

        updated_action_file_raw = output_action_file(agent_name.replace("-", "_"), action_file_name, action_name, action_description, action_return_description, configs_added)
        updated_action_file_parsed = parse_config_output(updated_action_file_raw)
        write_agent_file(agent_name.replace("-", "_"), "agent_action",updated_action_file_parsed["file_content"] ,action_file_name)


    test_case_prompt = create_test_cases_prompt(
    agent_name.replace("-", "_"), agent_dictionary["description"], action_dictionary
    )
    test_case_response = make_llm_api_call(test_case_prompt)
    # print(f"test_case_response: {test_case_response}")

    return jsonify(
        {
            "success": True,
            "message": f"Agent '{agent_name}' created successfully",
            "agent_id": "sample-agent-id-12345",  # This would be generated by the system
        }
    )


# Add a health check endpoint
@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "API is running"})


# Add a catch-all route to help debug 404s
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path):
    print(f"Received request for path: {path}")
    return (
        jsonify(
            {
                "error": "not_found",
                "message": f"Path '/{path}' not found",
                "available_endpoints": ["/api/create-agent", "/api/health"],
            }
        ),
        404,
    )


if __name__ == "__main__":
    # Run on 0.0.0.0 to make it accessible from other machines/containers
    print("Starting server with CORS enabled for all origins...")
    app.run(host="0.0.0.0", port=5002, debug=True)
