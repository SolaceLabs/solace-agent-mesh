import sys
from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import sys
from solace_agent_mesh.config_portal.backend.common import default_options

#disable flask startup banner
import logging
log = logging.getLogger('werkzeug')
log.disabled = True
cli = sys.modules['flask.cli']
cli.show_server_banner = lambda *x: None


def create_app(shared_config=None):
    """Factory function that creates the Flask application with configuration injected"""
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5174", "http://127.0.0.1:5174"]}})

    EXCLUDE_OPTIONS = ["config_dir", "module_dir", "env_file", "build_dir", "container_engine", "rest_api_enabled",
                     "rest_api_server_input_port", "rest_api_server_host", "rest_api_server_input_endpoint", 
                     "rest_api_gateway_name", "webui_enabled", "webui_listen_port", "webui_host"]

    @app.route('/api/default_options', methods=['GET'])
    def get_default_options():
        """Endpoint that returns the default options for form initialization"""
        modified_default_options = default_options.copy()
        for option in EXCLUDE_OPTIONS:
            modified_default_options.pop(option, None)
        return jsonify({
            "default_options": modified_default_options,
            "status": "success"
        })

    @app.route('/api/save_config', methods=['POST'])
    def save_config():
        """
        Endpoint that accepts configuration data from the frontend,
        merges it with default options, and updates the shared configuration.
        """
        try:
            received_data = request.json
            
            if not received_data:
                return jsonify({"status": "error", "message": "No data received"}), 400
            
            complete_config = default_options.copy()
            
            # Update with the received data
            for key, value in received_data.items():
                if key in complete_config or key:
                    complete_config[key] = value
            
            # Update the shared configuration if it exists
            if shared_config is not None:
                for key, value in complete_config.items():
                    shared_config[key] = value
            
            return jsonify({
                "status": "success",
            })
            
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/api/shutdown', methods=['POST'])
    def shutdown():
        """Kills this Flask process immediately"""
        response = jsonify({"message": "Server shutting down...", "status": "success"})
        os._exit(0) 
        return response
        
    return app

def run_flask(host="127.0.0.1", port=5002, shared_config=None):
    """
    Run the Flask development server with dependency-injected shared configuration.
    """
    app = create_app(shared_config)
    app.run(host=host, port=port, debug=False, use_reloader=False)

