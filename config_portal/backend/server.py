import sys
from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_cors import CORS
import os
import sys
from solace_agent_mesh.config_portal.backend.common import default_options, CONTAINER_RUN_COMMAND 
from cli.utils import get_formatted_names
import shutil
import litellm

litellm.suppress_debug_info = True

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
        path = request.args.get('path', 'advanced')
        
        modified_default_options = default_options.copy()
        
        # Base exclusions for all paths
        base_exclude_options = EXCLUDE_OPTIONS.copy()
        
        # Additional exclusions for quick path
        quick_path_exclude_options = [
            "namespace", "broker_type", "broker_url", "broker_vpn",
            "broker_username", "broker_password", "container_engine",
            "built_in_agent", "file_service_provider", "file_service_config"
        ]
        
        # Apply exclusions based on path
        exclude_options = base_exclude_options.copy()
        if path == 'quick':
            exclude_options.extend(quick_path_exclude_options)
        
        # Remove excluded options
        for option in exclude_options:
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
            force = received_data.pop('force', False)

            if not received_data:
                return jsonify({"status": "error", "message": "No data received"}), 400
            
            complete_config = default_options.copy()
            
            # Update with the received data
            for key, value in received_data.items():
                if key in complete_config or key:
                    complete_config[key] = value
            
            config_directory = complete_config["config_dir"]
            formatted_name = get_formatted_names(complete_config["rest_api_gateway_name"])
            gateway_directory = os.path.join(
            config_directory, "gateways", formatted_name["SNAKE_CASE_NAME"]
            )

            #Handle the case where the gateway directory for rest already exists
            if os.path.exists(gateway_directory) and not force:
                return jsonify({"status": "ask_confirmation", "message": f"Gateway directory {gateway_directory} already exists, it will be overwritten."}), 400
            elif os.path.exists(gateway_directory) and force:
                shutil.rmtree(gateway_directory)

            # Update the shared configuration if it exists
            if shared_config is not None:
                for key, value in complete_config.items():
                    shared_config[key] = value
            
            return jsonify({
                "status": "success",
            })
            
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/api/test_llm_config', methods=['POST'])
    def test_llm_config():
        """
        Endpoint that tests the LLM configuration given by the users"""
        llm_config = request.json

        #check for all values
        if not llm_config.get("model") or not llm_config.get("api_key") or not llm_config.get("base_url"):
            return jsonify({"status": "error", "message": "Please provide all the required values"}), 400

        try:
            response = litellm.completion(
                model=llm_config.get("model"),
                api_key=llm_config.get("api_key"),
                base_url=llm_config.get("base_url"),
                messages=[{"role":"user","content": "Say OK"}]
                )
            message = response.get("choices")[0].get("message")

            if message is not None:
                return jsonify({"status": "success", "message": message.content}), 200
            else:
                raise ValueError("No response from LLM")
        except Exception:  
            return jsonify({"status": "error", "message": "No response from LLM."}), 400



    @app.route('/api/runcontainer', methods=['POST'])
    def runcontainer():
        try:
            data = request.json or {}
            
            # Check if the user has podman or docker installed
            has_podman = shutil.which("podman") is not None
            has_docker = shutil.which("docker") is not None
            
            if not has_podman and not has_docker:
                return jsonify({
                    "status": "error", 
                    "message": "You need to have either podman or docker installed to use the container broker."
                }), 400
            
            # Determine which container engine to use
            container_engine = data.get('container_engine')
            
            # If both are available, default to podman
            if not container_engine and has_podman and has_docker:
                container_engine = "podman"
            # If only one is available, use that one
            elif not container_engine:
                container_engine = "podman" if has_podman else "docker"
            
            # Validate the container engine selection
            if container_engine not in ["podman", "docker"]:
                return jsonify({
                    "status": "error", 
                    "message": f"Invalid container engine: {container_engine}. Must be 'podman' or 'docker'."
                }), 400
            
            if container_engine == "podman" and not has_podman:
                return jsonify({
                    "status": "error", 
                    "message": "Podman was selected but is not installed on this system."
                }), 400
            
            if container_engine == "docker" and not has_docker:
                return jsonify({
                    "status": "error", 
                    "message": "Docker was selected but is not installed on this system."
                }), 400
            
            # Run command for the container start
            command = container_engine + CONTAINER_RUN_COMMAND
            
            # Execute the command and capture exit code
            response_status = os.system(command)
            
            if response_status != 0:
                return jsonify({
                    "status": "error", 
                    "message": f"Failed to start container. Exit code: {response_status}"
                }), 500
            
            return jsonify({
                "status": "success",
                "message": f"Successfully started Solace PubSub+ broker container using {container_engine}",
                "container_engine": container_engine
            })
            
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500


    @app.route('/api/shutdown', methods=['POST'])
    def shutdown():
        """Kills this Flask process immediately"""
        response = jsonify({"message": "Server shutting down...", "status": "success"})
        os._exit(0) 
        return response
        


    @app.route("/assets/<path:path>")
    def serve_assets(path):
        return send_from_directory("../frontend/static/client/assets", path)

    @app.route("/static/client/<path:path>")
    def serve_client_files(path):
        return send_from_directory("../frontend/static/client", path)

    @app.route("/", defaults={"path": ""})
    def serve(path):
        return send_file("../frontend/static/client/index.html")

    @app.route("/<path:path>")
    def serve_files(path):
        if path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico')):
            return send_from_directory("../frontend/static/client", path)
        return send_file("../frontend/static/client/index.html")
    
    return app

def run_flask(host="127.0.0.1", port=5002, shared_config=None):
    """
    Run the Flask development server with dependency-injected shared configuration.
    """
    app = create_app(shared_config)
    app.run(host=host, port=port, debug=False, use_reloader=False)

