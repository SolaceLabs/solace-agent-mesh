import pytest
import requests
import json
import os

REST_ENDPOINT = os.getenv("REST_API_SERVER_INPUT_ENDPOINT", "/api/v1/request")
WEB_ENDPOINT = "/api/v1/chat"

@pytest.mark.skip(reason="Manually run these tests with sam running")
class TestInterruptedRequests:
    ### Rest server tests ###
    def test_rest_server_interrupted_requests(self, rest_server):
        """Test the server's ability to handle interrupted streaming responses"""
        headers = {
            'Authorization': 'Bearer test_token',
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Refresh-Token': 'test_refresh_token'
        }
        data = {
            "prompt": "Generate a long response",
            "stream": "true",
            "session_id": "test_session"
        }

        session = requests.Session() 
        try:
            # Start streaming but interrupt it
            response = requests.post(
                f"{rest_server()}{REST_ENDPOINT}",
                headers=headers,
                data=data,
                stream=True,
                timeout=10
            )
            assert response.status_code == 200
            # Simulate interruption
            for i, chunk in enumerate(response.iter_lines()):
                # print(f"Chunk {i}: {chunk.decode('utf-8')}")
                if i > 10:  # Arbitrary condition to simulate interruption
                    break
        except requests.exceptions.ReadTimeout:
            print("Request timed out, simulating interruption")
            pytest.skip("Request timed out, simulating interruption")
        finally:
            # Close the response and session
            print("\nClosing response and session")
            if 'response' in locals():
                response.close()
            session.close()

        # Verify server's health after interruption
        print("Verifying server health after interruption")
        health_response = requests.get(f"{rest_server()}/health")
        assert health_response.status_code == 200

        # Make another streaming request to ensure server is still working
        data = {
            "prompt": "Hello, this is a test message",
            "stream": "false",
            "session_id": "test_session"
        }
        print("Making another streaming request")
        with requests.post(
            f"{rest_server()}{REST_ENDPOINT}",
            headers=headers,
            data=data,
            stream=False
        ) as response:
            assert response.status_code == 200
            response_text = json.loads(response.text)
            print(f"Response: {response_text.get('response').get('content')}")
            assert response_text.get("response").get("content") is not None
            assert response_text.get("id") is not None

    ### Web server tests ###
    def test_web_server_interrupted_requests(self, web_server):
        """Test the server's ability to handle interrupted streaming responses"""
        data = {
            "prompt": "Generate a long response",
            "stream": "true",
            "session_id": "test_session"
        }
        headers = {
            'Authorization': 'Bearer test_token',
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Refresh-Token': 'test_refresh_token'
        }

        session = requests.Session()
        try:
            response = requests.post(
                f"{web_server()}{WEB_ENDPOINT}",
                headers=headers,
                data=data,
                stream=True,
                timeout=10
            )
            assert response.status_code == 200
            # Simulate interruption
            for i, chunk in enumerate(response.iter_lines()):
                print(f"Chunk {i}: {chunk.decode('utf-8')}")
                if i > 10:  # Arbitrary condition to simulate interruption
                    break
        except requests.exceptions.ReadTimeout:
            print("Request timed out, simulating interruption")
            pytest.skip("Request timed out, simulating interruption")
        finally:
            # Close the response and session
            print("\nClosing response and session")
            if 'response' in locals():
                response.close()
            session.close()
        
        # Verify server's health after interruption
        print("Verifying server health after interruption")
        health_response = requests.get(f"{web_server()}/health")
        assert health_response.status_code == 200

        # Make another streaming request to ensure server is still working
        data = {
            "prompt": "Hello, this is a test message",
            "stream": "false",
            "session_id": "test_session"
        }
        print("Making another streaming request")
        with requests.post(
            f"{web_server()}{WEB_ENDPOINT}",
            headers=headers,
            data=data,
            stream=False
        ) as response:
            assert response.status_code == 200
            response_text = json.loads(response.text)
            print(f"Response: {response_text.get('response').get('content')}")
            assert response_text.get("response").get("content") is not None
            assert response_text.get("id") is not None


    