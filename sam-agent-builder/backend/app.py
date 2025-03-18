
import sys
import os

# Add the project root to the path
solace_agent_mesh = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.append(solace_agent_mesh)

from flask import Flask, request, jsonify, make_response
from solace_agent_mesh.cli.commands.add.agent import add_agent_command
from scripts.agent_builder import build_agent
# from solace_agent_mesh.cli.config import Config

app = Flask(__name__)
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

@app.route('/api/create-agent', methods=['POST'])
def create_agent():
    """Create a new agent with the provided configuration."""
    data = request.json
    
    # Extract data from request
    agent_name = data.get('name')
    agent_description = data.get('description')
    api_key = data.get('apiKey')
    
    # Log the received data for now (would integrate with agent mesh later)
    print(f"Creating agent: {agent_name}")
    print(f"Description: {agent_description}")
    print(f"API Key provided: {'Yes' if api_key else 'No'}")
    print(f"API key: {api_key}")
    
    # Here we would actually create the agent in the agent mesh framework
    # For now, just return a success response

    # Create a default config when not in CLI context
    config = {
        "solace_agent_mesh": {
            "config_directory": os.path.join(os.getcwd(), "config"),
            "modules_directory": os.path.join(os.getcwd(), "src"),
        }
    }

    result = add_agent_command(agent_name, config)

    if result == 1:
        return jsonify({
            "success": False,
            "message": f"Failed to create agent '{agent_name}'"
        }), 500
    
    build_agent(agent_name, agent_description)
    
    return jsonify({
        "success": True,
        "message": f"Agent '{agent_name}' created successfully",
        "agent_id": "sample-agent-id-12345"  # This would be generated by the system
    })

# Add a health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "ok",
        "message": "API is running"
    })

# Add a catch-all route to help debug 404s
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    print(f"Received request for path: {path}")
    return jsonify({
        "error": "not_found",
        "message": f"Path '/{path}' not found",
        "available_endpoints": ["/api/create-agent", "/api/health"]
    }), 404

if __name__ == '__main__':
    # Run on 0.0.0.0 to make it accessible from other machines/containers
    print("Starting server with CORS enabled for all origins...")
    app.run(host='0.0.0.0', port=5002, debug=True)