
from flask import Flask, jsonify, request
from flask_cors import CORS

from agent.main import init_agent
from action.main import init_actions
from configs.main import init_configs

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Endpoint to create an agent
@app.route("/api/create-agent", methods=["POST"])
def create_agent():
    data = request.json
    # Extract data from request
    agent_data = {
        "name": data.get("name"),
        "description": data.get("description"),
        "api_key": data.get("apiKey"),
        "api_description": data.get("apiDescription"),
    }

    # Handle agent creation
    agent_dict = init_agent(agent_data)
    # Update configurations if needed
    configs_added = init_configs(agent_dict, agent_data['api_key'])
    # Handle action(s) creation
    init_actions(agent_dict, configs_added, agent_data['api_description'])
    # Test the agent (optional)

    return jsonify({
        "status": "success",
        "message": f"Agent '{agent_data['name']}' created successfully.",
        "data": {
            "name": agent_data['name'],
            "description": agent_data['description'],
            "apiKey": agent_data['api_key'],
            "apiDescription": agent_data['name'],
        },
    }), 201

# Health endpoint
@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "API is running"})


# All endpoints
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path):
    print(f"Received request for path: {path}")
    return (
        jsonify({
            "error": "not_found",
            "message": f"Path '/{path}' not found",
            "available_endpoints": [
                "/api/create-agent",
                "/api/health",
                "/api/progress/<job_id>/stream",
            ],
        }), 404
    )


if __name__ == "__main__":
    # Run on 0.0.0.0 to make it accessible from other machines/containers
    print("Starting server with CORS enabled for all origins...")
    app.run(host="0.0.0.0", port=5002, debug=True)