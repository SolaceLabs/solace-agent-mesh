"""
Text-to-Speech (TTS) API Integration Tests

Tests for /api/speech/tts and /api/speech/tts/stream endpoints including:
- Text-to-speech generation with different providers
- Voice selection
- Streaming for long text
- Error handling
- Provider selection
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock


class TestTTSAPI:
    """Test Text-to-Speech API endpoints"""

    @pytest.mark.skip(reason="Requires actual TTS service configuration")
    def test_tts_basic_generation(self, api_client: TestClient, sample_text_for_tts):
        """Test basic TTS generation"""
        request_data = {
            "input": sample_text_for_tts
        }
        
        response = api_client.post("/api/v1/speech/tts", json=request_data)
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mpeg"
        assert len(response.content) > 0

    @pytest.mark.skip(reason="Requires actual TTS service configuration")
    def test_tts_with_voice_selection(self, api_client: TestClient, sample_text_for_tts):
        """Test TTS with specific voice"""
        request_data = {
            "input": sample_text_for_tts,
            "voice": "Kore"
        }
        
        response = api_client.post("/api/v1/speech/tts", json=request_data)
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mpeg"

    def test_tts_empty_input(self, api_client: TestClient):
        """Test TTS with empty input returns error"""
        request_data = {
            "input": ""
        }
        
        response = api_client.post("/api/v1/speech/tts", json=request_data)
        
        assert response.status_code == 400
        assert "required" in response.json()["detail"].lower()

    def test_tts_missing_input(self, api_client: TestClient):
        """Test TTS without input field"""
        request_data = {}
        
        response = api_client.post("/api/v1/speech/tts", json=request_data)
        
        # Should return 422 for missing required field
        assert response.status_code == 422

    def test_tts_text_too_long(self, api_client: TestClient):
        """Test TTS rejects text longer than 10000 characters"""
        request_data = {
            "input": "a" * 10001
        }
        
        response = api_client.post("/api/v1/speech/tts", json=request_data)
        
        assert response.status_code == 413
        assert "too long" in response.json()["detail"].lower()

    @pytest.mark.skip(reason="Requires actual TTS service configuration")
    def test_tts_with_provider_selection(self, api_client: TestClient, sample_text_for_tts):
        """Test TTS with explicit provider selection"""
        request_data = {
            "input": sample_text_for_tts,
            "provider": "gemini"
        }
        
        response = api_client.post("/api/v1/speech/tts", json=request_data)
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mpeg"

    @pytest.mark.skip(reason="Requires actual TTS service configuration")
    def test_tts_with_message_id(self, api_client: TestClient, sample_text_for_tts):
        """Test TTS with message ID for caching"""
        request_data = {
            "input": sample_text_for_tts,
            "messageId": "test-message-123"
        }
        
        response = api_client.post("/api/v1/speech/tts", json=request_data)
        
        assert response.status_code == 200

class TestTTSStreamingAPI:
    """Test TTS streaming endpoint for long text"""

    @pytest.mark.skip(reason="Requires actual TTS service configuration")
    def test_tts_stream_long_text(self, api_client: TestClient, long_text_for_tts):
        """Test streaming TTS for long text"""
        request_data = {
            "input": long_text_for_tts
        }
        
        response = api_client.post("/api/v1/speech/tts/stream", json=request_data)
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mpeg"
        
        # Verify we got streaming data
        assert len(response.content) > 0

    @pytest.mark.skip(reason="Requires actual TTS service configuration")
    def test_tts_stream_with_run_id(self, api_client: TestClient, long_text_for_tts):
        """Test streaming TTS with run ID"""
        request_data = {
            "input": long_text_for_tts,
            "runId": "test-run-456"
        }
        
        response = api_client.post("/api/v1/speech/tts/stream", json=request_data)
        
        assert response.status_code == 200
        # Check filename in Content-Disposition header
        assert "test-run-456" in response.headers.get("content-disposition", "")

    def test_tts_stream_empty_input(self, api_client: TestClient):
        """Test streaming TTS with empty input"""
        request_data = {
            "input": ""
        }
        
        response = api_client.post("/api/v1/speech/tts/stream", json=request_data)
        
        assert response.status_code == 400

    @pytest.mark.skip(reason="Requires actual TTS service configuration")
    def test_tts_stream_chunking(self, api_client: TestClient, long_text_for_tts):
        """Test that streaming TTS chunks the response"""
        request_data = {
            "input": long_text_for_tts
        }
        
        response = api_client.post("/api/v1/speech/tts/stream", json=request_data)
        
        assert response.status_code == 200
        # Verify Cache-Control header for streaming
        assert response.headers.get("cache-control") == "no-cache"


class TestTTSVoicesAPI:
    """Test TTS voices listing endpoint"""

    @pytest.mark.skip(reason="Requires actual TTS service configuration")
    def test_get_available_voices(self, api_client: TestClient):
        """Test getting list of available voices"""
        response = api_client.get("/api/v1/speech/voices")
        
        assert response.status_code == 200
        data = response.json()
        assert "voices" in data
        assert "default" in data
        assert isinstance(data["voices"], list)
        assert len(data["voices"]) > 0

    @pytest.mark.skip(reason="Requires actual TTS service configuration")
    def test_get_voices_with_provider_filter(self, api_client: TestClient):
        """Test getting voices filtered by provider"""
        response = api_client.get("/api/v1/speech/voices?provider=azure")
        
        assert response.status_code == 200
        data = response.json()
        assert "voices" in data
        # Azure voices should contain "Neural" in names
        if len(data["voices"]) > 0:
            assert any("Neural" in voice for voice in data["voices"])

    @pytest.mark.skip(reason="Requires actual TTS service configuration")
    def test_get_voices_default_voice(self, api_client: TestClient):
        """Test that default voice is returned"""
        response = api_client.get("/api/v1/speech/voices")
        
        assert response.status_code == 200
        data = response.json()
        assert data["default"] is not None
        assert isinstance(data["default"], str)


class TestTTSConfiguration:
    """Test TTS configuration and provider handling"""

    def test_tts_config_not_configured(self, api_client: TestClient, sample_text_for_tts):
        """Test TTS returns error when not configured"""
        request_data = {
            "input": sample_text_for_tts
        }
        
        response = api_client.post("/api/v1/speech/tts", json=request_data)
        
        # Should return 500 if TTS not configured
        if response.status_code == 500:
            assert "not configured" in response.json()["detail"].lower()
        else:
            # If configured, skip this test
            pytest.skip("TTS is configured in test environment")

    @pytest.mark.skip(reason="Requires multiple TTS providers configured")
    def test_tts_provider_switching(self, api_client: TestClient, sample_text_for_tts):
        """Test switching between TTS providers"""
        # Test with Gemini
        response_gemini = api_client.post(
            "/api/v1/speech/tts",
            json={"input": sample_text_for_tts, "provider": "gemini"}
        )
        assert response_gemini.status_code == 200
        
        # Test with Azure
        response_azure = api_client.post(
            "/api/v1/speech/tts",
            json={"input": sample_text_for_tts, "provider": "azure"}
        )
        assert response_azure.status_code == 200


class TestSpeechConfigAPI:
    """Test speech configuration endpoint"""

    def test_get_speech_config(self, api_client: TestClient):
        """Test getting speech configuration"""
        response = api_client.get("/api/v1/speech/config")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check for expected configuration keys
        assert "sttExternal" in data
        assert "ttsExternal" in data
        assert isinstance(data["sttExternal"], bool)
        assert isinstance(data["ttsExternal"], bool)

    def test_speech_config_structure(self, api_client: TestClient):
        """Test speech configuration has correct structure"""
        response = api_client.get("/api/v1/speech/config")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify boolean flags
        assert isinstance(data.get("sttExternal"), bool)
        assert isinstance(data.get("ttsExternal"), bool)
        
        # If speech is configured, check for additional settings
        if data.get("ttsExternal"):
            # May have voice, playbackRate, etc.
            pass