"""
Speech API routes for STT and TTS functionality.
"""

from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel

from solace_ai_connector.common.log import log

from ..services.audio_service import AudioService
from ..dependencies import get_audio_service
from solace_agent_mesh.shared.api.auth_utils import get_current_user


router = APIRouter()


class TTSRequest(BaseModel):
    """Request model for text-to-speech"""
    input: str
    voice: Optional[str] = None
    messageId: Optional[str] = None
    provider: Optional[str] = None
    preprocess_markdown: bool = True  # Strip markdown syntax for natural speech


class PreprocessRequest(BaseModel):
    """Request model for markdown preprocessing"""
    text: str
    read_code_blocks: bool = False
    read_images: bool = True
    read_citations: bool = True


class StreamTTSRequest(BaseModel):
    """Request model for streaming text-to-speech"""
    input: str
    voice: Optional[str] = None
    runId: Optional[str] = None
    provider: Optional[str] = None
    preprocess_markdown: bool = True  # Strip markdown syntax for natural speech


@router.post("/stt")
async def speech_to_text(
    audio: UploadFile = File(...),
    provider: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
    audio_service: AudioService = Depends(get_audio_service)
):
    """
    Transcribe audio to text using configured STT service.
    
    Args:
        audio: Audio file (wav, mp3, webm, ogg)
        provider: Optional provider override (openai, azure)
        language: Optional language code (e.g., "en-US", "es-ES")
        user: Current authenticated user
        audio_service: Audio service instance
    
    Returns:
        JSON with transcribed text:
        {
            "text": "transcribed text",
            "language": "en",
            "duration": 5.2
        }
    
    Raises:
        HTTPException: If transcription fails
    """
    log.info(
        "[SpeechAPI] STT request from user=%s, filename=%s, provider=%s, language=%s",
        user.get("user_id"),
        audio.filename,
        provider,
        language
    )
    
    try:
        # Validate content type
        if not audio.content_type or not audio.content_type.startswith("audio/"):
            raise HTTPException(
                415,
                f"Unsupported media type: {audio.content_type}. Expected audio/*"
            )
        
        result = await audio_service.transcribe_audio(
            audio_file=audio,
            user_id=user.get("user_id", "anonymous"),
            session_id=user.get("session_id", "default"),
            app_name=user.get("app_name", "webui"),
            provider=provider,
            language=language
        )
        
        return result.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("[SpeechAPI] STT error: %s", e)
        raise HTTPException(500, f"Transcription failed: {str(e)}")


@router.post("/tts")
async def text_to_speech(
    request: TTSRequest,
    user: dict = Depends(get_current_user),
    audio_service: AudioService = Depends(get_audio_service)
):
    """
    Convert text to speech using configured TTS service.
    
    Args:
        request: TTS request with text and voice
        user: Current authenticated user
        audio_service: Audio service instance
    
    Returns:
        Audio data as MP3
    
    Raises:
        HTTPException: If generation fails
    """
    log.info(
        "[SpeechAPI] TTS request from user=%s, text_len=%d, voice=%s",
        user.get("user_id"),
        len(request.input),
        request.voice
    )
    
    try:
        # Validate input
        if not request.input or not request.input.strip():
            raise HTTPException(400, "Input text is required")
        
        if len(request.input) > 10000:
            raise HTTPException(
                413,
                "Text too long (max 10000 characters). Use /tts/stream for longer text."
            )
        
        audio_data = await audio_service.generate_speech(
            text=request.input,
            voice=request.voice,
            user_id=user.get("user_id", "anonymous"),
            session_id=user.get("session_id", "default"),
            app_name=user.get("app_name", "webui"),
            message_id=request.messageId,
            provider=request.provider,
            preprocess_markdown=request.preprocess_markdown
        )
        
        return Response(
            content=audio_data,
            media_type="audio/mpeg"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("[SpeechAPI] TTS error: %s", e)
        raise HTTPException(500, f"TTS generation failed: {str(e)}")


@router.post("/tts/stream")
async def stream_audio(
    request: StreamTTSRequest,
    user: dict = Depends(get_current_user),
    audio_service: AudioService = Depends(get_audio_service)
):
    """
    Stream TTS audio for long text (>4096 chars).
    Uses chunking and streaming for better UX.
    
    Args:
        request: Stream TTS request with text and voice
        user: Current authenticated user
        audio_service: Audio service instance
    
    Returns:
        Streaming audio response
    
    Raises:
        HTTPException: If generation fails
    """
    log.info(
        "[SpeechAPI] TTS stream request from user=%s, text_len=%d",
        user.get("user_id"),
        len(request.input)
    )
    
    try:
        # Validate input
        if not request.input or not request.input.strip():
            raise HTTPException(400, "Input text is required")
        
        # Add max length validation to prevent abuse (100KB max for streaming)
        if len(request.input) > 100000:
            raise HTTPException(
                413,
                "Text too long (max 100000 characters for streaming)"
            )
        
        async def audio_generator():
            async for chunk in audio_service.stream_speech(
                text=request.input,
                voice=request.voice,
                user_id=user.get("user_id", "anonymous"),
                session_id=user.get("session_id", "default"),
                app_name=user.get("app_name", "webui"),
                provider=request.provider,
                preprocess_markdown=request.preprocess_markdown
            ):
                yield chunk
        
        return StreamingResponse(
            audio_generator(),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f"inline; filename=tts_stream_{request.runId or 'audio'}.mp3",
                "Cache-Control": "no-cache"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("[SpeechAPI] TTS stream error: %s", e)
        raise HTTPException(500, f"TTS streaming failed: {str(e)}")


@router.get("/voices")
async def get_voices(
    provider: Optional[str] = None,  # NEW: Accept provider as query parameter
    user: dict = Depends(get_current_user),
    audio_service: AudioService = Depends(get_audio_service)
):
    """
    Get available TTS voices based on configuration and provider.
    
    Args:
        provider: Optional provider filter (azure, gemini)
        user: Current authenticated user
        audio_service: Audio service instance
    
    Returns:
        JSON with available voices:
        {
            "voices": ["Kore", "Puck", "Zephyr", ...],
            "default": "Kore"
        }
    """
    log.debug("[SpeechAPI] Voices request from user=%s, provider=%s", user.get("user_id"), provider)
    
    try:
        voices = await audio_service.get_available_voices(provider=provider)  # Pass provider
        
        # Get default voice from config
        config = audio_service.get_speech_config()
        default_voice = config.get("voice", "Kore")
        
        return {
            "voices": voices,
            "default": default_voice
        }
        
    except Exception as e:
        log.exception("[SpeechAPI] Error getting voices: %s", e)
        raise HTTPException(500, f"Failed to get voices: {str(e)}")


@router.get("/config")
async def get_speech_config(
    user: dict = Depends(get_current_user),
    audio_service: AudioService = Depends(get_audio_service)
):
    """
    Get speech configuration for frontend initialization.
    
    Args:
        user: Current authenticated user
        audio_service: Audio service instance
    
    Returns:
        JSON with speech configuration:
        {
            "sttExternal": true,
            "ttsExternal": true,
            "speechToText": true,
            "textToSpeech": true,
            "engineSTT": "external",
            "engineTTS": "external",
            "voice": "Kore",
            "playbackRate": 1.0,
            "cacheTTS": true,
            ...
        }
    """
    log.debug("[SpeechAPI] Config request from user=%s", user.get("user_id"))
    
    try:
        config = audio_service.get_speech_config()
        return config
        
    except Exception as e:
        log.exception("[SpeechAPI] Error getting config: %s", e)
        raise HTTPException(500, f"Failed to get config: {str(e)}")


@router.post("/preprocess")
async def preprocess_markdown(
    request: PreprocessRequest,
    user: dict = Depends(get_current_user)
):
    """
    Preprocess markdown text for natural speech.
    
    This endpoint converts markdown-formatted text to plain text suitable for
    Text-to-Speech engines. It removes markdown syntax while preserving the
    semantic meaning of the content.
    
    This is useful for browser-based TTS which doesn't go through the backend
    TTS pipeline that normally handles preprocessing.
    
    Args:
        request: Preprocess request with text and options
        user: Current authenticated user
    
    Returns:
        JSON with preprocessed text:
        {
            "text": "preprocessed plain text",
            "original_length": 150,
            "processed_length": 120
        }
    
    Raises:
        HTTPException: If preprocessing fails
    """
    log.debug(
        "[SpeechAPI] Preprocess request from user=%s, text_len=%d",
        user.get("user_id"),
        len(request.text)
    )
    
    try:
        # Validate input
        if not request.text:
            return {
                "text": "",
                "original_length": 0,
                "processed_length": 0
            }
        
        # Import and use the backend markdown_to_speech utility
        from solace_agent_mesh.common.utils.markdown_to_speech import (
            markdown_to_speech,
            MarkdownToSpeechOptions
        )
        
        original_length = len(request.text)
        
        # Create options object with the request parameters
        options = MarkdownToSpeechOptions(
            read_code_blocks=request.read_code_blocks,
            read_images=request.read_images,
            read_citations=request.read_citations
        )
        
        processed_text = markdown_to_speech(request.text, options=options)
        
        return {
            "text": processed_text,
            "original_length": original_length,
            "processed_length": len(processed_text)
        }
        
    except Exception as e:
        log.exception("[SpeechAPI] Preprocess error: %s", e)
        raise HTTPException(500, f"Preprocessing failed: {str(e)}")


@router.post("/voice-sample")
async def get_voice_sample(
    voice: str = Form(...),
    provider: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
    audio_service: AudioService = Depends(get_audio_service)
):
    """
    Generate a sample audio for a specific voice to preview before selection.
    
    Args:
        voice: Voice name to sample
        provider: Optional provider (azure, gemini)
        user: Current authenticated user
        audio_service: Audio service instance
    
    Returns:
        Audio data as MP3
    
    Raises:
        HTTPException: If generation fails
    """
    log.debug("[SpeechAPI] Voice sample request from user=%s, voice=%s, provider=%s",
              user.get("user_id"), voice, provider)
    
    try:
        # Validate voice parameter
        if not voice or not voice.strip():
            raise HTTPException(400, "Voice parameter is required")
        
        # Generate a sample text based on provider
        sample_text = "Hello! This is a sample of my voice. I hope you find it pleasant to listen to."
        
        audio_data = await audio_service.generate_speech(
            text=sample_text,
            voice=voice,
            user_id=user.get("user_id", "anonymous"),
            session_id=user.get("session_id", "default"),
            app_name=user.get("app_name", "webui"),
            message_id=f"voice_sample_{voice}",
            provider=provider,
            preprocess_markdown=False  # Sample text has no markdown
        )
        
        return Response(
            content=audio_data,
            media_type="audio/mpeg"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("[SpeechAPI] Voice sample error: %s", e)
        raise HTTPException(500, f"Voice sample generation failed: {str(e)}")