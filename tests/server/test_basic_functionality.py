import json
import time
import socketio
import pytest
import requests
import threading
import os

REST_API_SERVER_INPUT_ENDPOINT = os.getenv("REST_API_SERVER_INPUT_ENDPOINT", "/api/v1/request")

@pytest.mark.skip(reason="Manually run these tests with sam running")
class TestBasicFunctionality:
    ### Web server tests ###
    def test_web_server_health(self, web_server):
        """Test the health endpoint of the web server"""
        response = requests.get(f"{web_server()}/health")
        assert response.status_code == 200

    def test_csrf_token(self, web_server):
        """Test CSRF token in the response"""
        response = requests.get(f"{web_server()}/api/v1/csrf-token")
        assert response.status_code == 200
        assert 'csrf_token' in response.cookies
        assert response.cookies['csrf_token']

    def test_config_endpoint(self, web_server):
        """Test the config endpoint"""
        response = requests.get(f"{web_server()}/api/v1/config")
        assert response.status_code == 200
        data = response.json()
        assert 'frontend_server_url' in data
        assert 'frontend_bot_name' in data

    def test_feedback_endpoint(self, web_server):
        """Test the feedback endpoint"""
        data = {
            "messageId": "test_message_id",
            "sessionId": "test_session_id",
            "isPositive": True
        }
        response = requests.post(
            f"{web_server()}/api/v1/feedback",
            json=data,
            headers={'Content-Type': 'application/json'}
        )
        assert response.status_code == 200
        assert response.json().get('status') == 'success'

    def test_chat_endpoint(self, web_server):
        """Test the chat endpoint"""
        data = {
            "prompt": "Hello, this is a test message",
            "stream": "false",
            "session_id": "test_session"
        }
        headers = {
            'Authorization': 'Bearer test_token',
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Refresh-Token': 'test_refresh_token'
        }
        response = requests.post(
            f"{web_server()}/api/v1/chat",
            data=data,
            headers=headers
        )
        assert response.status_code == 200
        assert 'response' in response.json()
        assert response.json()['response']['content'] is not None
        # print(f"\nResponse: {response.json()['response']['content']}")

    ### Rest server tests ###
    def test_rest_server_health(self, rest_server):
        """Test the health endpoint of the rest server"""
        response = requests.get(f"{rest_server()}/health")
        assert response.status_code == 200

    def test_single_chat_request(self, rest_server):
        """Test a single chat request"""
        try:
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }

            data = {
                "prompt": "Hello, this is a test message",
                "stream": "false",
                "session_id": "test_session"
            }

            response = requests.post(
                f"{rest_server()}{REST_API_SERVER_INPUT_ENDPOINT}",
                data=data,
                headers=headers
            )
            assert response.status_code == 200
        except Exception as e:
            print(f"Error during chat request: {e}")
            assert False, "Chat request failed"

    ### Websocket server tests ###
    def test_websocket_server_connection(self, websocket_server):
        """Test the websocket server connection"""
        try:
            websocket_server()
        except socketio.exceptions.ConnectionError:
            assert False, "Websocket server connection failed"
        except Exception as e:
            assert False, f"Unexpected error: {e}"
