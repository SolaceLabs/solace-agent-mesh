# wizard_command.py
import subprocess
import shlex
import sys
from flask import Flask, jsonify, request
app = Flask(__name__)

def _get_backend_agent_definitions():
    """
    Internal function representing loading agent definitions from a trusted backend source.
    Crucially, this is NOT using data directly from the request beyond the ID.
    """
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

# --- Endpoint for Frontend to get Configs (to display) ---
@app.route('/api/agents/config', methods=['GET'])
def get_agent_configs_for_frontend():
    """ Returns the configuration for available agents for the frontend to display. """
    agent_defs = _get_backend_agent_definitions()
    return jsonify(agent_defs)


@app.route('/api/agents/install', methods=['POST'])
def install_agent():
    """
    Executes the install command for a given agent plugin,
    looking up the command on the BACKEND based on the received agent_id.
    If installation succeeds, it then copies the plugin configuration
    using the agent_name provided in the request and the plugin_agent_name
    defined in the backend configuration.
    """
    data = request.json
    agent_id_from_request = data.get('agent_id')
    agent_name_from_request = data.get('agent_name') # Get the user-provided name for this instance

    if not agent_id_from_request:
        return jsonify({"status": "error", "message": "agent_id is required"}), 400
    if not agent_name_from_request:
        # Make agent_name mandatory if it's needed for copy_from_plugin
        return jsonify({"status": "error", "message": "agent_name is required to create the agent instance"}), 400

    backend_definitions = _get_backend_agent_definitions()
    agent_to_install = next((agent for agent in backend_definitions['agents']
                             if agent['id'] == agent_id_from_request), None)

    install_command_from_backend = agent_to_install.get('install_command')
    plugin_agent_name_from_backend = agent_to_install.get('plugin_agent_name') # <-- Get the plugin name
    print(f"Attempting to install agent plugin: ID '{agent_id_from_request}' (User-friendly name: '{agent_to_install.get('name', 'N/A')}')")
    print(f"Executing backend-defined command: '{install_command_from_backend}'")

    # --- 4. Execute the command ---
    try:
        result = subprocess.run(
            shlex.split(install_command_from_backend), # Use the command defined on backend
            capture_output=True,
            text=True,
            check=False,
            shell=False # Safer
        )
        output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        print(output) # Log output

        if result.returncode == 0:
            print(f"Plugin installation successful for ID '{agent_id_from_request}'.")

            # --- 5. Copy agent configuration from the installed plugin ---
            try:
                from solace_agent_mesh.cli.commands.add.copy_from_plugin import copy_from_plugin

                print(f"Attempting to create agent instance '{agent_name_from_request}' "
                      f"using plugin template '{plugin_agent_name_from_backend}'...")

                copy_from_plugin(
                    agent_name_from_request,
                    f"{agent_id_from_request}:{plugin_agent_name_from_backend}",
                    "agents"
                 )

                print(f"Successfully created agent instance '{agent_name_from_request}' from plugin '{plugin_agent_name_from_backend}'.")
                return jsonify({
                    "status": "success",
                    "message": f"Agent plugin '{agent_to_install.get('name', agent_id_from_request)}' installed and agent instance '{agent_name_from_request}' created successfully.",
                    "output": output
                })
            except ImportError as ie:
                 error_msg = f"Failed to import 'copy_from_plugin'. Ensure 'solace_agent_mesh' is installed and accessible. Error: {ie}"
                 print(error_msg)
                 # Return error, as the agent instance couldn't be created
                 return jsonify({"status": "error", "message": error_msg, "output": output}), 500
            except Exception as copy_e:
                 error_msg = f"Plugin installation command succeeded, but failed to create agent instance '{agent_name_from_request}' from plugin template '{plugin_agent_name_from_backend}': {str(copy_e)}"
                 print(error_msg)
                 # Return error, as the agent instance couldn't be created
                 return jsonify({"status": "error", "message": error_msg, "output": output}), 500
        else:
            print(f"Plugin installation failed for ID '{agent_id_from_request}'. Return code: {result.returncode}")
            return jsonify({
                "status": "error",
                "message": f"Plugin installation command for '{agent_to_install.get('name', agent_id_from_request)}' (ID: {agent_id_from_request}) failed with return code {result.returncode}.",
                "output": output
             }), 500

    except FileNotFoundError as fnf_e:
        error_msg = f"Error executing install command: '{install_command_from_backend}'. The command or its executable might not be found in the system's PATH. Details: {str(fnf_e)}"
        print(error_msg)
        return jsonify({"status": "error", "message": error_msg, "output": ''}), 500
    except Exception as e:
        error_msg = f"An unexpected error occurred during plugin installation for ID '{agent_id_from_request}': {str(e)}"
        print(error_msg)
        # Try to get command output if available even during exception
        output_on_error = getattr(e, 'output', '')
        if not output_on_error and hasattr(e, 'stdout'):
             output_on_error += f"STDOUT:\n{getattr(e, 'stdout', '')}\n"
        if not output_on_error and hasattr(e, 'stderr'):
             output_on_error += f"STDERR:\n{getattr(e, 'stderr', '')}"
        return jsonify({"status": "error", "message": error_msg, "output": output_on_error}), 500

def wizard_command():
    print("Starting Flask server for Wizard on http://0.0.0.0:5005...")
    print("Using Werkzeug reloader for development.")
    print("Press Ctrl+C to stop the server.")

    app.run(host='0.0.0.0', port=5005, debug=True)
    print("Wizard backend stopped.")

if __name__ == '__main__':
   wizard_command()