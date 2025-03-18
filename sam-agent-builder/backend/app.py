from flask import Flask, request, jsonify, make_response

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
    
    # Here we would actually create the agent in the agent mesh framework
    # For now, just return a success response
    
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