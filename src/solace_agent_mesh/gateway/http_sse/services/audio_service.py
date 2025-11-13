"""
Audio Service for Speech-to-Text and Text-to-Speech operations.
Bridges gateway endpoints and external speech APIs.
"""

import asyncio
import io
import tempfile
from typing import Any, AsyncGenerator, Dict, List, Optional
from fastapi import UploadFile, HTTPException
from solace_ai_connector.common.log import log

from ....agent.tools.audio_tools import ALL_AVAILABLE_VOICES


# Azure Neural Voices (popular subset with HD voices)
AZURE_NEURAL_VOICES = [
    # US English - HD Voices
    "en-US-Andrew:DragonHDLatestNeural",
    "en-US-Ava:DragonHDLatestNeural",
    "en-US-Brian:DragonHDLatestNeural",
    "en-US-Emma:DragonHDLatestNeural",
    # US English - Standard
    "en-US-JennyNeural",
    "en-US-GuyNeural",
    "en-US-AriaNeural",
    "en-US-DavisNeural",
    "en-US-JaneNeural",
    "en-US-JasonNeural",
    "en-US-NancyNeural",
    "en-US-TonyNeural",
    "en-US-SaraNeural",
    "en-US-AmberNeural",
    "en-US-AnaNeural",
    "en-US-AndrewNeural",
    "en-US-AshleyNeural",
    "en-US-BrandonNeural",
    "en-US-ChristopherNeural",
    "en-US-CoraNeural",
    "en-US-ElizabethNeural",
    "en-US-EricNeural",
    "en-US-JacobNeural",
    "en-US-MichelleNeural",
    "en-US-MonicaNeural",
    "en-US-RogerNeural",
    "en-US-SteffanNeural",
    # UK English
    "en-GB-LibbyNeural",
    "en-GB-RyanNeural",
    "en-GB-SoniaNeural",
    "en-GB-MiaNeural",
    "en-GB-AlfieNeural",
    "en-GB-BellaNeural",
    "en-GB-ElliotNeural",
    "en-GB-EthanNeural",
    "en-GB-HollieNeural",
    "en-GB-OliverNeural",
    "en-GB-OliviaNeural",
    "en-GB-ThomasNeural",
    # Australian English
    "en-AU-NatashaNeural",
    "en-AU-WilliamNeural",
    "en-AU-AnnetteNeural",
    "en-AU-CarlyNeural",
    "en-AU-DarrenNeural",
    "en-AU-DuncanNeural",
    "en-AU-ElsieNeural",
    "en-AU-FreyaNeural",
    "en-AU-JoanneNeural",
    "en-AU-KenNeural",
    "en-AU-KimNeural",
    "en-AU-NeilNeural",
    "en-AU-TimNeural",
    "en-AU-TinaNeural",
    # Canadian English
    "en-CA-ClaraNeural",
    "en-CA-LiamNeural",
    # Indian English
    "en-IN-NeerjaNeural",
    "en-IN-PrabhatNeural",
]


class TranscriptionResult:
    """Result of audio transcription"""
    def __init__(self, text: str, language: str = "en", duration: float = 0.0):
        self.text = text
        self.language = language
        self.duration = duration
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "language": self.language,
            "duration": self.duration
        }


class AudioService:
    """
    Service layer for audio operations.
    Bridges gateway endpoints and agent audio tools.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize AudioService with configuration.
        
        Args:
            config: Configuration dictionary containing speech settings
        """
        self.config = config
        self.speech_config = config.get("speech", {})
        
    async def transcribe_audio(
        self,
        audio_file: UploadFile,
        user_id: str,
        session_id: str,
        app_name: str = "webui"
    ) -> TranscriptionResult:
        """
        Transcribe audio file to text using configured STT service.
        
        Args:
            audio_file: Uploaded audio file
            user_id: User identifier
            session_id: Session identifier
            app_name: Application name
            
        Returns:
            TranscriptionResult with transcribed text
            
        Raises:
            HTTPException: If transcription fails
        """
        
        try:
            # Validate file
            if not audio_file.filename:
                raise HTTPException(400, "No filename provided")
            
            # Check file size (max 25MB)
            content = await audio_file.read()
            if len(content) > 25 * 1024 * 1024:
                raise HTTPException(413, "Audio file too large (max 25MB)")
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(
                suffix=self._get_file_extension(audio_file.filename),
                delete=False
            ) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name
            
            try:
                # Get STT configuration
                stt_config = self.speech_config.get("stt", {})
                if not stt_config:
                    raise HTTPException(
                        500,
                        "STT not configured. Please add speech.stt configuration."
                    )
                
                # Use direct API call instead of the tool (which requires artifact service)
                # The transcribe_audio tool is designed for agent use with artifacts
                # For gateway API, we'll call the STT API directly
                import httpx
                import os
                
                api_url = stt_config.get("url", "https://api.openai.com/v1/audio/transcriptions")
                api_key = stt_config.get("api_key", "")
                model = stt_config.get("model", "whisper-1")
                
                if not api_key:
                    raise HTTPException(500, "STT API key not configured")
                
                # Read the audio file
                with open(temp_path, "rb") as audio_file:
                    audio_data = audio_file.read()
                
                # Prepare multipart form data
                files = {
                    "file": (os.path.basename(temp_path), audio_data, "audio/webm"),
                }
                data = {
                    "model": model,
                }
                headers = {
                    "Authorization": f"Bearer {api_key}"
                }
                
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(api_url, headers=headers, files=files, data=data)
                    response.raise_for_status()
                    result = response.json()
                
                transcription_text = result.get("text", "").strip()
                
                if not transcription_text:
                    # Empty transcription - likely silence or very short audio
                    log.warning("[AudioService] Empty transcription - no speech detected in audio")
                    raise HTTPException(400, "No speech detected in audio. Please try speaking louder or longer.")
                
                result = {
                    "status": "success",
                    "transcription": transcription_text
                }
                
                if result.get("status") == "error":
                    raise HTTPException(500, result.get("message", "Transcription failed"))
                
                transcription_text = result.get("transcription", "")

                return TranscriptionResult(
                    text=transcription_text,
                    language="en",  # TODO: Detect language
                    duration=0.0  # TODO: Calculate duration
                )
                
            finally:
                # Clean up temp file
                import os
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    log.warning("[AudioService] Failed to delete temp file: %s", e)
        
        except HTTPException:
            raise
        except Exception as e:
            log.exception("[AudioService] Transcription error: %s", e)
            raise HTTPException(500, f"Transcription failed: {str(e)}")
    def _generate_azure_ssml(self, text: str, voice: str) -> str:
        """
        Generate SSML for Azure TTS with proper XML escaping.
        Handles both standard and HD voice formats.
        
        Args:
            text: Text to convert to speech
            voice: Azure voice name (e.g., "en-US-JennyNeural" or "en-US-Ava:DragonHDLatestNeural")
            
        Returns:
            SSML string
        """
        # Escape XML special characters
        escaped_text = (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))
        
        # For HD voices, the format is "locale-Name:DragonHDLatestNeural"
        # Azure expects just the voice name in SSML, not the :DragonHDLatestNeural suffix
        # The HD quality is specified via the voice name itself
        voice_name = voice  # Use the full voice name as-is for HD voices
        
        return f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
    <voice name="{voice_name}">
        <prosody rate="medium" pitch="default">
            {escaped_text}
        </prosody>
    </voice>
</speak>"""
    
    async def generate_speech_azure(
        self,
        text: str,
        voice: Optional[str],
        user_id: str,
        session_id: str,
        app_name: str = "webui",
        message_id: Optional[str] = None
    ) -> bytes:
        """
        Generate speech using Azure Neural Voices.
        
        Args:
            text: Text to convert to speech
            voice: Azure voice name (e.g., "en-US-JennyNeural")
            user_id: User identifier
            session_id: Session identifier
            app_name: Application name
            message_id: Optional message ID for caching
            
        Returns:
            Audio data as bytes (MP3 format)
            
        Raises:
            HTTPException: If generation fails
        """
        
        try:
            log.info("[AudioService] Starting Azure TTS generation")
            
            # Import Azure SDK
            try:
                import azure.cognitiveservices.speech as speechsdk
                log.info("[AudioService] Azure SDK imported successfully")
            except ImportError as e:
                log.error(f"[AudioService] Azure SDK not installed: {e}")
                raise HTTPException(
                    500,
                    "Azure Speech SDK not installed. Run: pip install azure-cognitiveservices-speech"
                )
            
            # Get Azure configuration
            tts_config = self.speech_config.get("tts", {})
            azure_config = tts_config.get("azure", {})
            
            api_key = azure_config.get("api_key", "")
            region = azure_config.get("region", "")
            
            if not api_key or not region:
                log.error("[AudioService] Azure TTS missing api_key or region")
                raise HTTPException(
                    500,
                    "Azure TTS not configured. Please set speech.tts.azure.api_key and region."
                )
            
            # Set voice - use default if provided voice is not an Azure voice
            requested_voice = voice or azure_config.get("default_voice", "en-US-JennyNeural")
            
            # Check if requested voice is an Azure voice
            # Azure voices contain "Neural" or "DragonHD" and have locale prefix (e.g., "en-US-")
            is_azure_voice = (
                ("Neural" in requested_voice or "DragonHD" in requested_voice)
                and ("-" in requested_voice)
            )
            
            if is_azure_voice:
                final_voice = requested_voice
            else:
                # Not an Azure voice, use default
                final_voice = azure_config.get("default_voice", "en-US-JennyNeural")
                
            # Create speech config
            speech_config = speechsdk.SpeechConfig(
                subscription=api_key,
                region=region
            )
            
            # Set output format to MP3
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
            )
            
            # Generate SSML
            ssml = self._generate_azure_ssml(text, final_voice)
            
            log.debug(f"[AudioService] Generated SSML: {ssml[:200]}...")
            
            # Create synthesizer (None for in-memory output)
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config,
                audio_config=None
            )
            
            # Synthesize speech (run in thread pool to avoid blocking)
            result = await asyncio.to_thread(
                lambda: synthesizer.speak_ssml_async(ssml).get()
            )
            
            # Check result
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                audio_data = result.audio_data
                return audio_data
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                error_msg = f"Azure TTS canceled: {cancellation.reason}"
                if cancellation.error_details:
                    error_msg += f" - {cancellation.error_details}"
                log.error(f"[AudioService] {error_msg}")
                raise HTTPException(500, error_msg)
            else:
                raise HTTPException(500, f"Azure TTS failed with reason: {result.reason}")
                
        except HTTPException:
            raise
        except Exception as e:
            log.exception("[AudioService] Azure TTS generation error: %s", e)
            raise HTTPException(500, f"Azure TTS generation failed: {str(e)}")
    
    async def generate_speech_gemini(
        self,
        text: str,
        voice: Optional[str],
        user_id: str,
        session_id: str,
        app_name: str = "webui",
        message_id: Optional[str] = None
    ) -> bytes:
        """
        Generate speech using Gemini TTS (original implementation).
        
        Args:
            text: Text to convert to speech
            voice: Voice name to use
            user_id: User identifier
            session_id: Session identifier
            app_name: Application name
            message_id: Optional message ID for caching
            
        Returns:
            Audio data as bytes (MP3 format)
            
        Raises:
            HTTPException: If generation fails
        """

        try:
            
            # Get TTS configuration
            tts_config = self.speech_config.get("tts", {})
            gemini_config = tts_config.get("gemini", tts_config)  
            
            # Use direct Gemini API call
            from google import genai
            from google.genai import types as adk_types
            import wave
            from pydub import AudioSegment
            import os
            
            api_key = gemini_config.get("api_key", "")
            model = gemini_config.get("model", "gemini-2.5-flash-preview-tts")
            final_voice = voice or gemini_config.get("default_voice", "Kore")
            language = gemini_config.get("language", "en-US")
            
            if not api_key:
                log.error("[AudioService] No Gemini API key found")
                raise HTTPException(500, "Gemini TTS API key not configured")
            
            
            # Create Gemini client
            client = genai.Client(api_key=api_key)
            
            # Create voice config
            voice_config = adk_types.VoiceConfig(
                prebuilt_voice_config=adk_types.PrebuiltVoiceConfig(voice_name=final_voice)
            )
            speech_config = adk_types.SpeechConfig(voice_config=voice_config)
            
            # Generate audio
            config = adk_types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=speech_config,
            )
            
            # Retry logic for transient API failures
            max_retries = 2
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=model,
                        contents=f"Say in a clear voice: {text}",
                        config=config
                    )
                    
                    # Validate response structure
                    if not response:
                        raise ValueError("Gemini API returned empty response")
                    
                    if not response.candidates or len(response.candidates) == 0:
                        raise ValueError("Gemini API returned no candidates")
                    
                    candidate = response.candidates[0]
                    
                    # Log candidate details for debugging
                    log.debug(f"[AudioService] Candidate finish_reason: {getattr(candidate, 'finish_reason', 'unknown')}")
                    log.debug(f"[AudioService] Candidate has content: {candidate.content is not None}")
                    
                    if not candidate.content:
                        # Check if there's a finish_reason that explains why
                        finish_reason = getattr(candidate, 'finish_reason', None)
                        if finish_reason:
                            raise ValueError(f"Gemini API returned candidate with no content (finish_reason: {finish_reason})")
                        raise ValueError("Gemini API returned candidate with no content")
                    
                    # Success - break retry loop
                    break
                    
                except ValueError as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        log.warning(f"[AudioService] TTS attempt {attempt + 1} failed: {e}, retrying...")
                        await asyncio.sleep(0.5)  # Brief delay before retry
                    else:
                        log.error(f"[AudioService] TTS failed after {max_retries} attempts: {e}")
                        raise HTTPException(500, f"TTS generation failed after {max_retries} attempts: {str(e)}")
            
            if not candidate.content.parts or len(candidate.content.parts) == 0:
                raise HTTPException(500, "Gemini API returned no audio parts")
            
            part = candidate.content.parts[0]
            if not hasattr(part, 'inline_data') or not part.inline_data:
                raise HTTPException(500, "Gemini API returned part with no inline_data")
            
            wav_data = part.inline_data.data
            if not wav_data:
                raise HTTPException(500, "No audio data received from Gemini API")
            
            # Convert WAV to MP3
            def create_wav_file(filename: str, pcm_data: bytes):
                with wave.open(filename, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(24000)
                    wf.writeframes(pcm_data)
            
            wav_temp_path = None
            mp3_temp_path = None
            
            try:
                # Create temp WAV file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_temp:
                    wav_temp_path = wav_temp.name
                
                await asyncio.to_thread(create_wav_file, wav_temp_path, wav_data)
                
                # Create temp MP3 file
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as mp3_temp:
                    mp3_temp_path = mp3_temp.name
                
                # Convert to MP3
                audio = await asyncio.to_thread(AudioSegment.from_wav, wav_temp_path)
                await asyncio.to_thread(audio.export, mp3_temp_path, format="mp3")
                
                # Read MP3 data
                with open(mp3_temp_path, "rb") as mp3_file:
                    mp3_data = mp3_file.read()
                
                return mp3_data
                
            finally:
                # Clean up temp files
                if wav_temp_path:
                    try:
                        os.remove(wav_temp_path)
                    except:
                        pass
                if mp3_temp_path:
                    try:
                        os.remove(mp3_temp_path)
                    except:
                        pass
            
        except HTTPException:
            raise
        except Exception as e:
            log.exception("[AudioService] Gemini TTS generation error: %s", e)
            raise HTTPException(500, f"Gemini TTS generation failed: {str(e)}")
    
    
    async def generate_speech(
        self,
        text: str,
        voice: Optional[str],
        user_id: str,
        session_id: str,
        app_name: str = "webui",
        message_id: Optional[str] = None,
        provider: Optional[str] = None  # NEW: Allow provider override from request
    ) -> bytes:
        """
        Generate speech audio from text using configured TTS service.
        Routes to appropriate provider (Azure, Gemini, etc.).
        
        Args:
            text: Text to convert to speech
            voice: Voice name to use
            user_id: User identifier
            session_id: Session identifier
            app_name: Application name
            message_id: Optional message ID for caching
            provider: Optional provider override (azure, gemini)
            
        Returns:
            Audio data as bytes (MP3 format)
            
        Raises:
            HTTPException: If generation fails
        """
        log.info(
            "[AudioService] Generating speech for user=%s, session=%s, voice=%s, text_len=%d, provider=%s",
            user_id, session_id, voice, len(text), provider
        )
        
        try:
            # Get TTS configuration with detailed debugging
            log.info(f"[AudioService] Full config keys: {list(self.config.keys())}")
            log.info(f"[AudioService] Has 'speech' key: {'speech' in self.config}")
            log.info(f"[AudioService] Speech config: {self.speech_config}")
            
            tts_config = self.speech_config.get("tts", {}) if self.speech_config else {}
            log.info(f"[AudioService] TTS config exists: {bool(tts_config)}")
            log.info(f"[AudioService] TTS config keys: {list(tts_config.keys()) if tts_config else 'empty'}")
            
            if not tts_config:
                log.error("[AudioService] TTS not configured in speech.tts")
                log.error(f"[AudioService] Available config keys: {list(self.config.keys())}")
                log.error(f"[AudioService] Speech config value: {self.speech_config}")
                raise HTTPException(
                    500,
                    "TTS not configured. Please add speech.tts configuration to gateway YAML under app_config."
                )
            
            # Determine provider - use request provider if provided, otherwise use config
            final_provider = provider or tts_config.get("provider", "gemini")
            
            # Route to appropriate provider
            if final_provider == "azure":
                return await self.generate_speech_azure(
                    text, voice, user_id, session_id, app_name, message_id
                )
            elif final_provider == "gemini":
                return await self.generate_speech_gemini(
                    text, voice, user_id, session_id, app_name, message_id
                )
            else:
                raise HTTPException(500, f"Unknown TTS provider: {final_provider}")
                
        except HTTPException:
            raise
        except Exception as e:
            log.exception("[AudioService] TTS generation error: %s", e)
            raise HTTPException(500, f"TTS generation failed: {str(e)}")
    
    async def stream_speech(
        self,
        text: str,
        voice: Optional[str],
        user_id: str,
        session_id: str,
        app_name: str = "webui"
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream speech audio for long text with intelligent sentence-based chunking.
        Generates audio chunks concurrently for faster playback.
        
        Args:
            text: Text to convert to speech
            voice: Voice name to use
            user_id: User identifier
            session_id: Session identifier
            app_name: Application name
            
        Yields:
            Audio data chunks as bytes
        """
        log.info(
            "[AudioService] Streaming speech for user=%s, session=%s, text_len=%d",
            user_id, session_id, len(text)
        )
        
        # Split text into sentence-based chunks for more natural audio boundaries
        import re
        
        # Split on sentence boundaries (., !, ?, newlines)
        sentences = re.split(r'(?<=[.!?\n])\s+', text)
        
        # Group sentences into chunks (max ~500 chars per chunk for faster generation)
        MAX_CHUNK_SIZE = 500
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) > MAX_CHUNK_SIZE and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += " " + sentence if current_chunk else sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        log.info("[AudioService] Split text into %d chunks for streaming", len(chunks))
        
        # Process chunks with concurrent generation (generate next while streaming current)
        async def generate_chunk(chunk_text: str, chunk_idx: int):
            try:
                return await self.generate_speech(
                    text=chunk_text,
                    voice=voice,
                    user_id=user_id,
                    session_id=session_id,
                    app_name=app_name,
                    message_id=f"chunk_{chunk_idx}"
                )
            except Exception as e:
                log.error("[AudioService] Error generating chunk %d: %s", chunk_idx, e)
                return None
        
        # Use a small buffer to pre-generate chunks
        buffer_size = 2
        tasks = []
        
        for i, chunk in enumerate(chunks):
            log.debug("[AudioService] Processing chunk %d/%d (len=%d)", i+1, len(chunks), len(chunk))
            
            # Start generating current chunk
            task = asyncio.create_task(generate_chunk(chunk, i))
            tasks.append(task)
            
            # If we have enough tasks in buffer, yield the oldest one
            if len(tasks) >= buffer_size:
                audio_data = await tasks.pop(0)
                if audio_data:
                    yield audio_data
        
        # Yield remaining buffered chunks
        for task in tasks:
            audio_data = await task
            if audio_data:
                yield audio_data
    
    async def get_available_voices(self, provider: Optional[str] = None) -> List[str]:
        """
        Get list of available TTS voices from configuration.
        
        Args:
            provider: Optional provider filter (azure, gemini)
        
        Returns:
            List of voice names
        """
        tts_config = self.speech_config.get("tts", {})
        # Use provided provider or fall back to config
        final_provider = provider or tts_config.get("provider", "gemini")
        
        if final_provider == "azure":
            azure_config = tts_config.get("azure", {})
            voices = azure_config.get("voices", AZURE_NEURAL_VOICES)
        elif final_provider == "gemini":
            gemini_config = tts_config.get("gemini", tts_config)  # Fallback to root for backward compat
            voices = gemini_config.get("voices", ALL_AVAILABLE_VOICES)
        else:
            voices = []
        
        log.debug("[AudioService] Available voices for provider %s: %d", final_provider, len(voices))
        return voices
    
    def get_speech_config(self) -> Dict[str, Any]:
        """
        Get speech configuration for frontend initialization.
        
        Returns:
            Configuration dictionary
        """
        stt_config = self.speech_config.get("stt", {})
        tts_config = self.speech_config.get("tts", {})
        speech_tab = self.speech_config.get("speechTab", {})
        
        config = {
            "sttExternal": bool(stt_config),
            "ttsExternal": bool(tts_config),
        }
        
        # Add speech tab settings if configured
        if speech_tab:
            config.update({
                "advancedMode": speech_tab.get("advancedMode", False),
            })
            
            # STT settings
            stt_settings = speech_tab.get("speechToText", {})
            if stt_settings:
                config.update({
                    "speechToText": stt_settings.get("speechToText", True),
                    "engineSTT": stt_settings.get("engineSTT", "browser"),
                    "languageSTT": stt_settings.get("languageSTT", "en-US"),
                    "autoSendText": stt_settings.get("autoSendText", -1),
                    "autoTranscribeAudio": stt_settings.get("autoTranscribeAudio", True),
                    "decibelValue": stt_settings.get("decibelValue", -45),
                })
            
            # TTS settings
            tts_settings = speech_tab.get("textToSpeech", {})
            if tts_settings:
                config.update({
                    "textToSpeech": tts_settings.get("textToSpeech", True),
                    "engineTTS": tts_settings.get("engineTTS", "browser"),
                    "voice": tts_settings.get("voice", tts_config.get("default_voice", "Kore")),
                    "playbackRate": tts_settings.get("playbackRate", 1.0),
                    "automaticPlayback": tts_settings.get("automaticPlayback", False),
                    "cacheTTS": tts_settings.get("cacheTTS", True),
                    "cloudBrowserVoices": tts_settings.get("cloudBrowserVoices", False),
                })
            
            # Conversation mode
            config["conversationMode"] = speech_tab.get("conversationMode", False)
        
        log.debug("[AudioService] Speech config: %s", config.keys())
        return config
    
    def _get_file_extension(self, filename: str) -> str:
        """Get file extension from filename"""
        import os
        return os.path.splitext(filename)[1] or ".wav"
    
    async def _mock_save_artifact(self, *args, **kwargs):
        """Mock artifact save for TTS tool"""
        # This is a placeholder - proper integration with artifact service needed
        return {
            "status": "success",
            "data_version": 1,
            "artifact_id": "mock-id"
        }