"""
Speech-to-Text (STT) API Integration Tests

Tests for /api/speech/stt endpoint including:
- Audio transcription with different providers
- File format validation
- Error handling
- Provider selection
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock


class TestSTTAPI:
    """Test Speech-to-Text API endpoints"""

    @pytest.mark.skip(reason="Requires actual STT service configuration")
    def test_stt_with_wav_file(self, api_client: TestClient, mock_audio_file):
        """Test STT with WAV audio file"""
        # Prepare file upload
        files = {
            "audio": ("test.wav", mock_audio_file, "audio/wav")
        }
        
        # Make request
        response = api_client.post("/api/v1/speech/stt", files=files)
        
        # Assert response
        assert response.status_code == 200
        data = response.json()
        assert "text" in data
        assert "language" in data
        assert isinstance(data["text"], str)

    @pytest.mark.skip(reason="Requires actual STT service configuration")
    def test_stt_with_webm_file(self, api_client: TestClient, mock_webm_audio_file):
        """Test STT with WebM audio file"""
        files = {
            "audio": ("test.webm", mock_webm_audio_file, "audio/webm")
        }
        
        response = api_client.post("/api/v1/speech/stt", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert "text" in data

    def test_stt_missing_audio_file(self, api_client: TestClient):
        """Test STT without audio file returns error"""
        response = api_client.post("/api/v1/speech/stt")
        
        # Should return 422 for missing required field
        assert response.status_code == 422

    def test_stt_invalid_content_type(self, api_client: TestClient):
        """Test STT with invalid content type"""
        import io
        
        files = {
            "audio": ("test.txt", io.BytesIO(b"not audio"), "text/plain")
        }
        
        response = api_client.post("/api/v1/speech/stt", files=files)
        
        # Should return 415 for unsupported media type
        assert response.status_code == 415
        assert "Unsupported media type" in response.json()["detail"]

    @pytest.mark.skip(reason="Requires actual STT service configuration")
    def test_stt_with_provider_selection(self, api_client: TestClient, mock_audio_file):
        """Test STT with explicit provider selection"""
        files = {
            "audio": ("test.wav", mock_audio_file, "audio/wav")
        }
        data = {
            "provider": "openai"
        }
        
        response = api_client.post("/api/v1/speech/stt", files=files, data=data)
        
        assert response.status_code == 200
        result = response.json()
        assert "text" in result

    def test_stt_large_file_rejection(self, api_client: TestClient):
        """Test STT rejects files larger than 25MB"""
        import io
        
        # Create a file larger than 25MB
        large_file = io.BytesIO(b"0" * (26 * 1024 * 1024))
        
        files = {
            "audio": ("large.wav", large_file, "audio/wav")
        }
        
        response = api_client.post("/api/v1/speech/stt", files=files)
        
        # Should return 413 for payload too large
        assert response.status_code == 413
        assert "too large" in response.json()["detail"].lower()


class TestSTTConfiguration:
    """Test STT configuration and provider handling"""

    def test_stt_config_not_configured(self, api_client: TestClient, mock_audio_file):
        """Test STT returns error when not configured"""
        # This test assumes STT is not configured in test environment
        # If it is configured, this test should be skipped
        
        files = {
            "audio": ("test.wav", mock_audio_file, "audio/wav")
        }
        
        response = api_client.post("/api/v1/speech/stt", files=files)
        
        # Should return 500 if STT not configured
        if response.status_code == 500:
            assert "not configured" in response.json()["detail"].lower()
        else:
            # If configured, skip this test
            pytest.skip("STT is configured in test environment")

    @pytest.mark.skip(reason="Requires multiple STT providers configured")
    def test_stt_provider_switching(self, api_client: TestClient, mock_audio_file):
        """Test switching between STT providers"""
        files = {
            "audio": ("test.wav", mock_audio_file, "audio/wav")
        }
        
        # Test with OpenAI
        response_openai = api_client.post(
            "/api/v1/speech/stt",
            files=files,
            data={"provider": "openai"}
        )
        assert response_openai.status_code == 200
        
        # Test with Azure
        files["audio"][1].seek(0)  # Reset file pointer
        response_azure = api_client.post(
            "/api/v1/speech/stt",
            files=files,
            data={"provider": "azure"}
        )
        assert response_azure.status_code == 200