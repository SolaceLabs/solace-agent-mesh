"""Mock service fixtures for integration tests.

This module contains mocks for external services (OAuth, Gemini, etc.).
Extracted from the main integration conftest to improve maintainability.
"""

from typing import Any

import httpx
import pytest


@pytest.fixture
def mock_oauth_server():
    """
    Provides a mock OAuth 2.0 token endpoint using respx.
    Returns a helper object for configuring responses.
    """

    class MockOAuthServer:
        def __init__(self):
            import respx

            # Allow unmocked requests to pass through to support real HTTP calls
            self.mock = respx.mock(assert_all_called=False, assert_all_mocked=False)
            self.mock.route(host="127.0.0.1").pass_through()
            self.mock.route(host="localhost").pass_through()
            self.mock.route(path="/.well-known/agent-card.json").pass_through()

            print("\n[MockOAuthServer] Initializing respx mock")
            print("[MockOAuthServer] Pass-through configured for: 127.0.0.1, localhost")
            print("[MockOAuthServer] Pass-through configured for agent card path")

            self.mock.start()
            self._routes = {}
            self._call_log = []

            print("[MockOAuthServer] Mock started.")

        def configure_token_endpoint(
            self,
            token_url: str,
            access_token: str = "test_token_12345",
            expires_in: int = 3600,
            error: dict[str, Any] | None = None,
            status_code: int = 200,
        ):
            """Configure a token endpoint to return specific responses."""
            print(f"\n[MockOAuthServer] Configuring token endpoint: {token_url}")

            if error:
                response = httpx.Response(status_code=status_code, json=error)
                print(f"[MockOAuthServer] Will return error with status {status_code}")
            else:
                response = httpx.Response(
                    status_code=200,
                    json={
                        "access_token": access_token,
                        "token_type": "Bearer",
                        "expires_in": expires_in,
                    },
                )
                print(
                    f"[MockOAuthServer] Will return access_token: {access_token[:20]}..."
                )

            route = self.mock.post(token_url).mock(return_value=response)
            self._routes[token_url] = route
            print("[MockOAuthServer] Route configured and stored")
            return route

        def configure_token_endpoint_sequence(
            self, token_url: str, responses: list[dict[str, Any]]
        ):
            """Configure a token endpoint to return a sequence of responses."""
            http_responses = []
            for resp_config in responses:
                if "error" in resp_config:
                    http_responses.append(
                        httpx.Response(
                            status_code=resp_config.get("status_code", 400),
                            json=resp_config["error"],
                        )
                    )
                else:
                    http_responses.append(
                        httpx.Response(
                            status_code=200,
                            json={
                                "access_token": resp_config.get(
                                    "access_token", "test_token"
                                ),
                                "token_type": "Bearer",
                                "expires_in": resp_config.get("expires_in", 3600),
                            },
                        )
                    )

            route = self.mock.post(token_url).mock(side_effect=http_responses)
            self._routes[token_url] = route
            return route

        def get_route(self, token_url: str):
            """Get the respx route for a token URL."""
            return self._routes.get(token_url)

        def assert_token_requested(self, token_url: str, times: int = 1):
            """Assert that a token endpoint was called a specific number of times."""
            route = self._routes.get(token_url)
            assert route is not None, f"No route configured for {token_url}"
            assert route.call_count == times, (
                f"Expected {times} calls to {token_url}, got {route.call_count}"
            )

        def get_last_token_request(self, token_url: str) -> Any | None:
            """Get the last request made to a token endpoint."""
            route = self._routes.get(token_url)
            if route and route.calls:
                return route.calls.last.request
            return None

        def stop(self):
            """Stop the mock."""
            print("\n[MockOAuthServer] Stopping respx mock")
            self.mock.stop()
            print("[MockOAuthServer] Mock stopped")

    server = MockOAuthServer()
    yield server
    server.stop()


@pytest.fixture
def mock_gemini_client(monkeypatch):
    """
    Mocks google.genai.Client and PIL.Image.open to prevent real API calls.
    Allows deterministic testing of Gemini-based tools.
    """

    class MockPILImage:
        def __init__(self):
            self.size = (1, 1)
            self.mode = "RGB"

        def split(self):
            return []

        def save(self, fp, format=None, quality=None):
            fp.write(b"mock_image_bytes")

    def mock_open(fp):
        return MockPILImage()

    try:
        from PIL import Image

        monkeypatch.setattr(Image, "open", mock_open)
    except ImportError:
        pass

    class MockPart:
        def __init__(self, text=None, inline_data=None):
            self.text = text
            self.inline_data = inline_data

    class MockContent:
        def __init__(self, parts):
            self.parts = parts

    class MockCandidate:
        def __init__(self, content):
            self.content = content

    class MockGenerateContentResponse:
        def __init__(self, candidates):
            self.candidates = candidates

    class MockGeminiClient:
        def __init__(self, api_key=None):
            self._api_key = api_key
            self.models = self

        def generate_content(self, model, contents, config):
            if self._api_key != "fake-gemini-api-key":
                raise Exception(
                    "400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': 'API key not valid. Please pass a valid API key.'}}"
                )

            edited_image_bytes = b"edited_image_bytes"
            mock_response = MockGenerateContentResponse(
                candidates=[
                    MockCandidate(
                        content=MockContent(
                            parts=[
                                MockPart(text="Image edited successfully."),
                                MockPart(
                                    inline_data=type(
                                        "obj", (object,), {"data": edited_image_bytes}
                                    )()
                                ),
                            ]
                        )
                    )
                ]
            )
            return mock_response

    monkeypatch.setattr("google.genai.Client", MockGeminiClient)
