"""
Unit tests for src/solace_agent_mesh/agent/tools/audio_tools.py

Tests the audio tools functionality including:
- Voice tone and gender mapping
- Voice selection algorithms
- Language code handling
- Voice configuration creation
- Helper functions for audio processing
- Edge cases and error conditions
"""

from unittest.mock import Mock, patch, MagicMock
import pytest

from src.solace_agent_mesh.agent.tools.audio_tools import (
    VOICE_TONE_MAPPING,
    GENDER_TO_VOICE_MAPPING,
    ALL_AVAILABLE_VOICES,
    DEFAULT_VOICE,
    _get_effective_tone_voices,
    _get_gender_voices,
    _get_voice_for_speaker,
    _get_language_code,
    _create_voice_config,
    _create_multi_speaker_config,
    _create_wav_file,
    _convert_pcm_to_mp3,
    _generate_audio_with_gemini,
    _save_audio_artifact,
    _is_supported_audio_format_for_transcription,
    _get_audio_mime_type,
    select_voice,
    text_to_speech,
    multi_speaker_text_to_speech,
    concatenate_audio,
    transcribe_audio,
)


class TestGetEffectiveToneVoices:
    """Tests for _get_effective_tone_voices function"""

    def test_get_effective_tone_voices_valid_tone(self):
        """Test getting voices for valid tone"""
        result = _get_effective_tone_voices("bright")
        assert result is not None
        assert isinstance(result, list)
        assert len(result) > 0
        assert result == VOICE_TONE_MAPPING["bright"]

    def test_get_effective_tone_voices_case_insensitive(self):
        """Test that tone matching is case insensitive"""
        result_lower = _get_effective_tone_voices("bright")
        result_upper = _get_effective_tone_voices("BRIGHT")
        result_mixed = _get_effective_tone_voices("Bright")
        
        assert result_lower == result_upper == result_mixed

    def test_get_effective_tone_voices_with_whitespace(self):
        """Test tone matching with whitespace"""
        result = _get_effective_tone_voices("  bright  ")
        assert result == VOICE_TONE_MAPPING["bright"]

    def test_get_effective_tone_voices_alias_mapping(self):
        """Test tone alias mapping"""
        # Test some aliases
        aliases = {
            "professional": "firm",
            "cheerful": "upbeat",
            "calm": "soft",
            "serious": "informative"
        }
        
        for alias, actual_tone in aliases.items():
            result = _get_effective_tone_voices(alias)
            expected = VOICE_TONE_MAPPING.get(actual_tone)
            assert result == expected

    def test_get_effective_tone_voices_invalid_tone(self):
        """Test getting voices for invalid tone"""
        result = _get_effective_tone_voices("nonexistent_tone")
        assert result is None

    def test_get_effective_tone_voices_none_input(self):
        """Test getting voices for None tone"""
        result = _get_effective_tone_voices(None)
        assert result is None

    def test_get_effective_tone_voices_empty_string(self):
        """Test getting voices for empty string tone"""
        result = _get_effective_tone_voices("")
        assert result is None

    def test_get_effective_tone_voices_custom_mapping(self):
        """Test getting voices with custom tone mapping"""
        custom_mapping = {
            "custom_tone": ["CustomVoice1", "CustomVoice2"]
        }
        
        result = _get_effective_tone_voices("custom_tone", custom_mapping)
        assert result == ["CustomVoice1", "CustomVoice2"]


class TestGetGenderVoices:
    """Tests for _get_gender_voices function"""

    def test_get_gender_voices_valid_gender(self):
        """Test getting voices for valid gender"""
        for gender in ["male", "female", "neutral"]:
            result = _get_gender_voices(gender)
            assert result is not None
            assert isinstance(result, list)
            assert len(result) > 0
            assert result == GENDER_TO_VOICE_MAPPING[gender]

    def test_get_gender_voices_case_insensitive(self):
        """Test that gender matching is case insensitive"""
        result_lower = _get_gender_voices("male")
        result_upper = _get_gender_voices("MALE")
        result_mixed = _get_gender_voices("Male")
        
        assert result_lower == result_upper == result_mixed

    def test_get_gender_voices_with_whitespace(self):
        """Test gender matching with whitespace"""
        result = _get_gender_voices("  female  ")
        assert result == GENDER_TO_VOICE_MAPPING["female"]

    def test_get_gender_voices_invalid_gender(self):
        """Test getting voices for invalid gender"""
        result = _get_gender_voices("nonexistent_gender")
        assert result is None

    def test_get_gender_voices_none_input(self):
        """Test getting voices for None gender"""
        result = _get_gender_voices(None)
        assert result is None

    def test_get_gender_voices_empty_string(self):
        """Test getting voices for empty string gender"""
        result = _get_gender_voices("")
        assert result is None

    def test_get_gender_voices_custom_mapping(self):
        """Test getting voices with custom gender mapping"""
        custom_mapping = {
            "custom_gender": ["CustomVoice1", "CustomVoice2"]
        }
        
        result = _get_gender_voices("custom_gender", custom_mapping)
        assert result == ["CustomVoice1", "CustomVoice2"]


class TestGetVoiceForSpeaker:
    """Tests for _get_voice_for_speaker function"""

    def test_get_voice_for_speaker_no_constraints(self):
        """Test voice selection with no gender or tone constraints"""
        used_voices = set()
        result = _get_voice_for_speaker(None, None, used_voices)
        
        assert result in ALL_AVAILABLE_VOICES
        assert isinstance(result, str)

    def test_get_voice_for_speaker_gender_only(self):
        """Test voice selection with gender constraint only"""
        used_voices = set()
        result = _get_voice_for_speaker("male", None, used_voices)
        
        assert result in GENDER_TO_VOICE_MAPPING["male"]

    def test_get_voice_for_speaker_tone_only(self):
        """Test voice selection with tone constraint only"""
        used_voices = set()
        result = _get_voice_for_speaker(None, "bright", used_voices)
        
        assert result in VOICE_TONE_MAPPING["bright"]

    def test_get_voice_for_speaker_both_constraints(self):
        """Test voice selection with both gender and tone constraints"""
        used_voices = set()
        result = _get_voice_for_speaker("female", "bright", used_voices)
        
        # Should be in both the gender and tone lists
        female_voices = set(GENDER_TO_VOICE_MAPPING["female"])
        bright_voices = set(VOICE_TONE_MAPPING["bright"])
        valid_voices = female_voices.intersection(bright_voices)
        
        if valid_voices:
            assert result in valid_voices
        else:
            # If no intersection, should fall back to gender or tone only
            assert result in female_voices or result in bright_voices

    def test_get_voice_for_speaker_avoids_used_voices(self):
        """Test that voice selection avoids already used voices"""
        # Use all but one voice from a small set
        available_voices = VOICE_TONE_MAPPING["bright"][:3]  # Take first 3
        used_voices = set(available_voices[:-1])  # Use all but last
        
        with patch('src.solace_agent_mesh.agent.tools.audio_tools.ALL_AVAILABLE_VOICES', available_voices):
            result = _get_voice_for_speaker(None, "bright", used_voices)
            assert result not in used_voices

    def test_get_voice_for_speaker_reuses_when_all_used(self):
        """Test that voice selection reuses voices when all are used"""
        available_voices = ["Voice1", "Voice2"]
        used_voices = set(available_voices)  # All voices used
        
        with patch('src.solace_agent_mesh.agent.tools.audio_tools.ALL_AVAILABLE_VOICES', available_voices):
            result = _get_voice_for_speaker(None, None, used_voices)
            assert result in available_voices  # Should reuse

    def test_get_voice_for_speaker_invalid_gender(self):
        """Test voice selection with invalid gender"""
        used_voices = set()
        result = _get_voice_for_speaker("invalid_gender", None, used_voices)
        
        # Should fall back to any available voice
        assert result in ALL_AVAILABLE_VOICES

    def test_get_voice_for_speaker_invalid_tone(self):
        """Test voice selection with invalid tone"""
        used_voices = set()
        result = _get_voice_for_speaker(None, "invalid_tone", used_voices)
        
        # Should fall back to any available voice
        assert result in ALL_AVAILABLE_VOICES

    def test_get_voice_for_speaker_fallback_to_default(self):
        """Test voice selection falls back to default when no voices available"""
        with patch('src.solace_agent_mesh.agent.tools.audio_tools.ALL_AVAILABLE_VOICES', []):
            used_voices = set()
            result = _get_voice_for_speaker(None, None, used_voices)
            assert result == DEFAULT_VOICE

    @patch('src.solace_agent_mesh.agent.tools.audio_tools.random.choice')
    def test_get_voice_for_speaker_randomization(self, mock_choice):
        """Test that voice selection uses randomization"""
        mock_choice.return_value = "TestVoice"
        used_voices = set()
        
        result = _get_voice_for_speaker(None, None, used_voices)
        
        assert mock_choice.called
        assert result == "TestVoice"

    def test_voice_selection_deterministic_with_seed(self):
        """Test that voice selection is deterministic when random seed is set"""
        import random
        
        used_voices = set()
        
        # Set seed and get result
        random.seed(42)
        result1 = _get_voice_for_speaker("male", "bright", used_voices)
        
        # Reset seed and get result again
        random.seed(42)
        result2 = _get_voice_for_speaker("male", "bright", used_voices)
        
        assert result1 == result2


class TestGetLanguageCode:
    """Tests for _get_language_code function"""

    def test_get_language_code_valid_language_name(self):
        """Test getting language code for valid language name"""
        result = _get_language_code("english")
        assert result == "en-US"
        
        result = _get_language_code("spanish")
        assert result == "es-US"

    def test_get_language_code_case_insensitive(self):
        """Test that language code lookup is case insensitive"""
        result_lower = _get_language_code("english")
        result_upper = _get_language_code("ENGLISH")
        result_mixed = _get_language_code("English")
        
        assert result_lower == result_upper == result_mixed

    def test_get_language_code_with_whitespace(self):
        """Test language code lookup with whitespace"""
        result = _get_language_code("  english  ")
        assert result == "en-US"

    def test_get_language_code_already_bcp47(self):
        """Test getting language code for already BCP-47 formatted input"""
        result = _get_language_code("en-GB")
        assert result == "en-GB"
        
        result = _get_language_code("es-MX")
        assert result == "es-MX"

    def test_get_language_code_invalid_language(self):
        """Test getting language code for invalid language"""
        result = _get_language_code("nonexistent_language")
        assert result == "en-US"  # Should default to English

    def test_get_language_code_none_input(self):
        """Test getting language code for None input"""
        result = _get_language_code(None)
        assert result == "en-US"

    def test_get_language_code_empty_string(self):
        """Test getting language code for empty string"""
        result = _get_language_code("")
        assert result == "en-US"

    def test_get_language_code_short_string(self):
        """Test getting language code for string shorter than BCP-47 format"""
        result = _get_language_code("en")
        assert result == "en-US"  # Should default since it's not full BCP-47


class TestCreateVoiceConfig:
    """Tests for _create_voice_config function"""

    @patch('src.solace_agent_mesh.agent.tools.audio_tools.adk_types')
    def test_create_voice_config(self, mock_adk_types):
        """Test creating voice configuration"""
        mock_voice_config = Mock()
        mock_adk_types.VoiceConfig.return_value = mock_voice_config
        mock_adk_types.PrebuiltVoiceConfig.return_value = Mock()
        
        result = _create_voice_config("TestVoice")
        
        assert result == mock_voice_config
        mock_adk_types.PrebuiltVoiceConfig.assert_called_once_with(voice_name="TestVoice")
        mock_adk_types.VoiceConfig.assert_called_once()


class TestCreateMultiSpeakerConfig:
    """Tests for _create_multi_speaker_config function"""

    @patch('src.solace_agent_mesh.agent.tools.audio_tools.adk_types')
    @patch('src.solace_agent_mesh.agent.tools.audio_tools._create_voice_config')
    def test_create_multi_speaker_config_single_speaker(self, mock_create_voice_config, mock_adk_types):
        """Test creating multi-speaker configuration with single speaker"""
        mock_voice_config = Mock()
        mock_create_voice_config.return_value = mock_voice_config
        
        mock_speaker_voice_config = Mock()
        mock_adk_types.SpeakerVoiceConfig.return_value = mock_speaker_voice_config
        
        mock_multi_config = Mock()
        mock_adk_types.MultiSpeakerVoiceConfig.return_value = mock_multi_config
        
        speaker_configs = [{"name": "Speaker1", "voice": "Voice1"}]
        
        result = _create_multi_speaker_config(speaker_configs)
        
        assert result == mock_multi_config
        mock_create_voice_config.assert_called_once_with("Voice1")
        mock_adk_types.SpeakerVoiceConfig.assert_called_once_with(
            speaker="Speaker1",
            voice_config=mock_voice_config
        )
        mock_adk_types.MultiSpeakerVoiceConfig.assert_called_once_with(
            speaker_voice_configs=[mock_speaker_voice_config]
        )

    @patch('src.solace_agent_mesh.agent.tools.audio_tools.adk_types')
    @patch('src.solace_agent_mesh.agent.tools.audio_tools._create_voice_config')
    def test_create_multi_speaker_config_multiple_speakers(self, mock_create_voice_config, mock_adk_types):
        """Test creating multi-speaker configuration with multiple speakers"""
        mock_voice_config = Mock()
        mock_create_voice_config.return_value = mock_voice_config
        
        mock_speaker_voice_config = Mock()
        mock_adk_types.SpeakerVoiceConfig.return_value = mock_speaker_voice_config
        
        mock_multi_config = Mock()
        mock_adk_types.MultiSpeakerVoiceConfig.return_value = mock_multi_config
        
        speaker_configs = [
            {"name": "Speaker1", "voice": "Voice1"},
            {"name": "Speaker2", "voice": "Voice2"}
        ]
        
        result = _create_multi_speaker_config(speaker_configs)
        
        assert result == mock_multi_config
        assert mock_create_voice_config.call_count == 2
        assert mock_adk_types.SpeakerVoiceConfig.call_count == 2

    @patch('src.solace_agent_mesh.agent.tools.audio_tools.adk_types')
    @patch('src.solace_agent_mesh.agent.tools.audio_tools._create_voice_config')
    def test_create_multi_speaker_config_default_values(self, mock_create_voice_config, mock_adk_types):
        """Test creating multi-speaker configuration with default values"""
        mock_voice_config = Mock()
        mock_create_voice_config.return_value = mock_voice_config
        
        mock_speaker_voice_config = Mock()
        mock_adk_types.SpeakerVoiceConfig.return_value = mock_speaker_voice_config
        
        mock_multi_config = Mock()
        mock_adk_types.MultiSpeakerVoiceConfig.return_value = mock_multi_config
        
        # Config with missing name and voice
        speaker_configs = [{}]
        
        result = _create_multi_speaker_config(speaker_configs)
        
        assert result == mock_multi_config
        mock_create_voice_config.assert_called_once_with("Kore")  # Default voice
        mock_adk_types.SpeakerVoiceConfig.assert_called_once_with(
            speaker="Speaker",  # Default name
            voice_config=mock_voice_config
        )

    @patch('src.solace_agent_mesh.agent.tools.audio_tools.adk_types')
    def test_create_multi_speaker_config_empty_list(self, mock_adk_types):
        """Test creating multi-speaker configuration with empty speaker list"""
        mock_multi_config = Mock()
        mock_adk_types.MultiSpeakerVoiceConfig.return_value = mock_multi_config
        
        result = _create_multi_speaker_config([])
        
        assert result == mock_multi_config
        mock_adk_types.MultiSpeakerVoiceConfig.assert_called_once_with(
            speaker_voice_configs=[]
        )


class TestCreateWavFile:
    """Tests for _create_wav_file function"""

    def test_create_wav_file_basic(self):
        """Test creating a basic WAV file"""
        with patch('builtins.open', new_callable=MagicMock) as mock_open:
            pcm_data = b'\x00\x00' * 24000
            _create_wav_file("test.wav", pcm_data)
            mock_open.assert_called_with("test.wav", "wb")

    def test_create_wav_file_custom_params(self):
        """Test creating WAV file with custom parameters"""
        with patch('builtins.open', new_callable=MagicMock) as mock_open:
            pcm_data = b'\x00\x00' * 1000
            _create_wav_file("test.wav", pcm_data, channels=2, rate=48000, sample_width=4)
            mock_open.assert_called_with("test.wav", "wb")

    def test_create_wav_file_empty_data(self):
        """Test creating WAV file with empty PCM data"""
        with patch('builtins.open', new_callable=MagicMock) as mock_open:
            pcm_data = b''
            _create_wav_file("test.wav", pcm_data)
            mock_open.assert_called_with("test.wav", "wb")


class TestIsSupportedAudioFormat:
    """Tests for _is_supported_audio_format_for_transcription function"""

    def test_supported_wav_format(self):
        """Test that .wav files are supported"""
        assert _is_supported_audio_format_for_transcription("audio.wav") is True
        assert _is_supported_audio_format_for_transcription("audio.WAV") is True
        assert _is_supported_audio_format_for_transcription("/path/to/audio.wav") is True

    def test_supported_mp3_format(self):
        """Test that .mp3 files are supported"""
        assert _is_supported_audio_format_for_transcription("audio.mp3") is True
        assert _is_supported_audio_format_for_transcription("audio.MP3") is True
        assert _is_supported_audio_format_for_transcription("/path/to/audio.mp3") is True

    def test_unsupported_formats(self):
        """Test that other formats are not supported"""
        assert _is_supported_audio_format_for_transcription("audio.flac") is False
        assert _is_supported_audio_format_for_transcription("audio.ogg") is False
        assert _is_supported_audio_format_for_transcription("audio.m4a") is False
        assert _is_supported_audio_format_for_transcription("audio.aac") is False

    def test_no_extension(self):
        """Test files without extension"""
        assert _is_supported_audio_format_for_transcription("audio") is False
        assert _is_supported_audio_format_for_transcription("") is False


class TestGetAudioMimeType:
    """Tests for _get_audio_mime_type function"""

    def test_wav_mime_type(self):
        """Test getting MIME type for WAV files"""
        assert _get_audio_mime_type("audio.wav") == "audio/wav"
        assert _get_audio_mime_type("audio.WAV") == "audio/wav"
        assert _get_audio_mime_type("/path/to/audio.wav") == "audio/wav"

    def test_mp3_mime_type(self):
        """Test getting MIME type for MP3 files"""
        assert _get_audio_mime_type("audio.mp3") == "audio/mpeg"
        assert _get_audio_mime_type("audio.MP3") == "audio/mpeg"
        assert _get_audio_mime_type("/path/to/audio.mp3") == "audio/mpeg"

    def test_unknown_mime_type(self):
        """Test getting MIME type for unknown formats defaults to wav"""
        assert _get_audio_mime_type("audio.flac") == "audio/wav"
        assert _get_audio_mime_type("audio.ogg") == "audio/wav"
        assert _get_audio_mime_type("audio") == "audio/wav"


class TestConvertPcmToMp3:
    """Tests for _convert_pcm_to_mp3 async function"""

    @pytest.mark.asyncio
    async def test_convert_pcm_to_mp3_success(self):
        """Test successful PCM to MP3 conversion"""
        pcm_data = b'\x00\x00' * 1000
        
        with patch('src.solace_agent_mesh.agent.tools.audio_tools.tempfile.NamedTemporaryFile') as mock_temp, \
             patch('src.solace_agent_mesh.agent.tools.audio_tools.asyncio.to_thread') as mock_to_thread, \
             patch('src.solace_agent_mesh.agent.tools.audio_tools.AudioSegment') as mock_audio_segment, \
             patch('builtins.open', create=True) as mock_open:
            
            mock_wav_file = MagicMock()
            mock_wav_file.name = '/tmp/test.wav'
            mock_mp3_file = MagicMock()
            mock_mp3_file.name = '/tmp/test.mp3'
            
            mock_temp.side_effect = [mock_wav_file, mock_mp3_file]
            
            mock_audio = MagicMock()
            mock_audio_segment.from_wav.return_value = mock_audio
            mock_to_thread.side_effect = [None, mock_audio, None]
            
            mock_file_handle = MagicMock()
            mock_file_handle.read.return_value = b'mp3_data'
            mock_open.return_value.__enter__.return_value = mock_file_handle
            
            result = await _convert_pcm_to_mp3(pcm_data)
            
            assert result == b'mp3_data'
            assert mock_to_thread.call_count == 3

    @pytest.mark.asyncio
    async def test_convert_pcm_to_mp3_cleanup(self):
        """Test that temporary files are cleaned up"""
        pcm_data = b'\x00\x00' * 100
        
        with patch('src.solace_agent_mesh.agent.tools.audio_tools.tempfile.NamedTemporaryFile') as mock_temp, \
             patch('src.solace_agent_mesh.agent.tools.audio_tools.asyncio.to_thread') as mock_to_thread, \
             patch('src.solace_agent_mesh.agent.tools.audio_tools.AudioSegment') as mock_audio_segment, \
             patch('builtins.open', create=True) as mock_open, \
             patch('os.remove') as mock_remove:
            
            mock_wav_file = MagicMock()
            mock_wav_file.name = '/tmp/test.wav'
            mock_mp3_file = MagicMock()
            mock_mp3_file.name = '/tmp/test.mp3'
            
            mock_temp.side_effect = [mock_wav_file, mock_mp3_file]
            
            mock_audio = MagicMock()
            mock_audio_segment.from_wav.return_value = mock_audio
            mock_to_thread.side_effect = [None, mock_audio, None]
            
            mock_file_handle = MagicMock()
            mock_file_handle.read.return_value = b'mp3_data'
            mock_open.return_value.__enter__.return_value = mock_file_handle
            
            await _convert_pcm_to_mp3(pcm_data)
            
            assert mock_remove.call_count == 2


class TestGenerateAudioWithGemini:
    """Tests for _generate_audio_with_gemini async function"""

    @pytest.mark.asyncio
    async def test_generate_audio_success(self):
        """Test successful audio generation"""
        mock_client = MagicMock()
        mock_speech_config = MagicMock()
        
        mock_inline_data = MagicMock()
        mock_inline_data.data = b'audio_data'
        
        mock_part = MagicMock()
        mock_part.inline_data = mock_inline_data
        
        mock_content = MagicMock()
        mock_content.parts = [mock_part]
        
        mock_candidate = MagicMock()
        mock_candidate.content = mock_content
        
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        
        with patch('src.solace_agent_mesh.agent.tools.audio_tools.asyncio.to_thread') as mock_to_thread, \
             patch('src.solace_agent_mesh.agent.tools.audio_tools.adk_types') as mock_adk_types:
            
            mock_to_thread.return_value = mock_response
            mock_config = MagicMock()
            mock_adk_types.GenerateContentConfig.return_value = mock_config
            
            result = await _generate_audio_with_gemini(
                mock_client,
                "Test prompt",
                mock_speech_config,
                model="test-model",
                language="en-US"
            )
            
            assert result == b'audio_data'
            mock_to_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_audio_no_response(self):
        """Test error when no response from API"""
        mock_client = MagicMock()
        mock_speech_config = MagicMock()
        
        with patch('src.solace_agent_mesh.agent.tools.audio_tools.asyncio.to_thread') as mock_to_thread, \
             patch('src.solace_agent_mesh.agent.tools.audio_tools.adk_types'):
            
            mock_to_thread.return_value = None
            
            with pytest.raises(ValueError, match="did not return valid audio data"):
                await _generate_audio_with_gemini(
                    mock_client,
                    "Test prompt",
                    mock_speech_config
                )

    @pytest.mark.asyncio
    async def test_generate_audio_no_audio_data(self):
        """Test error when response has no audio data"""
        mock_client = MagicMock()
        mock_speech_config = MagicMock()
        
        mock_inline_data = MagicMock()
        mock_inline_data.data = None
        
        mock_part = MagicMock()
        mock_part.inline_data = mock_inline_data
        
        mock_content = MagicMock()
        mock_content.parts = [mock_part]
        
        mock_candidate = MagicMock()
        mock_candidate.content = mock_content
        
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        
        with patch('src.solace_agent_mesh.agent.tools.audio_tools.asyncio.to_thread') as mock_to_thread, \
             patch('src.solace_agent_mesh.agent.tools.audio_tools.adk_types'):
            
            mock_to_thread.return_value = mock_response
            
            with pytest.raises(ValueError, match="No audio data received"):
                await _generate_audio_with_gemini(
                    mock_client,
                    "Test prompt",
                    mock_speech_config
                )


class TestSaveAudioArtifact:
    """Tests for _save_audio_artifact async function"""

    @pytest.mark.asyncio
    async def test_save_audio_artifact_success(self):
        """Test successful audio artifact saving"""
        audio_data = b'test_audio_data'
        filename = "test.mp3"
        metadata = {"description": "Test audio"}
        
        mock_tool_context = MagicMock()
        mock_inv_context = MagicMock()
        mock_inv_context.app_name = "test_app"
        mock_inv_context.user_id = "test_user"
        mock_inv_context.artifact_service = MagicMock()
        mock_tool_context._invocation_context = mock_inv_context
        
        with patch('src.solace_agent_mesh.agent.tools.audio_tools.get_original_session_id') as mock_get_session, \
             patch('src.solace_agent_mesh.agent.tools.audio_tools.save_artifact_with_metadata') as mock_save:
            
            mock_get_session.return_value = "test_session"
            mock_save.return_value = {"status": "success", "data_version": 1}
            
            result = await _save_audio_artifact(
                audio_data, filename, metadata, mock_tool_context
            )
            
            assert result["status"] == "success"
            assert result["data_version"] == 1
            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_audio_artifact_no_service(self):
        """Test error when artifact service is not available"""
        audio_data = b'test_audio_data'
        filename = "test.mp3"
        metadata = {"description": "Test audio"}
        
        mock_tool_context = MagicMock()
        mock_inv_context = MagicMock()
        mock_inv_context.artifact_service = None
        mock_tool_context._invocation_context = mock_inv_context
        
        with pytest.raises(ValueError, match="ArtifactService is not available"):
            await _save_audio_artifact(
                audio_data, filename, metadata, mock_tool_context
            )

    @pytest.mark.asyncio
    async def test_save_audio_artifact_save_error(self):
        """Test error handling when save fails"""
        audio_data = b'test_audio_data'
        filename = "test.mp3"
        metadata = {"description": "Test audio"}
        
        mock_tool_context = MagicMock()
        mock_inv_context = MagicMock()
        mock_inv_context.app_name = "test_app"
        mock_inv_context.user_id = "test_user"
        mock_inv_context.artifact_service = MagicMock()
        mock_tool_context._invocation_context = mock_inv_context
        
        with patch('src.solace_agent_mesh.agent.tools.audio_tools.get_original_session_id') as mock_get_session, \
             patch('src.solace_agent_mesh.agent.tools.audio_tools.save_artifact_with_metadata') as mock_save:
            
            mock_get_session.return_value = "test_session"
            mock_save.return_value = {"status": "error", "message": "Save failed"}
            
            with pytest.raises(IOError, match="Failed to save audio artifact"):
                await _save_audio_artifact(
                    audio_data, filename, metadata, mock_tool_context
                )


class TestSelectVoice:
    """Tests for select_voice async function"""

    @pytest.mark.asyncio
    async def test_select_voice_with_gender(self):
        """Test voice selection with gender parameter"""
        result = await select_voice(gender="male")
        
        assert result["status"] == "success"
        assert "voice_name" in result
        assert isinstance(result["voice_name"], str)

    @pytest.mark.asyncio
    async def test_select_voice_with_tone(self):
        """Test voice selection with tone parameter"""
        result = await select_voice(tone="friendly")
        
        assert result["status"] == "success"
        assert "voice_name" in result

    @pytest.mark.asyncio
    async def test_select_voice_with_exclusions(self):
        """Test voice selection with excluded voices"""
        exclude_list = ["Kore", "Puck"]
        result = await select_voice(exclude_voices=exclude_list)
        
        assert result["status"] == "success"
        assert result["voice_name"] not in exclude_list

    @pytest.mark.asyncio
    async def test_select_voice_no_params(self):
        """Test voice selection with no parameters"""
        result = await select_voice()
        
        assert result["status"] == "success"
        assert "voice_name" in result

    @pytest.mark.asyncio
    async def test_select_voice_exception_handling(self):
        """Test exception handling in select_voice"""
        with patch('src.solace_agent_mesh.agent.tools.audio_tools._get_voice_for_speaker', side_effect=Exception("Test error")):
            result = await select_voice(gender="male")
            
            assert result["status"] == "error"
            assert "error" in result["message"].lower()


class TestTextToSpeech:
    """Tests for text_to_speech async function"""

    @pytest.mark.asyncio
    async def test_text_to_speech_missing_context(self):
        """Test error when tool context is missing"""
        result = await text_to_speech("Hello world", tool_context=None)
        
        assert result["status"] == "error"
        assert "ToolContext is missing" in result["message"]

    @pytest.mark.asyncio
    async def test_text_to_speech_empty_text(self):
        """Test error when text is empty"""
        mock_context = MagicMock()
        result = await text_to_speech("", tool_context=mock_context)
        
        assert result["status"] == "error"
        assert "Text input is required" in result["message"]

    @pytest.mark.asyncio
    async def test_text_to_speech_missing_api_key(self):
        """Test error when API key is missing"""
        mock_context = MagicMock()
        tool_config = {}
        
        result = await text_to_speech(
            "Hello world",
            tool_context=mock_context,
            tool_config=tool_config
        )
        
        assert result["status"] == "error"
        assert "GEMINI_API_KEY is required" in result["message"]

    @pytest.mark.asyncio
    async def test_text_to_speech_success(self):
        """Test successful text to speech generation"""
        mock_context = MagicMock()
        mock_inv_context = MagicMock()
        mock_inv_context.app_name = "test_app"
        mock_inv_context.user_id = "test_user"
        mock_inv_context.artifact_service = MagicMock()
        mock_context._invocation_context = mock_inv_context
        
        tool_config = {
            "gemini_api_key": "test_key",
            "model": "test-model"
        }
        
        with patch('src.solace_agent_mesh.agent.tools.audio_tools.genai.Client') as mock_client, \
             patch('src.solace_agent_mesh.agent.tools.audio_tools._generate_audio_with_gemini') as mock_generate, \
             patch('src.solace_agent_mesh.agent.tools.audio_tools._convert_pcm_to_mp3') as mock_convert, \
             patch('src.solace_agent_mesh.agent.tools.audio_tools._save_audio_artifact') as mock_save, \
             patch('src.solace_agent_mesh.agent.tools.audio_tools.get_original_session_id'):
            
            mock_generate.return_value = b'wav_data'
            mock_convert.return_value = b'mp3_data'
            mock_save.return_value = {"status": "success", "data_version": 1}
            
            result = await text_to_speech(
                "Hello world",
                tool_context=mock_context,
                tool_config=tool_config
            )
            
            assert result["status"] == "success"
            assert "output_filename" in result
            assert "output_version" in result

    @pytest.mark.asyncio
    async def test_text_to_speech_with_voice_name(self):
        """Test text to speech with specific voice name"""
        mock_context = MagicMock()
        mock_inv_context = MagicMock()
        mock_inv_context.app_name = "test_app"
        mock_inv_context.user_id = "test_user"
        mock_inv_context.artifact_service = MagicMock()
        mock_context._invocation_context = mock_inv_context
        
        tool_config = {"gemini_api_key": "test_key"}
        
        with patch('src.solace_agent_mesh.agent.tools.audio_tools.genai.Client'), \
             patch('src.solace_agent_mesh.agent.tools.audio_tools._generate_audio_with_gemini') as mock_generate, \
             patch('src.solace_agent_mesh.agent.tools.audio_tools._convert_pcm_to_mp3') as mock_convert, \
             patch('src.solace_agent_mesh.agent.tools.audio_tools._save_audio_artifact') as mock_save, \
             patch('src.solace_agent_mesh.agent.tools.audio_tools.get_original_session_id'):
            
            mock_generate.return_value = b'wav_data'
            mock_convert.return_value = b'mp3_data'
            mock_save.return_value = {"status": "success", "data_version": 1}
            
            result = await text_to_speech(
                "Hello world",
                voice_name="Puck",
                tool_context=mock_context,
                tool_config=tool_config
            )
            
            assert result["status"] == "success"
            assert result["voice_used"] == "Puck"


class TestMultiSpeakerTextToSpeech:
    """Tests for multi_speaker_text_to_speech async function"""

    @pytest.mark.asyncio
    async def test_multi_speaker_missing_context(self):
        """Test error when tool context is missing"""
        result = await multi_speaker_text_to_speech(
            "Speaker1: Hello\nSpeaker2: Hi",
            tool_context=None
        )
        
        assert result["status"] == "error"
        assert "ToolContext is missing" in result["message"]

    @pytest.mark.asyncio
    async def test_multi_speaker_empty_text(self):
        """Test error when conversation text is empty"""
        mock_context = MagicMock()
        result = await multi_speaker_text_to_speech("", tool_context=mock_context)
        
        assert result["status"] == "error"
        assert "Conversation text input is required" in result["message"]

    @pytest.mark.asyncio
    async def test_multi_speaker_missing_api_key(self):
        """Test error when API key is missing"""
        mock_context = MagicMock()
        tool_config = {}
        
        result = await multi_speaker_text_to_speech(
            "Speaker1: Hello",
            tool_context=mock_context,
            tool_config=tool_config
        )
        
        assert result["status"] == "error"
        assert "GEMINI_API_KEY is required" in result["message"]

    @pytest.mark.asyncio
    async def test_multi_speaker_success(self):
        """Test successful multi-speaker TTS generation"""
        mock_context = MagicMock()
        mock_inv_context = MagicMock()
        mock_inv_context.app_name = "test_app"
        mock_inv_context.user_id = "test_user"
        mock_inv_context.artifact_service = MagicMock()
        mock_context._invocation_context = mock_inv_context
        
        tool_config = {"gemini_api_key": "test_key"}
        speaker_configs = [
            {"name": "Speaker1", "voice": "Kore"},
            {"name": "Speaker2", "voice": "Puck"}
        ]
        
        with patch('src.solace_agent_mesh.agent.tools.audio_tools.genai.Client'), \
             patch('src.solace_agent_mesh.agent.tools.audio_tools._generate_audio_with_gemini') as mock_generate, \
             patch('src.solace_agent_mesh.agent.tools.audio_tools._convert_pcm_to_mp3') as mock_convert, \
             patch('src.solace_agent_mesh.agent.tools.audio_tools._save_audio_artifact') as mock_save, \
             patch('src.solace_agent_mesh.agent.tools.audio_tools.get_original_session_id'):
            
            mock_generate.return_value = b'wav_data'
            mock_convert.return_value = b'mp3_data'
            mock_save.return_value = {"status": "success", "data_version": 1}
            
            result = await multi_speaker_text_to_speech(
                "Speaker1: Hello\nSpeaker2: Hi there",
                speaker_configs=speaker_configs,
                tool_context=mock_context,
                tool_config=tool_config
            )
            
            assert result["status"] == "success"
            assert "output_filename" in result
            assert "speakers_used" in result


class TestConcatenateAudio:
    """Tests for concatenate_audio async function"""