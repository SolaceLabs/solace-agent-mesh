---
title: Audio Tools
sidebar_position: 30
---

# Using Text-to-Speech (TTS) Tools

This guide provides technical documentation for the text-to-speech (TTS) tools available in Agent Mesh.

## Overview

The `audio` tool group provides two primary TTS tools for generating high-quality audio artifacts:

1.  **`text_to_speech`**: Converts a string of text to speech using a single voice, featuring intelligent tone selection.
2.  **`multi_speaker_text_to_speech`**: Converts a conversational script, delineated by speaker, into a multi-speaker audio file.

## Setup and Configuration

### Prerequisites
- **API Key**: A valid Google Gemini API key with access to the TTS model is required.
- **Dependencies**: The `pydub` library is necessary for audio processing and format conversion. It can be installed via `pip install pydub`.

### Basic Configuration
1.  **Environment Variable**: The Gemini API key must be set as an environment variable.
    ```bash
    export GEMINI_API_KEY="your_gemini_api_key_here"
    ```
2.  **Enablement**: The `audio` tool group must be enabled in the agent's `app_config.yml`.
    ```yaml
    tools:
      - tool_type: builtin-group
        group_name: "audio"
    ```

## Advanced Configuration

You can exercise more granular control over the TTS tools by providing a `tool_config` block for each tool in your `app_config.yml`.

### `text_to_speech` Configuration

This example shows how to set a default voice and define the mapping between tones and specific voice models.

```yaml
- tool_type: builtin
  tool_name: "text_to_speech"
  tool_config:
    gemini_api_key: ${GEMINI_API_KEY}
    model: "gemini-2.5-flash-preview-tts"
    voice_name: "Kore"  # Default voice if no tone is matched
    language: "en-US"   # Default language
    output_format: "mp3"
    # Voice selection by tone mapping
    voice_tone_mapping:
      bright: ["Zephyr", "Autonoe"]
      upbeat: ["Puck", "Laomedeia"]
      informative: ["Charon", "Rasalgethi"]
      firm: ["Kore", "Orus", "Alnilam"]
      friendly: ["Achird"]
      casual: ["Zubenelgenubi"]
      warm: ["Sulafar"]
```

### `multi_speaker_text_to_speech` Configuration

This example defines default voice configurations for up to five speakers.

```yaml
- tool_type: builtin
  tool_name: "multi_speaker_text_to_speech"
  tool_config:
    gemini_api_key: ${GEMINI_API_KEY}
    model: "gemini-2.5-flash-preview-tts"
    language: "en-US"
    output_format: "mp3"
    # Default speaker voice configurations
    default_speakers:
      - { name: "Speaker1", voice: "Kore", tone: "firm" }
      - { name: "Speaker2", voice: "Puck", tone: "upbeat" }
      - { name: "Speaker3", voice: "Charon", tone: "informative" }
      - { name: "Speaker4", voice: "Achird", tone: "friendly" }
      - { name: "Speaker5", voice: "Sulafar", tone: "warm" }
    # The voice_tone_mapping can also be included here
```

## Features

### Intelligent Tone Selection
The system supports tone-based voice selection, allowing for dynamic voice choice based on desired emotional or stylistic output, rather than explicit voice names.

**Available Tones**:
`bright`, `upbeat`, `informative`, `firm`, `excitable`, `youthful`, `breezy`, `easy-going`, `breathy`, `clear`, `smooth`, `gravelly`, `soft`, `even`, `mature`, `forward`, `friendly`, `casual`, `gentle`, `lively`, `knowledgeable`, `warm`

**Tone Aliases**:
- `professional` → `firm`
- `cheerful` → `upbeat`
- `calm` → `soft`
- `conversational` → `casual`

### Multi-Language Support
The tools support over 25 languages, specified via BCP-47 language codes (for example, `en-US`, `fr-FR`, `es-US`, `ja-JP`).

## Usage Examples

### Single-Voice Text-to-Speech (`text_to_speech`)

**Basic Usage**
```
Convert the following text to speech: "Welcome to the technical briefing on artificial intelligence."
```

**With Tone Selection**
```
Convert this text to speech with a professional tone: "Thank you for joining today's technical review."
```

### Multi-Speaker Text-to-Speech (`multi_speaker_text_to_speech`)

**Basic Conversation**
```
Convert this conversation to speech:
Speaker1: Welcome to the podcast.
Speaker2: Thank you for having me.
```

**With Custom Speaker Tones**
```
Convert this conversation using specific tones for each speaker:
- Speaker1 should sound professional
- Speaker2 should sound friendly

Conversation:
Speaker1: Good morning, this is the daily security briefing.
Speaker2: Hi everyone, let's review the agenda for today's session.
```

## Tool Reference

### `text_to_speech`
| Parameter         | Type   | Description                   |
| ----------------- | ------ | ----------------------------- |
| `text`            | string | The text to be synthesized.   |
| `output_filename` | string | (Optional) A custom MP3 filename. |
| `voice_name`      | string | (Optional) A specific voice name to use. |
| `tone`            | string | (Optional) The desired voice tone.  |
| `language`        | string | (Optional) The BCP-47 language code. |

### `multi_speaker_text_to_speech`
| Parameter           | Type  | Description                               |
| ------------------- | ----- | ----------------------------------------- |
| `conversation_text` | string| A string of text with speaker labels (for example, `S1: ...`). |
| `output_filename`   | string| (Optional) A custom MP3 filename.           |
| `speaker_configs`   | array | (Optional) An array to configure tones for specific speakers.  |
| `language`          | string| (Optional) The BCP-47 language code.          |

## Output and Metadata

Both tools generate an MP3 audio artifact that includes a rich set of metadata:
- The source text (or a truncated version for long inputs)
- The voice(s) and language used for synthesis
- The generation timestamp and the specific tool invoked
- The requested tone and any speaker-specific configurations

## Troubleshooting

- **`Error: GEMINI_API_KEY is required`**: This indicates that the `GEMINI_API_KEY` environment variable has not been set correctly.
- **`Warning: Unknown tone 'xyz'`**: The specified tone is not recognized. Refer to the list of supported tones. The system will fall back to a default voice.
- **`Error: Failed to convert WAV to MP3`**: This typically indicates that `pydub` is not installed or that the underlying system is missing necessary audio codecs (for example, `ffmpeg`).
