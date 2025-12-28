"""
Collection of Python tools for audio processing and text-to-speech generation.
"""

import logging
import asyncio
import io
import json
import os
import random
import tempfile
import uuid
import wave
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from google import genai
from google.genai import types as adk_types
from google.adk.tools import ToolContext
from pydub import AudioSegment

from ...agent.utils.artifact_helpers import (
    load_artifact_content_or_metadata,
    ensure_correct_extension,
)
from ...agent.utils.context_helpers import get_original_session_id

from .tool_definition import BuiltinTool
from .tool_result import ToolResult, DataObject, DataDisposition
from .registry import tool_registry

log = logging.getLogger(__name__)

VOICE_TONE_MAPPING = {
    "bright": ["Zephyr", "Autonoe"],
    "upbeat": ["Puck", "Laomedeia"],
    "informative": ["Charon", "Rasalgethi"],
    "firm": ["Kore", "Orus", "Alnilam"],
    "excitable": ["Fenrir"],
    "youthful": ["Leda"],
    "breezy": ["Aoede"],
    "easy-going": ["Callirrhoe", "Umbriel"],
    "breathy": ["Enceladus"],
    "clear": ["Iapetus", "Erinome"],
    "smooth": ["Algieba", "Despina"],
    "gravelly": ["Algenib"],
    "soft": ["Achernar"],
    "even": ["Schedar"],
    "mature": ["Gacrux"],
    "forward": ["Pulcherrima"],
    "friendly": ["Achird"],
    "casual": ["Zubenelgenubi"],
    "gentle": ["Vindemiatrix"],
    "lively": ["Sadachbia"],
    "knowledgeable": ["Sadaltager"],
    "warm": ["Sulafat"],
}

GENDER_TO_VOICE_MAPPING = {
    "male": [
        "Puck",
        "Charon",
        "Orus",
        "Enceladus",
        "Iapetus",
        "Algieba",
        "Algenib",
        "Alnilam",
        "Schedar",
        "Achird",
        "Zubenelgenubi",
        "Sadachbia",
        "Sadaltager",
    ],
    "female": [
        "Zephyr",
        "Kore",
        "Leda",
        "Aoede",
        "Callirrhoe",
        "Autonoe",
        "Despina",
        "Erinome",
        "Laomedeia",
        "Achernar",
        "Gacrux",
        "Pulcherrima",
        "Vindemiatrix",
        "Sulafat",
    ],
    "neutral": [
        "Fenrir",
        "Umbriel",
        "Rasalgethi",
    ],
}

_all_voices_set = set(
    voice for voices_in_tone in VOICE_TONE_MAPPING.values() for voice in voices_in_tone
)
_all_voices_set.update(
    voice
    for voices_in_gender in GENDER_TO_VOICE_MAPPING.values()
    for voice in voices_in_gender
)
ALL_AVAILABLE_VOICES = list(_all_voices_set)

if not ALL_AVAILABLE_VOICES:
    ALL_AVAILABLE_VOICES = [
        "Kore",
        "Puck",
        "Zephyr",
        "Charon",
        "Rasalgethi",
        "Alnilam",
        "Fenrir",
        "Leda",
        "Aoede",
        "Callirrhoe",
        "Umbriel",
        "Enceladus",
        "Iapetus",
        "Erinome",
        "Algieba",
        "Despina",
        "Algenib",
        "Achernar",
        "Schedar",
        "Gacrux",
        "Pulcherrima",
        "Achird",
        "Zubenelgenubi",
        "Vindemiatrix",
        "Sadachbia",
        "Sadaltager",
        "Sulafat",
        "Autonoe",
        "Laomedeia",
        "Orus",
    ]


SUPPORTED_LANGUAGES = {
    "arabic": "ar-EG",
    "arabic_egyptian": "ar-EG",
    "german": "de-DE",
    "english": "en-US",
    "english_us": "en-US",
    "english_india": "en-IN",
    "spanish": "es-US",
    "spanish_us": "es-US",
    "french": "fr-FR",
    "hindi": "hi-IN",
    "indonesian": "id-ID",
    "italian": "it-IT",
    "japanese": "ja-JP",
    "korean": "ko-KR",
    "portuguese": "pt-BR",
    "portuguese_brazil": "pt-BR",
    "russian": "ru-RU",
    "dutch": "nl-NL",
    "polish": "pl-PL",
    "thai": "th-TH",
    "turkish": "tr-TR",
    "vietnamese": "vi-VN",
    "romanian": "ro-RO",
    "ukrainian": "uk-UA",
    "bengali": "bn-BD",
    "marathi": "mr-IN",
    "tamil": "ta-IN",
    "telugu": "te-IN",
}

from typing import Set

DEFAULT_VOICE = "Kore"


def _get_effective_tone_voices(
    tone: Optional[str], voice_tone_mapping: Optional[Dict[str, List[str]]] = None
) -> Optional[List[str]]:
    """Helper to get voices for a tone, considering aliases."""
    if not tone:
        return None
    mapping = voice_tone_mapping or VOICE_TONE_MAPPING
    tone_lower = tone.lower().strip()
    tone_aliases = {
        "professional": "firm",
        "business": "firm",
        "corporate": "firm",
        "cheerful": "upbeat",
        "happy": "upbeat",
        "energetic": "excitable",
        "calm": "soft",
        "relaxed": "easy-going",
        "serious": "informative",
        "educational": "knowledgeable",
        "teaching": "knowledgeable",
        "conversational": "casual",
        "natural": "friendly",
        "welcoming": "warm",
    }
    effective_tone = tone_aliases.get(tone_lower, tone_lower)
    return mapping.get(effective_tone)


def _get_gender_voices(
    gender: Optional[str], gender_voice_mapping: Optional[Dict[str, List[str]]] = None
) -> Optional[List[str]]:
    """Helper to get voices for a gender."""
    if not gender:
        return None
    mapping = gender_voice_mapping or GENDER_TO_VOICE_MAPPING
    return mapping.get(gender.lower().strip())


def _get_voice_for_speaker(
    gender: Optional[str],
    tone: Optional[str],
    used_voices_in_current_call: Set[str],
    voice_tone_mapping: Optional[Dict[str, List[str]]] = None,
    gender_voice_mapping: Optional[Dict[str, List[str]]] = None,
) -> str:
    """
    Selects a voice based on desired gender and/or tone, prioritizing uniqueness.

    Selection Priority:
    1. Unique voice matching both specified gender and tone.
    2. Unique voice matching specified gender (if tone match failed or tone not specified).
    3. Unique voice matching specified tone (if gender match failed or gender not specified).
    4. Any unique voice from the global pool.
    5. If all unique options exhausted (reuse necessary):
        a. Voice matching both specified gender and tone.
        b. Voice matching specified gender.
        c. Voice matching specified tone.
        d. Any voice from the global pool.
    6. Fallback to DEFAULT_VOICE ("Kore").

    Args:
        gender: The desired gender ("male", "female", "neutral").
        tone: The desired tone (e.g., "friendly", "professional").
        used_voices_in_current_call: A set of voice names already used.
        voice_tone_mapping: Optional custom tone-to-voice mapping.
        gender_voice_mapping: Optional custom gender-to-voice mapping.

    Returns:
        A voice name string.
    """
    log_identifier_select = "[AudioTools:_get_voice_for_speaker]"
    log.debug(
        "%s Selecting voice for gender='%s', tone='%s', used_voices=%s",
        log_identifier_select,
        gender,
        tone,
        used_voices_in_current_call,
    )

    candidate_pool = list(ALL_AVAILABLE_VOICES)

    gender_specific_voices = None
    if gender:
        gender_specific_voices = _get_gender_voices(gender, gender_voice_mapping)
        if gender_specific_voices:
            candidate_pool = [v for v in candidate_pool if v in gender_specific_voices]
            log.debug(
                "%s Filtered by gender '%s'. Candidates: %s",
                log_identifier_select,
                gender,
                candidate_pool,
            )
        else:
            log.warning(
                "%s Gender '%s' not found in mapping or has no voices. Gender filter ignored for now.",
                log_identifier_select,
                gender,
            )
            gender_specific_voices = None

    tone_specific_voices = None
    if tone:
        voices_for_tone = _get_effective_tone_voices(tone, voice_tone_mapping)
        if voices_for_tone:
            tone_specific_voices = voices_for_tone
            candidate_pool = [v for v in candidate_pool if v in voices_for_tone]
            log.debug(
                "%s Filtered by tone '%s'. Candidates: %s",
                log_identifier_select,
                tone,
                candidate_pool,
            )
        else:
            log.warning(
                "%s Tone '%s' not found in mapping or has no voices. Tone filter ignored.",
                log_identifier_select,
                tone,
            )
            tone_specific_voices = None

    available_unique_voices = [
        v for v in candidate_pool if v not in used_voices_in_current_call
    ]
    if available_unique_voices:
        selected = random.choice(available_unique_voices)
        log.info(
            "%s Selected unique voice '%s' from gender/tone filtered pool.",
            log_identifier_select,
            selected,
        )
        return selected

    log.debug(
        "%s No unique voice in primary filtered pool. Trying fallbacks for uniqueness.",
        log_identifier_select,
    )
    if gender_specific_voices:
        available_gender_unique = [
            v for v in gender_specific_voices if v not in used_voices_in_current_call
        ]
        if available_gender_unique:
            selected = random.choice(available_gender_unique)
            log.info(
                "%s Selected unique voice '%s' from gender-only pool (tone constraint relaxed).",
                log_identifier_select,
                selected,
            )
            return selected
    if tone_specific_voices:
        available_tone_unique = [
            v for v in tone_specific_voices if v not in used_voices_in_current_call
        ]
        if available_tone_unique:
            selected = random.choice(available_tone_unique)
            log.info(
                "%s Selected unique voice '%s' from tone-only pool (gender constraint relaxed or not specified).",
                log_identifier_select,
                selected,
            )
            return selected
    globally_available_unique = [
        v for v in ALL_AVAILABLE_VOICES if v not in used_voices_in_current_call
    ]
    if globally_available_unique:
        selected = random.choice(globally_available_unique)
        log.info(
            "%s Selected unique voice '%s' from global pool (all constraints relaxed).",
            log_identifier_select,
            selected,
        )
        return selected

    log.warning("%s All voices are used. Reusing a voice.", log_identifier_select)
    if candidate_pool:
        selected = random.choice(candidate_pool)
        log.info(
            "%s Reusing voice '%s' from gender/tone filtered pool.",
            log_identifier_select,
            selected,
        )
        return selected
    if gender_specific_voices:
        selected = random.choice(gender_specific_voices)
        log.info(
            "%s Reusing voice '%s' from gender-only pool.",
            log_identifier_select,
            selected,
        )
        return selected
    if tone_specific_voices:
        selected = random.choice(tone_specific_voices)
        log.info(
            "%s Reusing voice '%s' from tone-only pool.",
            log_identifier_select,
            selected,
        )
        return selected
    if ALL_AVAILABLE_VOICES:
        selected = random.choice(ALL_AVAILABLE_VOICES)
        log.info(
            "%s Reusing voice '%s' from global pool.", log_identifier_select, selected
        )
        return selected

    log.error(
        "%s No voices available in any mapping or pool. Using default '%s'.",
        log_identifier_select,
        DEFAULT_VOICE,
    )
    return DEFAULT_VOICE


def _get_language_code(language: str) -> str:
    """
    Get BCP-47 language code from language name or code.

    Args:
        language: Language name or BCP-47 code

    Returns:
        BCP-47 language code, defaults to "en-US"
    """
    if not language:
        return "en-US"

    language_lower = language.lower().strip()

    if "-" in language_lower and len(language_lower) >= 5:
        return language

    if language_lower in SUPPORTED_LANGUAGES:
        return SUPPORTED_LANGUAGES[language_lower]

    log.warning(f"[AudioTools] Unknown language '{language}', using default 'en-US'")
    return "en-US"


def _create_voice_config(voice_name: str) -> adk_types.VoiceConfig:
    """Create a VoiceConfig for single-voice TTS."""
    return adk_types.VoiceConfig(
        prebuilt_voice_config=adk_types.PrebuiltVoiceConfig(voice_name=voice_name)
    )


def _create_multi_speaker_config(
    speaker_configs: List[Dict[str, str]],
) -> adk_types.MultiSpeakerVoiceConfig:
    """Create a MultiSpeakerVoiceConfig for multi-speaker TTS."""
    speaker_voice_configs = []

    for config in speaker_configs:
        speaker_name = config.get("name", "Speaker")
        voice_name = config.get("voice", "Kore")

        speaker_voice_config = adk_types.SpeakerVoiceConfig(
            speaker=speaker_name, voice_config=_create_voice_config(voice_name)
        )
        speaker_voice_configs.append(speaker_voice_config)

    return adk_types.MultiSpeakerVoiceConfig(
        speaker_voice_configs=speaker_voice_configs
    )


async def _generate_audio_with_gemini(
    client: genai.Client,
    prompt: str,
    speech_config: adk_types.SpeechConfig,
    model: str = "gemini-2.5-flash-preview-tts",
    language: str = "en-US",
) -> bytes:
    """
    Shared function for generating audio using Gemini API.

    Args:
        client: Gemini client instance
        prompt: Text prompt for TTS
        speech_config: Speech configuration (single or multi-speaker)
        model: Gemini model to use
        language: BCP-47 language code

    Returns:
        Raw audio data as bytes
    """
    config = adk_types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=speech_config,
    )

    if hasattr(config, "language"):
        config.language = language

    response = await asyncio.to_thread(
        client.models.generate_content, model=model, contents=prompt, config=config
    )

    if (
        not response
        or not response.candidates
        or not response.candidates[0].content.parts
    ):
        raise ValueError("Gemini API did not return valid audio data")

    audio_data = response.candidates[0].content.parts[0].inline_data.data
    if not audio_data:
        raise ValueError("No audio data received from Gemini API")

    return audio_data


def _create_wav_file(
    filename: str,
    pcm_data: bytes,
    channels: int = 1,
    rate: int = 24000,
    sample_width: int = 2,
):
    """Create a proper WAV file from PCM data (based on working example)."""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm_data)


async def _convert_pcm_to_mp3(pcm_data: bytes) -> bytes:
    """
    Shared function for converting raw PCM data to MP3 format.

    Args:
        pcm_data: Raw PCM audio data from Gemini API

    Returns:
        MP3 audio data as bytes
    """
    wav_temp_path = None
    mp3_temp_path = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_temp:
            wav_temp_path = wav_temp.name

        await asyncio.to_thread(_create_wav_file, wav_temp_path, pcm_data)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as mp3_temp:
            mp3_temp_path = mp3_temp.name

        audio = await asyncio.to_thread(AudioSegment.from_wav, wav_temp_path)
        await asyncio.to_thread(audio.export, mp3_temp_path, format="mp3")

        with open(mp3_temp_path, "rb") as mp3_file:
            mp3_data = mp3_file.read()

        return mp3_data

    finally:
        if wav_temp_path:
            try:
                os.remove(wav_temp_path)
            except OSError:
                pass
        if mp3_temp_path:
            try:
                os.remove(mp3_temp_path)
            except OSError:
                pass


async def select_voice(
    gender: Optional[str] = None,
    tone: Optional[str] = None,
    exclude_voices: Optional[List[str]] = None,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """
    Selects a suitable voice name based on criteria like gender and tone.
    Use this to get a consistent voice name that can be passed to the `text_to_speech` tool for multiple calls.

    Args:
        gender: Optional desired gender for the voice ("male", "female", "neutral").
        tone: Optional tone preference (e.g., "friendly", "professional", "warm").
        exclude_voices: Optional list of voice names to exclude from the selection.
        tool_context: ADK tool context.
        tool_config: Configuration including voice mappings.

    Returns:
        ToolResult with selected voice name.
    """
    log_identifier = "[AudioTools:select_voice]"
    log.info(
        f"{log_identifier} Selecting voice for gender='{gender}', tone='{tone}', excluding='{exclude_voices}'"
    )

    try:
        config = tool_config or {}
        voice_tone_mapping = config.get("voice_tone_mapping", VOICE_TONE_MAPPING)
        gender_voice_mapping = config.get(
            "gender_voice_mapping", GENDER_TO_VOICE_MAPPING
        )

        used_voices = set(exclude_voices) if exclude_voices else set()

        selected_voice = _get_voice_for_speaker(
            gender=gender,
            tone=tone,
            used_voices_in_current_call=used_voices,
            voice_tone_mapping=voice_tone_mapping,
            gender_voice_mapping=gender_voice_mapping,
        )

        log.info(f"{log_identifier} Selected voice: {selected_voice}")

        return ToolResult.ok(
            f"Successfully selected voice '{selected_voice}'.",
            data={"voice_name": selected_voice},
        )

    except Exception as e:
        log.exception(f"{log_identifier} Unexpected error in select_voice: {e}")
        return ToolResult.error(f"An unexpected error occurred: {e}")


async def text_to_speech(
    text: str,
    output_filename: Optional[str] = None,
    voice_name: Optional[str] = None,
    gender: Optional[str] = None,
    tone: Optional[str] = None,
    language: Optional[str] = None,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """
    Converts text to speech using Gemini TTS API and saves as MP3 artifact.

    Args:
        text: The text to convert to speech.
        output_filename: Optional filename for the output MP3.
        voice_name: Optional specific voice name (e.g., "Kore", "Puck"). Overrides gender and tone.
        gender: Optional desired gender for the voice ("male", "female", "neutral").
                Used if 'voice_name' is not provided.
        tone: Optional tone preference (e.g., "friendly", "professional", "warm").
              Used if 'voice_name' is not provided, considered after 'gender'.
        language: Optional language code (e.g., "en-US", "fr-FR", "ja-JP").
        tool_context: ADK tool context.
        tool_config: Configuration including API key, model settings, and voice mappings.

    Returns:
        ToolResult with output artifact details.
    """
    log_identifier = "[AudioTools:text_to_speech]"

    if not tool_context:
        return ToolResult.error("ToolContext is missing")

    if not text or not text.strip():
        return ToolResult.error("Text input is required")

    try:
        log.info(f"{log_identifier} Processing TTS request for text: '{text[:50]}...'")

        config = tool_config or {}
        api_key = config.get("gemini_api_key")
        model = config.get("model", "gemini-2.5-flash-preview-tts")
        default_voice = config.get("voice_name", DEFAULT_VOICE)
        default_language = config.get("language", "en-US")
        voice_tone_mapping = config.get("voice_tone_mapping", VOICE_TONE_MAPPING)
        gender_voice_mapping = config.get(
            "gender_voice_mapping", GENDER_TO_VOICE_MAPPING
        )

        if not api_key:
            return ToolResult.error("GEMINI_API_KEY is required in tool configuration")

        final_voice = voice_name
        if not final_voice:
            final_voice = _get_voice_for_speaker(
                gender=gender,
                tone=tone,
                used_voices_in_current_call=set(),
                voice_tone_mapping=voice_tone_mapping,
                gender_voice_mapping=gender_voice_mapping,
            )
            log.info(
                f"{log_identifier} Selected voice '{final_voice}' for gender='{gender}', tone='{tone}'"
            )
        else:
            log.info(
                f"{log_identifier} Using specified voice_name '{final_voice}'. Gender/tone selection skipped."
            )

        if not final_voice:
            final_voice = default_voice
            log.warning(
                f"{log_identifier} Voice selection resulted in None, using default '{default_voice}'."
            )

        final_language = _get_language_code(language or default_language)

        client = genai.Client(api_key=api_key)

        voice_config = _create_voice_config(final_voice)
        speech_config = adk_types.SpeechConfig(voice_config=voice_config)

        log.info(
            f"{log_identifier} Generating audio with voice '{final_voice}' and language '{final_language}'"
        )
        wav_data = await _generate_audio_with_gemini(
            client=client,
            prompt=f"Say in a clear voice: {text}",
            speech_config=speech_config,
            model=model,
            language=final_language,
        )

        log.info(f"{log_identifier} Converting audio to MP3 format")
        mp3_data = await _convert_pcm_to_mp3(wav_data)

        final_filename = output_filename
        if not final_filename:
            final_filename = f"tts_audio_{uuid.uuid4()}.mp3"
        elif not final_filename.lower().endswith(".mp3"):
            final_filename = f"{final_filename}.mp3"

        metadata = {
            "description": f"Text-to-speech audio generated from text input. Used voice: {final_voice}\nSource text: {text[:1500]}",
            "source_text": text[:500],
            "voice_name": final_voice,
            "language": final_language,
            "model": model,
            "generation_tool": "text_to_speech",
            "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if voice_name:
            metadata["requested_voice_name"] = voice_name
        if gender:
            metadata["requested_gender"] = gender
        if tone:
            metadata["requested_tone"] = tone
        if language:
            metadata["requested_language"] = language

        log.info(f"{log_identifier} Returning audio as DataObject for artifact storage")

        return ToolResult.ok(
            "Text-to-speech audio generated successfully.",
            data={
                "voice_used": final_voice,
                "language_used": final_language,
            },
            data_objects=[
                DataObject(
                    name=final_filename,
                    content=mp3_data,
                    mime_type="audio/mpeg",
                    disposition=DataDisposition.ARTIFACT,
                    description=f"Text-to-speech audio. Voice: {final_voice}. Text: {text[:100]}...",
                    metadata=metadata,
                )
            ],
        )

    except ValueError as ve:
        log.error(f"{log_identifier} Value error: {ve}")
        return ToolResult.error(str(ve))
    except IOError as ioe:
        log.error(f"{log_identifier} IO error: {ioe}")
        return ToolResult.error(str(ioe))
    except Exception as e:
        log.exception(f"{log_identifier} Unexpected error in text_to_speech: {e}")
        return ToolResult.error(f"An unexpected error occurred: {e}")


async def multi_speaker_text_to_speech(
    conversation_text: str,
    output_filename: Optional[str] = None,
    speaker_configs: Optional[List[Dict[str, str]]] = None,
    language: Optional[str] = None,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """
    Converts conversation text with speaker labels to speech using multiple voices.

    Args:
        conversation_text: Text with speaker labels (e.g., "Speaker1: Hello\\nSpeaker2: Hi there").
        output_filename: Optional filename for the output MP3.
        speaker_configs: Optional list of speaker configurations. Each item is a dictionary:
                         `{"name": "Speaker1", "voice": "Kore", "gender": "female", "tone": "firm"}`.
                         - `name` (str): The speaker's name as it appears in `conversation_text`.
                         - `voice` (Optional[str]): Specific voice name to use. Overrides gender/tone.
                         - `gender` (Optional[str]): Desired gender ("male", "female", "neutral").
                         - `tone` (Optional[str]): Desired tone (e.g., "friendly").
                         If only `gender` and/or `tone` are provided, a voice is selected.
                         If no config for a speaker in text, or if speaker_configs is empty,
                         default speakers from tool_config are used, or a default voice is assigned.
        language: Optional language code (e.g., "en-US", "fr-FR", "ja-JP").
        tool_context: ADK tool context.
        tool_config: Configuration including API key, model, default speakers, and voice mappings.

    Returns:
        ToolResult with output artifact details.
    """
    log_identifier = "[AudioTools:multi_speaker_text_to_speech]"

    if not tool_context:
        return ToolResult.error("ToolContext is missing")

    if not conversation_text or not conversation_text.strip():
        return ToolResult.error("Conversation text input is required")

    try:
        log.info(
            f"{log_identifier} Processing multi-speaker TTS request for text: '{conversation_text[:50]}...'"
        )

        config = tool_config or {}
        api_key = config.get("gemini_api_key")
        model = config.get("model", "gemini-2.5-flash-preview-tts")
        default_language = config.get("language", "en-US")
        default_speakers = config.get(
            "default_speakers",
            [
                {"name": "Speaker1", "voice": "Kore"},
                {
                    "name": "Speaker2",
                    "voice": "Puck",
                    "gender": "male",
                    "tone": "upbeat",
                },
                {
                    "name": "Speaker3",
                    "voice": "Zephyr",
                    "gender": "female",
                    "tone": "bright",
                },
            ],
        )
        voice_tone_mapping = config.get("voice_tone_mapping", VOICE_TONE_MAPPING)
        gender_voice_mapping = config.get(
            "gender_voice_mapping", GENDER_TO_VOICE_MAPPING
        )

        if not api_key:
            return ToolResult.error("GEMINI_API_KEY is required in tool configuration")

        final_speaker_configs = []
        used_voices_in_current_call: Set[str] = set()

        configs_to_process = speaker_configs if speaker_configs else default_speakers
        if not configs_to_process and conversation_text:
            log.warning(
                "%s No speaker_configs and no default_speakers. Creating a default speaker.",
                log_identifier,
            )
            configs_to_process = [
                {"name": "Speaker1", "gender": "neutral", "tone": "neutral"}
            ]

        for i, config_item in enumerate(configs_to_process):
            speaker_name = config_item.get("name", f"Speaker{i+1}")
            voice_name_from_config = config_item.get("voice")
            gender_from_config = config_item.get("gender")
            tone_from_config = config_item.get("tone")
            final_voice_for_speaker = None

            if voice_name_from_config:
                final_voice_for_speaker = voice_name_from_config
                log.info(
                    f"{log_identifier} Using specified voice '{final_voice_for_speaker}' for speaker '{speaker_name}'."
                )
            else:
                final_voice_for_speaker = _get_voice_for_speaker(
                    gender=gender_from_config,
                    tone=tone_from_config,
                    used_voices_in_current_call=used_voices_in_current_call,
                    voice_tone_mapping=voice_tone_mapping,
                    gender_voice_mapping=gender_voice_mapping,
                )
                log.info(
                    f"{log_identifier} Selected voice '{final_voice_for_speaker}' for speaker '{speaker_name}' (gender='{gender_from_config}', tone='{tone_from_config}')."
                )

            if not final_voice_for_speaker:
                final_voice_for_speaker = DEFAULT_VOICE
                log.warning(
                    f"{log_identifier} Voice selection for speaker '{speaker_name}' resulted in None, using default '{DEFAULT_VOICE}'."
                )

            final_speaker_configs.append(
                {"name": speaker_name, "voice": final_voice_for_speaker}
            )
            if final_voice_for_speaker:
                used_voices_in_current_call.add(final_voice_for_speaker)

        final_language = _get_language_code(language or default_language)

        client = genai.Client(api_key=api_key)

        multi_speaker_config = _create_multi_speaker_config(final_speaker_configs)
        speech_config = adk_types.SpeechConfig(
            multi_speaker_voice_config=multi_speaker_config
        )

        log.info(
            f"{log_identifier} Generating multi-speaker audio with {len(final_speaker_configs)} speakers and language '{final_language}'"
        )
        wav_data = await _generate_audio_with_gemini(
            client=client,
            prompt=f"TTS the following conversation: {conversation_text}",
            speech_config=speech_config,
            model=model,
            language=final_language,
        )

        log.info(f"{log_identifier} Converting audio to MP3 format")
        mp3_data = await _convert_pcm_to_mp3(wav_data)

        final_filename = output_filename
        if not final_filename:
            final_filename = f"multi_speaker_tts_{uuid.uuid4()}.mp3"
        elif not final_filename.lower().endswith(".mp3"):
            final_filename = f"{final_filename}.mp3"

        voice_info = ", ".join(
            [f"{s['name']} ({s['voice']})" for s in final_speaker_configs]
        )

        metadata = {
            "description": f"Multi-speaker text-to-speech audio generated from conversation. Voices used: {voice_info}\nSource text: {conversation_text[:1500]}...",
            "source_text": conversation_text[:500],
            "language": final_language,
            "model": model,
            "generation_tool": "multi_speaker_text_to_speech",
            "generation_timestamp": datetime.now(timezone.utc).isoformat(),
            "speaker_count": len(final_speaker_configs),
            "speakers_used_details": json.dumps(final_speaker_configs),
        }

        if language:
            metadata["requested_language"] = language
        if speaker_configs:
            metadata["requested_speaker_configs"] = json.dumps(speaker_configs)

        speaker_summary = ", ".join(
            [f"{s['name']} ({s['voice']})" for s in final_speaker_configs]
        )

        log.info(f"{log_identifier} Returning audio as DataObject for artifact storage")

        return ToolResult.ok(
            f"Multi-speaker text-to-speech audio generated successfully. Speakers: {speaker_summary}",
            data={
                "speakers_used": speaker_summary,
                "language_used": final_language,
            },
            data_objects=[
                DataObject(
                    name=final_filename,
                    content=mp3_data,
                    mime_type="audio/mpeg",
                    disposition=DataDisposition.ARTIFACT,
                    description=f"Multi-speaker TTS audio. Speakers: {speaker_summary}. Text: {conversation_text[:100]}...",
                    metadata=metadata,
                )
            ],
        )

    except ValueError as ve:
        log.error(f"{log_identifier} Value error: {ve}")
        return ToolResult.error(str(ve))
    except IOError as ioe:
        log.error(f"{log_identifier} IO error: {ioe}")
        return ToolResult.error(str(ioe))
    except Exception as e:
        log.exception(
            f"{log_identifier} Unexpected error in multi_speaker_text_to_speech: {e}"
        )
        return ToolResult.error(f"An unexpected error occurred: {e}")


def _is_supported_audio_format_for_transcription(filename: str) -> bool:
    """Check if the audio format is supported for transcription."""
    ext = os.path.splitext(filename)[1].lower()
    supported_formats = {".wav", ".mp3"}
    return ext in supported_formats


def _get_audio_mime_type(filename: str) -> str:
    """Get MIME type from audio file extension."""
    ext = os.path.splitext(filename)[1].lower()
    mime_mapping = {".wav": "audio/wav", ".mp3": "audio/mpeg"}
    return mime_mapping.get(ext, "audio/wav")


async def concatenate_audio(
    clips_to_join: List[Dict[str, Any]],
    output_filename: Optional[str] = None,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """
    Combines multiple audio artifacts in a specified order into a single audio file.
    Allows for custom pause durations between each clip.

    Args:
        clips_to_join: An ordered list of clip objects to be joined. Each object should contain:
                       - `filename` (str): The artifact filename of the audio clip (with optional :version).
                       - `pause_after_ms` (Optional[int]): The duration of silence, in milliseconds,
                         to insert *after* this clip. If omitted, a default pause will be used. The gap between
                         two people speaking in a conversation is typically around 250ms.
        output_filename: Optional. The desired filename for the final combined audio artifact.
        tool_context: The context provided by the ADK framework.
        tool_config: Configuration dictionary.

    Returns:
        ToolResult with output artifact details.
    """
    log_identifier = "[AudioTools:concatenate_audio]"
    if not tool_context:
        return ToolResult.error("ToolContext is missing")
    if not clips_to_join:
        return ToolResult.error("The 'clips_to_join' list cannot be empty.")

    try:
        inv_context = tool_context._invocation_context
        app_name = inv_context.app_name
        user_id = inv_context.user_id
        session_id = get_original_session_id(inv_context)
        artifact_service = inv_context.artifact_service
        host_component = getattr(inv_context.agent, "host_component", None)

        if not artifact_service:
            raise ValueError("ArtifactService is not available in the context.")

        config = tool_config or {}
        default_pause_ms = config.get("default_pause_ms", 250)

        combined_audio = None
        source_filenames = []

        for i, clip_info in enumerate(clips_to_join):
            clip_filename_with_version = clip_info.get("filename")
            if not clip_filename_with_version:
                raise ValueError(
                    f"Clip at index {i} is missing the required 'filename' key."
                )

            source_filenames.append(clip_filename_with_version)

            # Parse filename:version format (rsplit to handle colons in filenames)
            parts = clip_filename_with_version.rsplit(":", 1)
            if len(parts) == 2 and parts[1].isdigit():
                filename_base = parts[0]
                version_to_load = int(parts[1])
            else:
                filename_base = clip_filename_with_version
                version_to_load = "latest"

            load_result = await load_artifact_content_or_metadata(
                artifact_service=artifact_service,
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename_base,
                version=version_to_load,
                return_raw_bytes=True,
                component=host_component,
                log_identifier_prefix=f"{log_identifier}[LoadClip:{clip_filename_with_version}]",
            )

            if load_result.get("status") != "success":
                raise FileNotFoundError(
                    f"Failed to load audio clip '{clip_filename_with_version}': {load_result.get('message')}"
                )

            audio_bytes = load_result.get("raw_bytes")
            mime_type = load_result.get("mime_type", "audio/mpeg")

            audio_format = "mp3"
            if "wav" in mime_type:
                audio_format = "wav"
            elif "mpeg" in mime_type:
                audio_format = "mp3"

            log.debug(
                f"{log_identifier} Loading clip '{clip_filename_with_version}' with format '{audio_format}'"
            )

            clip_segment = await asyncio.to_thread(
                AudioSegment.from_file, io.BytesIO(audio_bytes), format=audio_format
            )

            if combined_audio is None:
                combined_audio = clip_segment
            else:
                combined_audio += clip_segment

            if i < len(clips_to_join) - 1:
                pause_ms = clip_info.get("pause_after_ms", default_pause_ms)
                if pause_ms > 0:
                    pause_segment = AudioSegment.silent(duration=pause_ms)
                    combined_audio += pause_segment
                    log.debug(
                        f"{log_identifier} Added {pause_ms}ms pause after '{clip_filename_with_version}'."
                    )

        if combined_audio is None:
            return ToolResult.error("No audio clips were successfully processed.")

        output_buffer = io.BytesIO()
        await asyncio.to_thread(combined_audio.export, output_buffer, format="mp3")
        mp3_data = output_buffer.getvalue()

        final_filename = output_filename
        if not final_filename:
            final_filename = f"concatenated_audio_{uuid.uuid4()}.mp3"
        elif not final_filename.lower().endswith(".mp3"):
            final_filename = f"{final_filename}.mp3"

        metadata = {
            "description": f"Concatenated audio created from {len(clips_to_join)} clips.",
            "source_clips": source_filenames,
            "generation_tool": "concatenate_audio",
            "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        log.info(f"{log_identifier} Returning concatenated audio as DataObject for artifact storage")

        return ToolResult.ok(
            "Audio clips concatenated successfully.",
            data={
                "clips_count": len(clips_to_join),
                "source_clips": source_filenames,
            },
            data_objects=[
                DataObject(
                    name=final_filename,
                    content=mp3_data,
                    mime_type="audio/mpeg",
                    disposition=DataDisposition.ARTIFACT,
                    description=f"Concatenated audio from {len(clips_to_join)} clips.",
                    metadata=metadata,
                )
            ],
        )

    except FileNotFoundError as e:
        log.warning(f"{log_identifier} File not found error: {e}")
        return ToolResult.error(str(e))
    except ValueError as ve:
        log.error(f"{log_identifier} Value error: {ve}")
        return ToolResult.error(str(ve))
    except IOError as ioe:
        log.error(f"{log_identifier} IO error: {ioe}")
        return ToolResult.error(str(ioe))
    except Exception as e:
        log.exception(f"{log_identifier} Unexpected error in concatenate_audio: {e}")
        return ToolResult.error(f"An unexpected error occurred: {e}")


async def transcribe_audio(
    input_audio: str,  # Artifact filename - wrapper converts to Artifact object
    output_filename: Optional[str] = None,
    description: Optional[str] = None,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """
    Transcribes an audio recording and saves the transcription as a text artifact.

    Args:
        input_audio: The artifact filename (framework pre-loads as Artifact object).
        output_filename: Optional filename for the transcription text file (without extension).
        description: Optional description of the transcription for metadata.
        tool_context: The context provided by the ADK framework.
        tool_config: Configuration dictionary containing model, api_base, api_key.

    Returns:
        ToolResult with transcription artifact details.

    Note:
        The input_audio parameter is declared as str for ADK schema compatibility,
        but the framework wrapper pre-loads it as an Artifact object with .filename,
        .as_bytes(), .mime_type attributes available at runtime.
    """
    log_identifier = f"[AudioTools:transcribe_audio:{input_audio.filename}]"

    try:
        current_tool_config = tool_config if tool_config is not None else {}

        model_name = current_tool_config.get("model")
        api_key = current_tool_config.get("api_key")
        api_base = current_tool_config.get("api_base")

        if not model_name:
            raise ValueError("'model' configuration is missing in tool_config.")
        if not api_key:
            raise ValueError("'api_key' configuration is missing in tool_config.")
        if not api_base:
            raise ValueError("'api_base' configuration is missing in tool_config.")

        log.debug(f"{log_identifier} Using model: {model_name}, API base: {api_base}")

        # Use pre-loaded artifact data
        audio_filename = input_audio.filename
        audio_version = input_audio.version
        audio_mime_type = input_audio.mime_type
        audio_bytes = input_audio.as_bytes()
        source_audio_metadata = input_audio.metadata or {}

        if not _is_supported_audio_format_for_transcription(audio_filename):
            raise ValueError("Unsupported audio format. Supported formats: .wav, .mp3")

        log.debug(f"{log_identifier} Using pre-loaded audio: {len(audio_bytes)} bytes")

        temp_file_path = None
        try:
            file_ext = os.path.splitext(audio_filename)[1]

            with tempfile.NamedTemporaryFile(
                suffix=file_ext, delete=False
            ) as temp_file:
                temp_file_path = temp_file.name
                temp_file.write(audio_bytes)

            log.debug(f"{log_identifier} Created temporary file: {temp_file_path}")

            api_url = f"{api_base.rstrip('/')}/v1/audio/transcriptions"
            headers = {"Authorization": f"Bearer {api_key}"}

            mime_type = _get_audio_mime_type(audio_filename)

            with open(temp_file_path, "rb") as audio_file:
                files = {
                    "file": (audio_filename, audio_file, mime_type),
                    "model": (None, model_name),
                }

                log.debug(f"{log_identifier} Calling transcription API...")

                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(api_url, headers=headers, files=files)
                    response.raise_for_status()
                    response_data = response.json()

            log.debug(f"{log_identifier} Transcription API response received.")

            if not response_data.get("text"):
                raise ValueError("API response does not contain transcription text.")

            transcription = response_data["text"]

            log.info(
                f"{log_identifier} Audio transcribed successfully. Transcription length: {len(transcription)} characters"
            )

            # Determine output filename
            if output_filename:
                final_filename = ensure_correct_extension(output_filename, "txt")
            else:
                # Auto-generate from source audio filename
                base_name = os.path.splitext(audio_filename)[0]
                final_filename = f"{base_name}_transcription.txt"

            # Build comprehensive metadata
            transcription_word_count = len(transcription.split())
            transcription_char_count = len(transcription)

            # Build description from multiple sources
            description_parts = []

            # Add user-provided description
            if description:
                description_parts.append(description)

            # Add source audio description if available
            source_description = source_audio_metadata.get("description")
            if source_description:
                description_parts.append(f"Source: {source_description}")

            # Add source audio info
            description_parts.append(
                f"Transcribed from audio file '{audio_filename}' (version {audio_version}, {audio_mime_type})"
            )

            # Combine all description parts
            final_description = ". ".join(description_parts)

            metadata = {
                "source_audio_filename": audio_filename,
                "source_audio_version": audio_version,
                "source_audio_mime_type": audio_mime_type,
                "transcription_model": model_name,
                "transcription_timestamp": datetime.now(timezone.utc).isoformat(),
                "transcription_word_count": transcription_word_count,
                "transcription_char_count": transcription_char_count,
                "generation_tool": "transcribe_audio",
            }

            # Copy source audio description separately for reference
            if source_description:
                metadata["source_audio_description"] = source_description

            # Add user-provided description separately if provided
            if description:
                metadata["user_provided_description"] = description

            log.info(f"{log_identifier} Returning transcription as DataObject for artifact storage")

            return ToolResult.ok(
                "Audio transcribed successfully.",
                data={
                    "audio_filename": audio_filename,
                    "audio_version": audio_version,
                    "transcription_word_count": transcription_word_count,
                    "transcription_char_count": transcription_char_count,
                },
                data_objects=[
                    DataObject(
                        name=final_filename,
                        content=transcription,
                        mime_type="text/plain",
                        disposition=DataDisposition.ARTIFACT_WITH_PREVIEW,
                        description=final_description,
                        metadata=metadata,
                        preview=transcription[:500] + "..." if len(transcription) > 500 else transcription,
                    )
                ],
            )

        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    log.debug(
                        f"{log_identifier} Cleaned up temporary file: {temp_file_path}"
                    )
                except OSError as e:
                    log.warning(
                        f"{log_identifier} Failed to clean up temporary file {temp_file_path}: {e}"
                    )

    except ValueError as ve:
        log.error(f"{log_identifier} Value error: {ve}")
        return ToolResult.error(str(ve))
    except httpx.HTTPStatusError as hse:
        log.error(
            f"{log_identifier} HTTP error calling transcription API: {hse.response.status_code} - {hse.response.text}"
        )
        return ToolResult.error(f"API error: {hse.response.status_code}")
    except httpx.RequestError as re:
        log.error(f"{log_identifier} Request error calling transcription API: {re}")
        return ToolResult.error(f"Request error: {re}")
    except json.JSONDecodeError as jde:
        log.error(f"{log_identifier} JSON decode error: {jde}")
        return ToolResult.error("Invalid JSON response from API")
    except Exception as e:
        log.exception(f"{log_identifier} Unexpected error in transcribe_audio: {e}")
        return ToolResult.error(f"An unexpected error occurred: {e}")


select_voice_tool_def = BuiltinTool(
    name="select_voice",
    implementation=select_voice,
    description="Selects a suitable voice name based on criteria like gender and tone. Use this to get a consistent voice name that can be passed to the `text_to_speech` tool for multiple calls.",
    category="audio",
    required_scopes=["tool:audio:tts"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "gender": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional desired gender for the voice ('male', 'female', 'neutral').",
                nullable=True,
            ),
            "tone": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional tone preference (e.g., 'friendly', 'professional').",
                nullable=True,
            ),
            "exclude_voices": adk_types.Schema(
                type=adk_types.Type.ARRAY,
                items=adk_types.Schema(type=adk_types.Type.STRING),
                description="Optional list of voice names to exclude from the selection.",
                nullable=True,
            ),
        },
        required=[],
    ),
    examples=[],
)

text_to_speech_tool_def = BuiltinTool(
    name="text_to_speech",
    implementation=text_to_speech,
    description="Converts text to speech using Gemini TTS API and saves as MP3 artifact.",
    category="audio",
    required_scopes=["tool:audio:tts"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "text": adk_types.Schema(
                type=adk_types.Type.STRING, description="The text to convert to speech."
            ),
            "output_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional filename for the output MP3.",
                nullable=True,
            ),
            "voice_name": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional specific voice name (e.g., 'Kore', 'Puck'). Overrides gender and tone.",
                nullable=True,
            ),
            "gender": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional desired gender for the voice ('male', 'female', 'neutral'). Used if 'voice_name' is not provided.",
                nullable=True,
            ),
            "tone": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional tone preference (e.g., 'friendly', 'professional'). Used if 'voice_name' is not provided.",
                nullable=True,
            ),
            "language": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional language code (e.g., 'en-US', 'fr-FR').",
                nullable=True,
            ),
        },
        required=["text"],
    ),
    examples=[],
)

multi_speaker_text_to_speech_tool_def = BuiltinTool(
    name="multi_speaker_text_to_speech",
    implementation=multi_speaker_text_to_speech,
    description="Converts conversation text with speaker labels to speech using multiple voices.",
    category="audio",
    required_scopes=["tool:audio:tts"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "conversation_text": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Text with speaker labels (e.g., 'Speaker1: Hello\\nSpeaker2: Hi there').",
            ),
            "output_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional filename for the output MP3.",
                nullable=True,
            ),
            "speaker_configs": adk_types.Schema(
                type=adk_types.Type.ARRAY,
                items=adk_types.Schema(
                    type=adk_types.Type.OBJECT,
                    description="Configuration for a single speaker.",
                    properties={
                        "name": adk_types.Schema(
                            type=adk_types.Type.STRING,
                            description="The speaker's name as it appears in conversation_text.",
                        ),
                        "voice": adk_types.Schema(
                            type=adk_types.Type.STRING,
                            description="Specific voice name to use. Overrides gender/tone.",
                            nullable=True,
                        ),
                        "gender": adk_types.Schema(
                            type=adk_types.Type.STRING,
                            description="Desired gender ('male', 'female', 'neutral').",
                            nullable=True,
                        ),
                        "tone": adk_types.Schema(
                            type=adk_types.Type.STRING,
                            description="Desired tone (e.g., 'friendly').",
                            nullable=True,
                        ),
                    },
                ),
                description="Optional list of speaker configurations.",
                nullable=True,
            ),
            "language": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional language code (e.g., 'en-US', 'fr-FR').",
                nullable=True,
            ),
        },
        required=["conversation_text"],
    ),
    examples=[],
)

concatenate_audio_tool_def = BuiltinTool(
    name="concatenate_audio",
    implementation=concatenate_audio,
    description="Combines multiple audio artifacts in a specified order into a single audio file. Allows for custom pause durations between each clip.",
    category="audio",
    required_scopes=["tool:audio:edit", "tool:artifact:create", "tool:artifact:load"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "clips_to_join": adk_types.Schema(
                type=adk_types.Type.ARRAY,
                description="An ordered list of clip objects to be joined.",
                items=adk_types.Schema(
                    type=adk_types.Type.OBJECT,
                    properties={
                        "filename": adk_types.Schema(
                            type=adk_types.Type.STRING,
                            description="The artifact filename of the audio clip (with optional :version).",
                        ),
                        "pause_after_ms": adk_types.Schema(
                            type=adk_types.Type.INTEGER,
                            description="Optional duration of silence in milliseconds to insert *after* this clip. Defaults to 500ms.",
                            nullable=True,
                        ),
                    },
                    required=["filename"],
                ),
            ),
            "output_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional. The desired filename for the final combined audio artifact.",
                nullable=True,
            ),
        },
        required=["clips_to_join"],
    ),
    examples=[],
)

transcribe_audio_tool_def = BuiltinTool(
    name="transcribe_audio",
    implementation=transcribe_audio,
    description="Transcribes an audio recording and saves the transcription as a text artifact.",
    category="audio",
    required_scopes=["tool:audio:transcribe", "tool:artifact:create"],
    artifact_args=["input_audio"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "input_audio": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The filename (and optional :version) of the input audio artifact.",
            ),
            "output_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional filename for the transcription text file (without .txt extension). If not provided, will auto-generate from source audio filename.",
                nullable=True,
            ),
            "description": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional description of the transcription for metadata (e.g., 'Transcription of customer support call about billing inquiry'). Will be combined with source audio description if available.",
                nullable=True,
            ),
        },
        required=["input_audio"],
    ),
    examples=[],
)

tool_registry.register(select_voice_tool_def)
tool_registry.register(text_to_speech_tool_def)
tool_registry.register(multi_speaker_text_to_speech_tool_def)
tool_registry.register(concatenate_audio_tool_def)
tool_registry.register(transcribe_audio_tool_def)
