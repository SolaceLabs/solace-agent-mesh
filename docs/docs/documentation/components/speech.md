# Speech Integration

Agent Mesh provides speech capabilities through integrated Speech-to-Text (STT) and Text-to-Speech (TTS) services. You can enable users to interact with agents through voice input and receive spoken responses, creating more natural and accessible conversational experiences.

## Understanding Speech Integration

The speech system consists of two complementary services that work together to enable voice interactions. The STT service converts spoken audio into text that agents can process, while the TTS service transforms agent responses into natural-sounding speech. Both services support multiple providers and can be configured independently based on your requirements.

The system integrates with the WebUI gateway to provide seamless voice interactions in chat interfaces. When you enable speech features, users see microphone and speaker controls that allow them to speak their questions and hear agent responses without typing.

## Configuring Speech Services

You configure speech services in your gateway YAML file under the `app_config.speech` section. The configuration defines which providers to use, authentication credentials, and service-specific settings that control behavior and quality.

### Speech-to-Text Configuration

The STT service transcribes audio input into text using either OpenAI's Whisper API or Azure Speech Services. You specify the provider and its credentials in your configuration:

```yaml
app_config:
  speech:
    stt:
      provider: openai  # or "azure"
      openai:
        api_key: ${OPENAI_API_KEY}
        url: https://api.openai.com/v1/audio/transcriptions
        model: whisper-1
```

When using Azure Speech Services, you provide your subscription key and region:

```yaml
app_config:
  speech:
    stt:
      provider: azure
      azure:
        api_key: ${AZURE_SPEECH_KEY}
        region: eastus
        language: en-US
```

The system validates audio files before transcription, rejecting files larger than 25MB or with unsupported formats. Supported formats include WAV, MP3, WebM, and OGG.

### Text-to-Speech Configuration

The TTS service generates natural-sounding speech from text using either Google's Gemini or Azure Neural Voices. You configure the provider, voice selection, and quality settings:

```yaml
app_config:
  speech:
    tts:
      provider: gemini  # or "azure"
      gemini:
        api_key: ${GEMINI_API_KEY}
        model: gemini-2.5-flash-preview-tts
        default_voice: Kore
        voices:
          - Kore
          - Puck
          - Charon
          - Kore
          - Fenrir
          - Aoede
```

Azure Neural Voices offer high-definition voices with natural prosody:

```yaml
app_config:
  speech:
    tts:
      provider: azure
      azure:
        api_key: ${AZURE_SPEECH_KEY}
        region: eastus
        default_voice: en-US-Ava:DragonHDLatestNeural
        voices:
          - en-US-Ava:DragonHDLatestNeural
          - en-US-Andrew:DragonHDLatestNeural
          - en-US-Emma:DragonHDLatestNeural
          - en-US-Brian:DragonHDLatestNeural
```

The system automatically chunks long text into manageable segments for streaming playback, reducing latency and improving the user experience.

## Enabling Speech Features

Speech features are disabled by default and require explicit configuration to appear in the user interface. You control feature visibility through the `frontend_feature_enablement` section:

```yaml
app_config:
  frontend_feature_enablement:
    speechToText: true
    textToSpeech: true
```

When you enable these flags, the WebUI displays microphone and speaker controls in the chat interface. Users can click the microphone to record voice input or the speaker icon to hear agent responses.

## Managing User Settings

Users can customize their speech experience through the settings panel. The system provides controls for voice selection, playback speed, and automatic playback behavior. You can set default values that users can override:

```yaml
app_config:
  speech:
    speechTab:
      speechToText:
        speechToText: true
        engineSTT: external
        languageSTT: en-US
      textToSpeech:
        textToSpeech: true
        engineTTS: external
        voice: Kore
        playbackRate: 1.0
```

## Monitoring Speech Usage

Speech services consume API credits based on audio duration and text length. OpenAI charges per minute of audio transcribed, while Gemini and Azure charge per character of text synthesized. You should monitor usage through your provider's dashboard and set appropriate rate limits to control costs.

The system logs all speech operations, including transcription requests, TTS generation, and any errors encountered. You can use these logs to track usage patterns, identify issues, and optimize your configuration for better performance and cost efficiency.

## Troubleshooting Speech Issues

When speech features do not appear in the interface, verify that you have enabled the feature flags in your configuration and that the gateway has restarted to load the new settings. Check the browser console for any JavaScript errors that might prevent the speech controls from rendering.

If transcription fails, confirm that your API keys are valid and that you have sufficient credits with your provider. The system returns specific error messages for common issues like unsupported audio formats, files that are too large, or API authentication failures.

For TTS problems, verify that your selected voice is available for your provider and region. Some voices require specific API versions or subscription tiers. The system falls back to default voices when requested voices are unavailable, but you should configure appropriate defaults to ensure consistent behavior.

## Security Considerations

Audio data passes through your gateway to external speech providers. The system does not store audio recordings by default, but transcribed text becomes part of the conversation history. You should inform users about data handling practices and comply with relevant privacy regulations when processing voice data.

## Integration Examples

For a complete working example, see the WebUI gateway configuration in `templates/webui.yaml`. This configuration demonstrates all speech settings with appropriate defaults and shows how to structure your YAML for production use.