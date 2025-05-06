import subprocess
import shlex
from flask import Flask, jsonify, request, abort
import re
from pathlib import Path
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

app = Flask(__name__)
CONFIGS_DIR = Path("configs/agents")
CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
ENV_VAR_REGEX = re.compile(r"\$\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:,\s*(.*?))?\s*\}")

def _get_backend_agent_definitions():
    return {
        "agents": [
            {
                "id": "sam-bedrock-agent",
                "plugin_agent_name" : "bedrock_agent",
                "name": "Bedrock Agent",
                "description": "Imports Amazon Bedrock agents/flows as actions.",
                "install_command": "sam plugin add sam-bedrock-agent --pip -u git+https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=sam-bedrock-agent"
            },
            {
                "id": "sam_geo_information",
                "plugin_agent_name" : "geo_information",
                "name": "Geographic Information Agent",
                "description": "Provides location lookup, timezone, and weather information services.",
                "install_command": "sam plugin add sam_geo_information --pip -u git+https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=sam-geo-information"
            },
            {
                "id": "sam_mcp_server",
                "plugin_agent_name" : "mcp_server",
                "name": "MCP Server Client Agent",
                "description": "Connects to external MCP servers (like server-filesystem) to use their tools/resources.",
                "install_command": "sam plugin add sam_mcp_server --pip -u git+https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=sam-mcp-server"
            },
            {
                "id": "sam_mermaid",
                "plugin_agent_name" : "mermaid",
                "name": "Mermaid Diagram Agent",
                "description": "Generates visualizations using Mermaid.js.",
                "install_command": "sam plugin add sam_mermaid --pip -u git+https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=sam-mermaid"
            },
            {
                "id": "sam_mongodb",
                "plugin_agent_name" : "mongodb",
                "name": "MongoDB Agent",
                "description": "Performs complex MongoDB queries based on natural language.",
                "install_command": "sam plugin add sam_mongodb --pip -u git+https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=sam-mongodb"
            },
            {
                "id": "sam_sql_database",
                "plugin_agent_name" : "sql_database",
                "name": "SQL Database Agent",
                "description": "Provides SQL query capabilities with natural language. Supports MySQL, PostgreSQL, SQLite.",
                "install_command": "sam plugin add sam_sql_database --pip -u git+https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=sam-sql-database"
            },
             {
                "id": "solace-event-mesh",
                "plugin_agent_name" : "solace_event_mesh",
                "name": "Solace Event Mesh Agent",
                "description": "Sends requests to topics on the Solace event mesh and receives responses.",
                "install_command": "sam plugin add solace-event-mesh --pip -u git+https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=solace-event-mesh"
            }
        ]
    }

def _get_agent_config_path(agent_name: str) -> Path:
    if '/' in agent_name or '\\' in agent_name or '..' in agent_name:
        abort(400, description="Invalid agent name format.")
    return CONFIGS_DIR / f"{agent_name}.yaml"

def _find_action_processor_config(yaml_data) -> CommentedMap | None:
    if not isinstance(yaml_data, dict) or 'flows' not in yaml_data: return None
    for flow in yaml_data.get('flows', []):
        if not isinstance(flow, dict) or 'components' not in flow: continue
        for component in flow.get('components', []):
            if isinstance(component, dict) and component.get('component_name') == 'action_request_processor':
                if isinstance(component.get('component_config'), CommentedMap):
                     return component['component_config']
                else:
                     app.logger.warning(f"Found 'action_request_processor' but 'component_config' is not a map/dict.")
                     return None
    return None

def _parse_env_placeholder(value) -> dict:
    if not isinstance(value, str): return {"is_env": False, "value": value}
    match = ENV_VAR_REGEX.fullmatch(value)
    if match:
        var_name = match.group(1)
        default_value_str = match.group(2)
        default_value = default_value_str if default_value_str is not None else None
        return {"is_env": True, "var_name": var_name, "default_value": default_value}
    else:
        return {"is_env": False, "value": value}

def _convert_ruamel_to_plain(data):
    if isinstance(data, CommentedMap): return {k: _convert_ruamel_to_plain(v) for k, v in data.items()}
    if isinstance(data, CommentedSeq): return [_convert_ruamel_to_plain(item) for item in data]
    return data

def _convert_plain_to_ruamel(data):
    """
    Recursively converts plain Python data structures (dict, list, scalars)
    into their ruamel.yaml equivalents (CommentedMap, CommentedSeq, scalars).

    This is essential for preserving key order and comments when updating
    a YAML structure loaded with ruamel.yaml(typ='rt') and then dumping it.

    Args:
        data: The plain Python data (often originating from JSON parsing).
              Can be a dict, list, str, int, float, bool, or None.

    Returns:
        The equivalent data structure using ruamel.yaml types where appropriate
        (CommentedMap for dicts, CommentedSeq for lists), or the original
        scalar value.
    """
    #dicts
    if isinstance(data, dict):
        # Create a CommentedMap to preserve key order from the input dict.
        ruamel_map = CommentedMap()
        for key, value in data.items():
            # Recursively convert the value before adding it to the map.
            ruamel_map[key] = _convert_plain_to_ruamel(value)
        return ruamel_map

    #Lists
    elif isinstance(data, list):
        # Create a CommentedSeq
        ruamel_sequence = CommentedSeq(
            [_convert_plain_to_ruamel(item) for item in data]
        )
        return ruamel_sequence

    #Scalar values (Base Case)
    else:
        return data

#Recursive Schema Inference Helper 
def _infer_schema_recursive(data):
    """Recursively infers schema for dicts, lists, or scalars, including key order for dicts."""
    if isinstance(data, CommentedMap):
         # Add key_order list, used to preserve order of object keys
        schema = {"type": "dict", "properties": {}, "key_order": []}
        for key, value in data.items():
            schema["key_order"].append(key)
            schema["properties"][key] = _infer_schema_recursive(value)
        return schema
    elif isinstance(data, CommentedSeq):
        schema = {"type": "list", "item_schema": None}
        if data:
            schema["item_schema"] = _infer_schema_recursive(data[0])
        else:
            # Default for empty lists
            schema["item_schema"] = {"type": "string"}
        return schema
    elif isinstance(data, bool):
        return {"type": "boolean"}
    elif isinstance(data, (int, float)):
        return {"type": "number"}
    elif data is None:
        return {"type": "string", "nullable": True}
    else: # Default to string
        return {"type": "string"}

@app.route('/api/agents/config', methods=['GET'])
def get_agent_configs_for_frontend():
    agent_defs = _get_backend_agent_definitions()
    return jsonify(agent_defs)

@app.route('/api/agents/install', methods=['POST'])
def install_agent():
    data = request.json
    agent_id_from_request = data.get('agent_id')
    agent_name_from_request = data.get('agent_name')
    if not agent_id_from_request:
        return jsonify({"status": "error", "message": "agent_id is required"}), 400
    if not agent_name_from_request:
        return jsonify({"status": "error", "message": "agent_name is required to create the agent instance"}), 400
    backend_definitions = _get_backend_agent_definitions()
    agent_to_install = next((agent for agent in backend_definitions['agents']
                             if agent['id'] == agent_id_from_request), None)
    if not agent_to_install:
         return jsonify({"status": "error", "message": f"Agent definition not found for ID: {agent_id_from_request}"}), 404

    install_command = agent_to_install.get('install_command')
    plugin_agent_name_from_backend = agent_to_install.get('plugin_agent_name')

    if not install_command:
        return jsonify({"status": "error", "message": f"No install command defined for agent ID: {agent_id_from_request}"}), 400
    if not plugin_agent_name_from_backend:
         return jsonify({"status": "error", "message": f"No plugin_agent_name defined for agent ID: {agent_id_from_request}"}), 400

    print(f"Attempting to install agent plugin: ID '{agent_id_from_request}' (User-friendly name: '{agent_to_install.get('name', 'N/A')}')")
    print(f"Executing backend-defined command: '{install_command}'")

    try:
        result = subprocess.run(
            shlex.split(install_command),
            capture_output=True,
            text=True,
            check=False,
            shell=False 
        )
        output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        print(output) 
        if result.returncode == 0:
            print(f"Plugin installation successful for ID '{agent_id_from_request}'.")
            try:
                from solace_agent_mesh.cli.commands.add.copy_from_plugin import copy_from_plugin
                print(f"Attempting to create agent instance '{agent_name_from_request}' "
                      f"using plugin template '{plugin_agent_name_from_backend}'...")

                plugin_source = f"{agent_id_from_request}:{plugin_agent_name_from_backend}"
                target_type = "agents"

                copy_from_plugin(
                    agent_name_from_request,
                    plugin_source,
                    target_type
                 )
                print(f"Successfully created agent instance '{agent_name_from_request}' from plugin '{plugin_agent_name_from_backend}'.")
                return jsonify({
                    "status": "success",
                    "message": f"Agent plugin '{agent_to_install.get('name', agent_id_from_request)}' installed and agent instance '{agent_name_from_request}' created successfully.",
                    "output": output
                })
            except ImportError as ie:
                 error_msg = f"Failed to import 'copy_from_plugin'. Ensure 'solace_agent_mesh' is installed and accessible in the backend environment's Python path. Error: {ie}"
                 print(error_msg)
                 return jsonify({"status": "error", "message": error_msg, "output": output}), 500
            except Exception as copy_e:
                 error_msg = f"Plugin installation command succeeded, but failed to create agent instance '{agent_name_from_request}' from plugin template '{plugin_agent_name_from_backend}': {str(copy_e)}"
                 print(error_msg)
                 return jsonify({"status": "error", "message": error_msg, "output": output}), 500
        else:
            print(f"Plugin installation failed for ID '{agent_id_from_request}'. Return code: {result.returncode}")
            return jsonify({
                "status": "error",
                "message": f"Plugin installation command for '{agent_to_install.get('name', agent_id_from_request)}' (ID: {agent_id_from_request}) failed with return code {result.returncode}.",
                "output": output
             }), 500
    except FileNotFoundError as fnf_e:
        error_msg = f"Error executing install command: '{install_command}'. The command or its executable ('sam') might not be found in the system's PATH or the backend environment. Details: {str(fnf_e)}"
        print(error_msg)
        return jsonify({"status": "error", "message": error_msg, "output": ''}), 500
    except Exception as e:
        error_msg = f"An unexpected error occurred during plugin installation for ID '{agent_id_from_request}': {str(e)}"
        print(error_msg)
        output_on_error = getattr(e, 'output', '')
        if not output_on_error and hasattr(e, 'stdout'): output_on_error += f"STDOUT:\n{getattr(e, 'stdout', '')}\n"
        if not output_on_error and hasattr(e, 'stderr'): output_on_error += f"STDERR:\n{getattr(e, 'stderr', '')}"
        return jsonify({"status": "error", "message": error_msg, "output": output_on_error}), 500


@app.route('/api/agents/configure/<string:agent_name>', methods=['GET'])
def get_agent_configuration(agent_name):
    """Gets the configurable parameters for a specific agent instance, including nested schema."""
    app.logger.info(f"Fetching configuration for agent: {agent_name}")
    config_path = _get_agent_config_path(agent_name)
    if not config_path.is_file():
        app.logger.warning(f"Config file not found for agent '{agent_name}' at {config_path}")
        return jsonify({"status": "error", "message": "Agent configuration file not found."}), 404

    yaml = YAML(typ='rt')
    yaml.preserve_quotes = True
    try:
        with open(config_path, 'r', encoding='utf-8') as f: # Specify encoding
            data = yaml.load(f)
    except Exception as e:
        app.logger.error(f"Error reading or parsing YAML file {config_path}: {e}")
        return jsonify({"status": "error", "message": f"Failed to read or parse configuration file: {e}"}), 500

    target_config = _find_action_processor_config(data)
    if target_config is None:
        app.logger.warning(f"Could not find 'action_request_processor.component_config' in {config_path}")

        return jsonify({"status": "success", "agent_name": agent_name, "config_params": []})

    configurable_params = []
    try:
        for key, value in target_config.items():
            #TODO: Some config items should be non editable
            param_info = {"name": key, "editable": True} 
            inferred_schema = _infer_schema_recursive(value)

            param_info["schema"] = inferred_schema # Store the full inferred schema

            if inferred_schema.get("type") == "list":
                param_info["type"] = "list"
                param_info["values"] = _convert_ruamel_to_plain(value)
                item_schema_type = inferred_schema.get("item_schema", {}).get("type")
                param_info["item_type"] = "complex" if item_schema_type in ["dict", "list"] else "simple"

            elif inferred_schema.get("type") == "dict":
                param_info["type"] = "dict"
                param_info["value"] = _convert_ruamel_to_plain(value)

            else:
                param_info["type"] = "simple"
                # Handle environment variable placeholders specifically for simple types
                parsed = _parse_env_placeholder(value)
                param_info["current_value_str"] = str(value)
                param_info["is_env_var"] = parsed["is_env"]
                param_info["env_var_name"] = parsed.get("var_name")
                param_info["env_var_default"] = parsed.get("default_value")
                param_info["data_type"] = inferred_schema.get("type", "string")

            configurable_params.append(param_info)

    except Exception as e:
        app.logger.error(f"Error processing configuration for agent '{agent_name}': {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Internal server error processing configuration."}), 500


    return jsonify({
        "status": "success",
        "agent_name": agent_name,
        "config_params": configurable_params
    })

@app.route('/api/agents/configure/<string:agent_name>', methods=['PUT'])
def update_agent_configuration(agent_name):
    """Updates the configuration, preserving structure and comments."""
    app.logger.info(f"Updating configuration for agent: {agent_name}")
    config_path = _get_agent_config_path(agent_name)
    if not config_path.is_file():
        app.logger.warning(f"Config file not found for update: agent '{agent_name}' at {config_path}")
        return jsonify({"status": "error", "message": "Agent configuration file not found."}), 404

    try:
        # Get the raw JSON payload sent by the frontend
        updates = request.get_json()
        if not isinstance(updates, dict):
            raise ValueError("Invalid JSON payload: expected an object.")
    except Exception as e:
        app.logger.error(f"Failed to parse JSON for agent '{agent_name}' update: {e}")
        return jsonify({"status": "error", "message": f"Invalid request body: {e}"}), 400

    yaml = YAML(typ='rt')
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    try:
        # Load the entire existing document to preserve structure and comments
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.load(f)
    except Exception as e:
        app.logger.error(f"Error reading YAML for update {config_path}: {e}")
        return jsonify({"status": "error", "message": f"Failed to read configuration file for update: {e}"}), 500

    target_config = _find_action_processor_config(data)
    if target_config is None:
        app.logger.error(f"Cannot update: 'action_request_processor.component_config' not found in {config_path}")
        return jsonify({"status": "error", "message": "Could not find the main configuration section to update."}), 500

    updated_keys = set()
    skipped_keys = set()
    conversion_errors = {}

    for key, new_plain_value in updates.items():
        if key not in target_config:
            app.logger.warning(f"Skipping update for unknown key '{key}' in agent '{agent_name}' config.")
            skipped_keys.add(key)
            continue

        # Convert the incoming plain python value back to ruamel types recursively
        try:
            ruamel_value = _convert_plain_to_ruamel(new_plain_value)
            target_config[key] = ruamel_value
            updated_keys.add(key)
            app.logger.debug(f"Prepared update for key '{key}' for agent '{agent_name}'")
        except Exception as e:
            app.logger.error(f"Error converting received data for key '{key}' back to ruamel types: {e}", exc_info=True)
            conversion_errors[key] = str(e)

    if conversion_errors:
         return jsonify({
             "status": "error",
             "message": f"Internal error processing update data for keys: {list(conversion_errors.keys())}.",
             "details": conversion_errors
         }), 500

    # Write updated data back to file
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f)
        app.logger.info(f"Successfully updated configuration for agent '{agent_name}'. Updated keys: {updated_keys}. Skipped keys: {skipped_keys}")
        return jsonify({"status": "success", "message": f"Configuration for agent '{agent_name}' updated successfully."})
    except Exception as e:
        app.logger.error(f"Error writing updated YAML to {config_path}: {e}")
        return jsonify({"status": "error", "message": f"Failed to write updated configuration file: {e}"}), 500


def wizard_command():
    print("Starting Flask server for Wizard on http://0.0.0.0:5005...")
    print("Using Werkzeug reloader for development.")
    print("Press Ctrl+C to stop the server.")
    app.run(host='0.0.0.0', port=5005, debug=True, use_reloader=False)
    print("Wizard backend stopped.")

if __name__ == '__main__':
   wizard_command()
