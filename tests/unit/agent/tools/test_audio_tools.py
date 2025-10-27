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

import pytest
from unittest.mock import Mock, patch

from src.solace_agent_mesh.agent.tools.audio_tools import (
    VOICE_TONE_MAPPING,
    GENDER_TO_VOICE_MAPPING,
    ALL_AVAILABLE_VOICES,
    SUPPORTED_LANGUAGES,
    DEFAULT_VOICE,
    _get_effective_tone_voices,
    _get_gender_voices,
    _get_voice_for_speaker,
    _get_language_code,
    _create_voice_config,
    _create_multi_speaker_config
)


class TestVoiceMappingConstants:
    """Tests for voice mapping constants and data structures"""

    def test_voice_tone_mapping_structure(self):
        """Test that VOICE_TONE_MAPPING has expected structure"""
        assert isinstance(VOICE_TONE_MAPPING, dict)
        assert len(VOICE_TONE_MAPPING) > 0
        
        # Check some expected tones
        expected_tones = ["bright", "upbeat", "informative", "firm", "friendly"]
        for tone in expected_tones:
            assert tone in VOICE_TONE_MAPPING
            assert isinstance(VOICE_TONE_MAPPING[tone], list)
            assert len(VOICE_TONE_MAPPING[tone]) > 0

    def test_gender_to_voice_mapping_structure(self):
        """Test that GENDER_TO_VOICE_MAPPING has expected structure"""
        assert isinstance(GENDER_TO_VOICE_MAPPING, dict)
        
        # Check expected genders
        expected_genders = ["male", "female", "neutral"]
        for gender in expected_genders:
            assert gender in GENDER_TO_VOICE_MAPPING
            assert isinstance(GENDER_TO_VOICE_MAPPING[gender], list)
            assert len(GENDER_TO_VOICE_MAPPING[gender]) > 0

    def test_all_available_voices_populated(self):
        """Test that ALL_AVAILABLE_VOICES is properly populated"""
        assert isinstance(ALL_AVAILABLE_VOICES, list)
        assert len(ALL_AVAILABLE_VOICES) > 0
        
        # Should contain voices from both mappings
        tone_voices = set()
        for voices in VOICE_TONE_MAPPING.values():
            tone_voices.update(voices)
        
        gender_voices = set()
        for voices in GENDER_TO_VOICE_MAPPING.values():
            gender_voices.update(voices)
        
        all_voices_set = set(ALL_AVAILABLE_VOICES)
        assert tone_voices.issubset(all_voices_set)
        assert gender_voices.issubset(all_voices_set)

    def test_default_voice_in_available_voices(self):
        """Test that DEFAULT_VOICE is in ALL_AVAILABLE_VOICES"""
        assert DEFAULT_VOICE in ALL_AVAILABLE_VOICES

    def test_supported_languages_structure(self):
        """Test that SUPPORTED_LANGUAGES has expected structure"""
        assert isinstance(SUPPORTED_LANGUAGES, dict)
        assert len(SUPPORTED_LANGUAGES) > 0
        
        # Check some expected languages
        expected_languages = ["english", "spanish", "french", "german"]
        for lang in expected_languages:
            assert lang in SUPPORTED_LANGUAGES
            assert isinstance(SUPPORTED_LANGUAGES[lang], str)
            assert "-" in SUPPORTED_LANGUAGES[lang]  # Should be BCP-47 format


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


class TestAudioToolsEdgeCases:
    """Tests for edge cases and error conditions"""

    def test_voice_mappings_consistency(self):
        """Test that voice mappings are consistent"""
        # All voices in tone mapping should be strings
        for tone, voices in VOICE_TONE_MAPPING.items():
            assert isinstance(tone, str)
            assert isinstance(voices, list)
            for voice in voices:
                assert isinstance(voice, str)
                assert len(voice) > 0

        # All voices in gender mapping should be strings
        for gender, voices in GENDER_TO_VOICE_MAPPING.items():
            assert isinstance(gender, str)
            assert isinstance(voices, list)
            for voice in voices:
                assert isinstance(voice, str)
                assert len(voice) > 0

    def test_supported_languages_format(self):
        """Test that supported languages are in correct BCP-47 format"""
        for lang_name, lang_code in SUPPORTED_LANGUAGES.items():
            assert isinstance(lang_name, str)
            assert isinstance(lang_code, str)
            assert "-" in lang_code
            assert len(lang_code.split("-")) == 2
            
            # Language code should be lowercase, country code uppercase
            parts = lang_code.split("-")
            assert parts[0].islower()
            assert parts[1].isupper()

    def test_no_duplicate_voices_in_all_available(self):
        """Test that ALL_AVAILABLE_VOICES contains no duplicates"""
        assert len(ALL_AVAILABLE_VOICES) == len(set(ALL_AVAILABLE_VOICES))

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