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


# AWS Polly Neural Voices (popular subset)
AWS_POLLY_NEURAL_VOICES = [
    # US English - Neural
    "Joanna",
    "Matthew",
    "Ruth",
    "Stephen",
    "Kendra",
    "Joey",
    "Kimberly",
    "Salli",
    "Ivy",
    # UK English - Neural
    "Amy",
    "Emma",
    "Brian",
    "Arthur",
    # Australian English
    "Olivia",
    # Canadian English
    "Liam",
    # Indian English
    "Kajal",
    "Aria",
]

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
        
    async def transcribe_audio_openai(
        self,
        temp_path: str,
        user_id: str,
        session_id: str,
        app_name: str = "webui",
        language: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio using OpenAI Whisper API.
        
        Args:
            temp_path: Path to temporary audio file
            user_id: User identifier
            session_id: Session identifier
            app_name: Application name
            language: Optional language code (e.g., "en", "es", "fr")
            
        Returns:
            TranscriptionResult with transcribed text
            
        Raises:
            HTTPException: If transcription fails
        """
        try:
            import httpx
            import os
            
            stt_config = self.speech_config.get("stt", {})
            openai_config = stt_config.get("openai", stt_config)  # Fallback to root for backward compat
            
            api_url = openai_config.get("url", "https://api.openai.com/v1/audio/transcriptions")
            api_key = openai_config.get("api_key", "")
            model = openai_config.get("model", "whisper-1")
            
            if not api_key:
                raise HTTPException(500, "OpenAI STT API key not configured")
            
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
            
            # Add language parameter if provided (OpenAI expects ISO-639-1 code like "en", "es")
            if language:
                # Convert language code from "en-US" format to "en" format for OpenAI
                lang_code = language.split("-")[0] if "-" in language else language
                data["language"] = lang_code
            
            headers = {
                "Authorization": f"Bearer {api_key}"
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(api_url, headers=headers, files=files, data=data)
                response.raise_for_status()
                result = response.json()
            
            transcription_text = result.get("text", "").strip()
            
            if not transcription_text:
                log.warning("[AudioService] Empty transcription - no speech detected in audio")
                raise HTTPException(400, "No speech detected in audio. Please try speaking louder or longer.")
            
            return TranscriptionResult(
                text=transcription_text,
                language="en",
                duration=0.0
            )
            
        except HTTPException:
            raise
        except Exception as e:
            log.exception("[AudioService] OpenAI STT error: %s", e)
            raise HTTPException(500, f"OpenAI STT failed: {str(e)}")
    
    async def transcribe_audio_azure(
        self,
        temp_path: str,
        user_id: str,
        session_id: str,
        app_name: str = "webui",
        language: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio using Azure Speech SDK.
        
        Args:
            temp_path: Path to temporary audio file
            user_id: User identifier
            session_id: Session identifier
            app_name: Application name
            language: Optional language code (e.g., "en-US", "es-ES")
            
        Returns:
            TranscriptionResult with transcribed text
            
        Raises:
            HTTPException: If transcription fails
        """
        wav_temp_path = None
        try:
            # Import Azure SDK
            try:
                import azure.cognitiveservices.speech as speechsdk
            except ImportError:
                raise HTTPException(
                    500,
                    "Azure Speech SDK not installed. Run: pip install azure-cognitiveservices-speech"
                )
            
            # Get Azure configuration
            stt_config = self.speech_config.get("stt", {})
            azure_config = stt_config.get("azure", {})
            
            api_key = azure_config.get("api_key", "")
            region = azure_config.get("region", "")
            # Use provided language or fall back to config
            final_language = language or azure_config.get("language", "en-US")
            
            if not api_key or not region:
                raise HTTPException(
                    500,
                    "Azure STT not configured. Please set speech.stt.azure.api_key and region, or speech.tts.azure if using shared config."
                )
            
            # Convert audio to WAV format (Azure SDK requires WAV)
            # WebM/OGG/MP4 need to be converted
            import os
            from pydub import AudioSegment
            
            file_ext = os.path.splitext(temp_path)[1].lower()
            
            if file_ext not in ['.wav']:
                # Convert to WAV
                # Load audio file
                if file_ext == '.webm':
                    audio = await asyncio.to_thread(AudioSegment.from_file, temp_path, format="webm")
                elif file_ext == '.ogg':
                    audio = await asyncio.to_thread(AudioSegment.from_ogg, temp_path)
                elif file_ext in ['.mp3', '.mp4']:
                    audio = await asyncio.to_thread(AudioSegment.from_file, temp_path)
                else:
                    audio = await asyncio.to_thread(AudioSegment.from_file, temp_path)
                
                # Create temp WAV file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_temp:
                    wav_temp_path = wav_temp.name
                
                # Export as WAV (16kHz, mono, 16-bit PCM - Azure's preferred format)
                await asyncio.to_thread(
                    audio.set_frame_rate(16000).set_channels(1).export,
                    wav_temp_path,
                    format="wav"
                )
                
                audio_path = wav_temp_path
            else:
                audio_path = temp_path
            
            # Create speech config
            speech_config = speechsdk.SpeechConfig(
                subscription=api_key,
                region=region
            )
            speech_config.speech_recognition_language = final_language
            
            # Create audio config from file
            audio_config = speechsdk.AudioConfig(filename=audio_path)
            
            # Create speech recognizer
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config
            )
            
            transcribed_texts = []
            done = asyncio.Event()
            
            def recognized_handler(evt):
                if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    text = evt.result.text.strip()
                    if text:
                        transcribed_texts.append(text)
            
            def canceled_handler(evt):
                if evt.cancellation_details.error_details:
                    log.error(f"[AudioService] Recognition error: {evt.cancellation_details.error_details}")
                done.set()
            
            def stopped_handler(evt):
                done.set()
            
            # Connect callbacks
            recognizer.recognized.connect(recognized_handler)
            recognizer.canceled.connect(canceled_handler)
            recognizer.session_stopped.connect(stopped_handler)
            
            # Start continuous recognition
            await asyncio.to_thread(recognizer.start_continuous_recognition)
            
            # Wait for recognition to complete
            await done.wait()
            
            # Stop recognition
            await asyncio.to_thread(recognizer.stop_continuous_recognition)
            
            # Combine all recognized text
            if not transcribed_texts:
                log.warning("[AudioService] No speech could be recognized")
                raise HTTPException(400, "No speech detected in audio. Please try speaking louder or longer.")
            
            full_transcription = " ".join(transcribed_texts).strip()
            
            return TranscriptionResult(
                text=full_transcription,
                language=final_language,
                duration=0.0  # Duration not available in continuous mode
            )
                
        except HTTPException:
            raise
        except Exception as e:
            log.exception("[AudioService] Azure STT error: %s", e)
            raise HTTPException(500, f"Azure STT failed: {str(e)}")
        finally:
            # Clean up WAV temp file if created
            if wav_temp_path:
                try:
                    import os
                    os.unlink(wav_temp_path)
                except Exception as e:
                    log.warning("[AudioService] Failed to delete WAV temp file: %s", e)
    
    async def transcribe_audio(
        self,
        audio_file: UploadFile,
        user_id: str,
        session_id: str,
        app_name: str = "webui",
        provider: Optional[str] = None,
        language: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio file to text using configured STT service.
        Routes to appropriate provider (OpenAI, Azure, etc.).
        
        Args:
            audio_file: Uploaded audio file
            user_id: User identifier
            session_id: Session identifier
            app_name: Application name
            provider: Optional provider override (openai, azure)
            language: Optional language code (e.g., "en-US", "es-ES")
            
        Returns:
            TranscriptionResult with transcribed text
            
        Raises:
            HTTPException: If transcription fails
        """
        
        try:
            # Validate file
            if not audio_file.filename:
                raise HTTPException(400, "No filename provided")
            
            # Check file size before reading (max 25MB) to prevent OOM
            if audio_file.size and audio_file.size > 25 * 1024 * 1024:
                raise HTTPException(413, "Audio file too large (max 25MB)")
            
            # Read content after size check
            content = await audio_file.read()
            
            # Double-check size after reading (in case size wasn't available before)
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
                
                # Determine provider - use request provider if provided, otherwise use config
                final_provider = provider or stt_config.get("provider", "openai")
                
                log.info(
                    "[AudioService] Transcribing audio for user=%s, session=%s, provider=%s, language=%s",
                    user_id, session_id, final_provider, language
                )
                
                # Route to appropriate provider
                if final_provider == "azure":
                    return await self.transcribe_audio_azure(
                        temp_path, user_id, session_id, app_name, language
                    )
                elif final_provider == "openai":
                    return await self.transcribe_audio_openai(
                        temp_path, user_id, session_id, app_name, language
                    )
                else:
                    raise HTTPException(500, f"Unknown STT provider: {final_provider}")
                
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
        # Escape XML special characters in text
        escaped_text = (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))
        
        # Escape XML special characters in voice name to prevent injection
        escaped_voice = (voice
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))
        
        # For HD voices, the format is "locale-Name:DragonHDLatestNeural"
        # Azure expects just the voice name in SSML, not the :DragonHDLatestNeural suffix
        # The HD quality is specified via the voice name itself
        
        return f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
    <voice name="{escaped_voice}">
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
            
            # Import Azure SDK
            try:
                import azure.cognitiveservices.speech as speechsdk
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
            # Gemini requires lowercase voice names
            final_voice = final_voice.lower()
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
    
    
    async def generate_speech_polly(
        self,
        text: str,
        voice: Optional[str],
        user_id: str,
        session_id: str,
        app_name: str = "webui",
        message_id: Optional[str] = None
    ) -> bytes:
        """
        Generate speech using AWS Polly.
        
        Args:
            text: Text to convert to speech
            voice: Polly voice ID (e.g., "Joanna", "Matthew")
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
            
            # Import boto3
            try:
                import boto3
                from botocore.exceptions import ClientError as BotoClientError, BotoCoreError
            except ImportError as e:
                log.error(f"[AudioService] boto3 not installed: {e}")
                raise HTTPException(
                    500,
                    "AWS boto3 SDK not installed. Run: pip install boto3"
                )
            
            # Get Polly configuration
            tts_config = self.speech_config.get("tts", {})
            polly_config = tts_config.get("polly", {})
            
            aws_access_key_id = polly_config.get("aws_access_key_id", "")
            aws_secret_access_key = polly_config.get("aws_secret_access_key", "")
            region = polly_config.get("region", "us-east-1")
            engine = polly_config.get("engine", "neural")  # 'neural' or 'standard'
            
            if not aws_access_key_id or not aws_secret_access_key:
                log.error("[AudioService] AWS Polly missing credentials")
                raise HTTPException(
                    500,
                    "AWS Polly not configured. Please set speech.tts.polly.aws_access_key_id and aws_secret_access_key."
                )
            
            # Set voice - use default if provided voice is not a Polly voice
            requested_voice = voice or polly_config.get("default_voice", "Joanna")
            
            # Polly voices are simple names (e.g., "Joanna", "Matthew")
            # Validate it's a reasonable voice name (alphanumeric)
            is_polly_voice = requested_voice.isalpha()
            
            if is_polly_voice:
                final_voice = requested_voice
            else:
                # Not a valid Polly voice, use default
                final_voice = polly_config.get("default_voice", "Joanna")
                log.warning(f"[AudioService] Invalid Polly voice '{requested_voice}', using default '{final_voice}'")
            
            # Create Polly client
            try:
                polly_client = boto3.client(
                    'polly',
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
                    region_name=region
                )
            except Exception as e:
                log.error(f"[AudioService] Failed to create Polly client: {e}")
                raise HTTPException(500, f"Failed to create AWS Polly client: {str(e)}")
            
            # Synthesize speech
            log.debug(f"[AudioService] Synthesizing with voice={final_voice}, engine={engine}, text_len={len(text)}")
            
            try:
                response = await asyncio.to_thread(
                    polly_client.synthesize_speech,
                    Text=text,
                    OutputFormat='mp3',
                    VoiceId=final_voice,
                    Engine=engine
                )
                
                # Read audio stream
                if 'AudioStream' in response:
                    audio_data = response['AudioStream'].read()
                    return audio_data
                else:
                    raise HTTPException(500, "No audio stream in Polly response")
                    
            except BotoClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                error_msg = e.response.get('Error', {}).get('Message', str(e))
                log.error(f"[AudioService] Polly API error: {error_code} - {error_msg}")
                
                if error_code == 'InvalidParameterValue':
                    raise HTTPException(400, f"Invalid Polly parameter: {error_msg}")
                elif error_code in ['AccessDeniedException', 'UnauthorizedException']:
                    raise HTTPException(403, f"AWS Polly authentication failed: {error_msg}")
                else:
                    raise HTTPException(500, f"AWS Polly error ({error_code}): {error_msg}")
                    
            except BotoCoreError as e:
                log.error(f"[AudioService] Boto core error: {e}")
                raise HTTPException(500, f"AWS SDK error: {str(e)}")
                
        except HTTPException:
            raise
        except Exception as e:
            log.exception("[AudioService] AWS Polly TTS generation error: %s", e)
            raise HTTPException(500, f"AWS Polly TTS generation failed: {str(e)}")
    
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
            tts_config = self.speech_config.get("tts", {}) if self.speech_config else {}
            
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
            elif final_provider == "polly":
                return await self.generate_speech_polly(
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
        app_name: str = "webui",
        provider: Optional[str] = None
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream speech audio for long text with intelligent sentence-based chunking.
        Generates and yields audio chunks immediately for reduced latency.
        
        Args:
            text: Text to convert to speech
            voice: Voice name to use
            user_id: User identifier
            session_id: Session identifier
            app_name: Application name
            provider: Optional provider override (azure, gemini, polly)
            
        Yields:
            Audio data chunks as bytes
        """
    
        # Split text into sentence-based chunks for more natural audio boundaries
        import re
        
        # Split on sentence boundaries (., !, ?, newlines)
        sentences = re.split(r'(?<=[.!?\n])\s+', text)
        
        # Group sentences into smaller chunks for faster initial playback
        MAX_CHUNK_SIZE = 300  # Reduced from 500 for faster first chunk
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
        
        
        # Generate and yield chunks immediately (no buffering)
        for i, chunk in enumerate(chunks):
            log.debug("[AudioService] Generating chunk %d/%d (len=%d)", i+1, len(chunks), len(chunk))
            
            try:
                audio_data = await self.generate_speech(
                    text=chunk,
                    voice=voice,
                    user_id=user_id,
                    session_id=session_id,
                    app_name=app_name,
                    message_id=f"chunk_{i}",
                    provider=provider  # Pass provider to generate_speech
                )
                
                if audio_data:
                    log.debug("[AudioService] Yielding chunk %d (%d bytes)", i+1, len(audio_data))
                    yield audio_data
                    
            except Exception as e:
                log.error("[AudioService] Error generating chunk %d: %s", i, e)
                # Continue with next chunk instead of failing completely
                continue
    
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
        elif final_provider == "polly":
            polly_config = tts_config.get("polly", {})
            voices = polly_config.get("voices", AWS_POLLY_NEURAL_VOICES)
        else:
            voices = []
        
        log.debug("[AudioService] Available voices for provider %s: %d", final_provider, len(voices))
        return voices
    
    def _is_valid_api_key(self, value: Any) -> bool:
        """
        Check if a value is a valid API key (non-empty string that's not an unresolved env var).
        
        Args:
            value: The value to check
            
        Returns:
            True if the value appears to be a valid API key
        """
        if not value:
            return False
        if not isinstance(value, str):
            return False
        # Check if it's an unresolved environment variable placeholder
        if value.startswith("${") or value == "":
            return False
        return True
    
    def get_speech_config(self) -> Dict[str, Any]:
        """
        Get speech configuration for frontend initialization.
        
        Returns:
            Configuration dictionary
        """
        stt_config = self.speech_config.get("stt", {})
        tts_config = self.speech_config.get("tts", {})
        speech_tab = self.speech_config.get("speechTab", {})
        
        # Check each STT provider individually
        stt_openai_valid = False
        stt_azure_valid = False
        if stt_config:
            # Check OpenAI - can be nested under 'openai' or at root level for backward compat
            openai_config = stt_config.get("openai", {})
            openai_api_key = openai_config.get("api_key") or stt_config.get("api_key")
            stt_openai_valid = self._is_valid_api_key(openai_api_key)
            
            azure_config = stt_config.get("azure", {})
            stt_azure_valid = (
                self._is_valid_api_key(azure_config.get("api_key")) and
                self._is_valid_api_key(azure_config.get("region"))
            )
        
        stt_configured = stt_openai_valid or stt_azure_valid
        
        # Check each TTS provider individually
        tts_gemini_valid = False
        tts_azure_valid = False
        tts_polly_valid = False
        if tts_config:
            # Check Gemini - can be nested under 'gemini' or at root level for backward compat
            gemini_nested = tts_config.get("gemini", {})
            gemini_api_key = gemini_nested.get("api_key") or tts_config.get("api_key")
            tts_gemini_valid = self._is_valid_api_key(gemini_api_key)
            
            azure_config = tts_config.get("azure", {})
            tts_azure_valid = (
                self._is_valid_api_key(azure_config.get("api_key")) and
                self._is_valid_api_key(azure_config.get("region"))
            )
            
            polly_config = tts_config.get("polly", {})
            tts_polly_valid = (
                self._is_valid_api_key(polly_config.get("aws_access_key_id")) and
                self._is_valid_api_key(polly_config.get("aws_secret_access_key"))
            )
        
        tts_configured = tts_gemini_valid or tts_azure_valid or tts_polly_valid
        
        config = {
            "sttExternal": stt_configured,
            "ttsExternal": tts_configured,
            # Per-provider configuration status
            "sttProviders": {
                "openai": stt_openai_valid,
                "azure": stt_azure_valid,
            },
            "ttsProviders": {
                "gemini": tts_gemini_valid,
                "azure": tts_azure_valid,
                "polly": tts_polly_valid,
            },
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