import pytest
import time
import requests
import threading
import json
import socketio
import os

WEBUI_HOST = os.getenv("WEBUI_HOST", "http://127.0.0.1")
WEBUI_PORT = os.getenv("WEBUI_PORT", 5001)
REST_API_SERVER_HOST = os.getenv("REST_API_SERVER_HOST", "http://127.0.0.1")
REST_API_SERVER_INPUT_PORT = os.getenv("REST_API_SERVER_INPUT_PORT", 5050)

@pytest.fixture(scope="session")
def web_server():
    """Fixture to connect to the web server for testing"""
    def _web_server(port=WEBUI_PORT):
        """Connect to the web server for testing"""
        server_url = f"{WEBUI_HOST}:{port}"

        # Wait for server to start
        max_retries = 3
        for _ in range(max_retries):
            try:
                response = requests.get(f"{server_url}/health")
                if response.status_code == 200:
                    break
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("Failed to start the web server")
        
        return server_url
    return _web_server

@pytest.fixture(scope="session")
def websocket_server():
    """Fixture to connect to the websocket server for testing"""
    def _websocket_server(port=5000):
        """Connect to the websocket server for testing"""
        server_url = f"http://localhost:{port}"
        # Check if the websocket server is running
        try:
            client = socketio.Client()
            expected_actions = [
                'change_agent_status',
                'clear_history',
                'error_action',
                'create_file',
                'retrieve_file',
                'convert_file_to_markdown',
                'error_action'
            ]
            global_agent_found = threading.Event()
            received_actions = []

            @client.on('message')
            def on_message(data):
                data = json.loads(data)
                if "payload" in data and data["payload"].get("agent_name") == "global":
                    print("Found global agent registration")
                    if "actions" in data["payload"]:
                        for action_dict in data["payload"]["actions"]:
                            for action in action_dict:
                                received_actions.append(action)
                global_agent_found.set()

            client.connect(server_url)
            global_agent_found.wait(timeout=45)
            client.disconnect()
            assert global_agent_found.is_set(), "Global agent was not found"
            for action in expected_actions:
                assert action in received_actions, f"Expected action '{action}' not found in received actions"
        except socketio.exceptions.ConnectionError:
            raise RuntimeError("Failed to start the websocket server")
        return server_url
    return _websocket_server

@pytest.fixture(scope="session")
def rest_server():
    """Fixture to connect to the rest server for testing"""
    def _rest_server(port=REST_API_SERVER_INPUT_PORT):
        """Connect to the rest server for testing"""
        server_url = f"{REST_API_SERVER_HOST}:{port}"

        # Wait for server to start
        max_retries = 3
        for _ in range(max_retries):
            try:
                response = requests.get(f"{server_url}/health")
                if response.status_code == 200:
                    break
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("Failed to start the rest server")
        
        return server_url
    return _rest_server