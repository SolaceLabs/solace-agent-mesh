"""
Pytest fixtures for speech API testing.

Provides test audio files and speech-specific configuration.
"""

import io
import pytest
from pathlib import Path


@pytest.fixture
def mock_audio_file():
    """
    Create a mock audio file for STT testing.
    Returns a file-like object with minimal WAV header.
    """
    # Minimal WAV file header (44 bytes) + some data
    wav_header = bytes([
        0x52, 0x49, 0x46, 0x46,  # "RIFF"
        0x24, 0x00, 0x00, 0x00,  # File size - 8
        0x57, 0x41, 0x56, 0x45,  # "WAVE"
        0x66, 0x6D, 0x74, 0x20,  # "fmt "
        0x10, 0x00, 0x00, 0x00,  # Subchunk1Size (16 for PCM)
        0x01, 0x00,              # AudioFormat (1 for PCM)
        0x01, 0x00,              # NumChannels (1 = mono)
        0x44, 0xAC, 0x00, 0x00,  # SampleRate (44100)
        0x88, 0x58, 0x01, 0x00,  # ByteRate
        0x02, 0x00,              # BlockAlign
        0x10, 0x00,              # BitsPerSample (16)
        0x64, 0x61, 0x74, 0x61,  # "data"
        0x00, 0x00, 0x00, 0x00,  # Subchunk2Size
    ])
    
    # Add some audio data (silence)
    audio_data = bytes([0x00] * 1000)
    
    return io.BytesIO(wav_header + audio_data)


@pytest.fixture
def mock_webm_audio_file():
    """
    Create a mock WebM audio file for STT testing.
    Returns a file-like object with minimal WebM header.
    """
    # Minimal WebM header (EBML + Segment)
    webm_header = bytes([
        0x1A, 0x45, 0xDF, 0xA3,  # EBML header
        0x01, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x1F,
    ])
    
    # Add some data
    audio_data = bytes([0x00] * 1000)
    
    return io.BytesIO(webm_header + audio_data)


@pytest.fixture
def sample_text_for_tts():
    """Sample text for TTS testing"""
    return "Hello, this is a test of the text to speech system."


@pytest.fixture
def long_text_for_tts():
    """Long text for streaming TTS testing"""
    return " ".join([
        "This is a longer text that will be used to test the streaming",
        "text-to-speech functionality. It contains multiple sentences",
        "and should be long enough to trigger chunking behavior.",
        "The system should split this into manageable pieces and",
        "stream them back to the client for better user experience."
    ] * 3)  # Repeat to make it longer