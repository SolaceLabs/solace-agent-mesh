---
title: Image Tools
sidebar_position: 50
---

# Image Tools

## Overview

The image tools provide agents with capabilities for generating, editing, and analyzing images. These tools enable multimodal workflows where agents can create visual content, enhance existing images, and extract information from visual data.

### Available Tools

- **create_image_from_description**: Generate images from text descriptions
- **describe_image**: Analyze and describe image contents
- **edit_image_with_gemini**: Edit existing images using AI
- **describe_audio**: Analyze audio content (cross-listed with audio tools)

### Common Use Cases

- Content creation and visual design
- Image analysis and quality inspection
- Visual data extraction and OCR
- Creative iteration and image enhancement
- Multimodal content generation

---

## Tool Reference

### create_image_from_description

Generate images from textual descriptions using AI image generation models.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image_description` | string | Yes | - | The textual prompt describing the desired image |
| `output_filename` | string | No | Auto-generated | Desired filename for the output image (PNG format) |

**Auto-generated filename format**: `generated_image_<uuid>.png`

#### Tool Configuration

Configure the image generation service in your agent's tool configuration:

```yaml
tools:
  - tool_type: builtin
    tool_name: "create_image_from_description"
    tool_config:
      model: "dall-e-3"                    # Image generation model
      api_key: "${OPENAI_API_KEY}"         # API authentication
      api_base: "https://api.openai.com"   # API endpoint
      extra_params:
        size: "1024x1024"                  # Image dimensions
        quality: "hd"                      # Quality level
        n: 1                               # Number of images
```

**Supported Models**:
- OpenAI: `dall-e-3`, `dall-e-2`
- Any LiteLLM-compatible image generation endpoint

#### Configuration Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | string | Image generation model identifier (e.g., `dall-e-3`, `openai/dall-e-3`) |
| `api_key` | string | API authentication key (use environment variables) |
| `api_base` | string | Base URL for the API endpoint |
| `extra_params` | object | Additional model-specific parameters (size, quality, style) |

#### Return Value

```json
{
  "status": "success",
  "message": "Image generated and saved successfully.",
  "output_filename": "generated_image_abc123.png",
  "output_version": 1,
  "result_preview": "Generated image from prompt: 'A sunset over...'"
}
```

#### Output Format

- **File Type**: PNG
- **Versioning**: Automatic artifact versioning
- **Storage**: Saved as artifact with metadata

#### Example Usage

```yaml
# Agent configuration
app_config:
  agent_name: "DesignAgent"
  instruction: "You create visual content based on user descriptions."

  tools:
    - tool_type: builtin
      tool_name: "create_image_from_description"
      tool_config:
        model: "dall-e-3"
        api_key: "${OPENAI_API_KEY}"
        api_base: "https://api.openai.com"
        extra_params:
          size: "1792x1024"
          quality: "hd"
```

**User Interaction**:
```
User: "Create an image of a modern office with plants and natural light"

Agent:
→ Calls create_image_from_description(
    image_description="A modern office interior with large windows, natural sunlight, various indoor plants, minimalist furniture, and a clean aesthetic",
    output_filename="modern_office.png"
  )
→ Returns: "I've created an image of a modern office with plants and natural lighting.
           The image has been saved as 'modern_office.png'."
```

---

### describe_image

Analyze and describe the contents of an image using vision-capable AI models.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image_filename` | string | Yes | - | Filename of the image artifact to analyze (e.g., `photo.png` or `photo.png:2`) |
| `prompt` | string | No | `"What is in this image?"` | Custom analysis prompt for specific information extraction |

**Version Specification**:
- `image.png` - Uses latest version
- `image.png:2` - Uses specific version 2

#### Tool Configuration

```yaml
tools:
  - tool_type: builtin
    tool_name: "describe_image"
    tool_config:
      model: "gpt-4-vision-preview"        # Vision model
      api_key: "${OPENAI_API_KEY}"
      api_base: "https://api.openai.com"
```

**Supported Models**:
- OpenAI: `gpt-4-vision-preview`, `gpt-4-turbo`
- Anthropic: `claude-3-opus-20240229`, `claude-3-sonnet-20240229`
- Google: `gemini-pro-vision`, `gemini-1.5-pro`
- Any OpenAI-compatible vision API

#### Supported Image Formats

- PNG (`.png`)
- JPEG (`.jpg`, `.jpeg`)
- WebP (`.webp`)
- GIF (`.gif`)

#### Return Value

```json
{
  "status": "success",
  "message": "Image described successfully",
  "description": "The image shows a modern office interior...",
  "image_filename": "office_photo.png",
  "image_version": 1,
  "tokens_used": {
    "prompt_tokens": 1250,
    "completion_tokens": 150,
    "total_tokens": 1400
  }
}
```

#### Example Usage

**Basic Image Analysis**:

```
User: "What's in the image 'product_photo.jpg'?"

Agent:
→ Calls describe_image(
    image_filename="product_photo.jpg"
  )
→ Returns: "The image shows a smartphone with a sleek black design,
           displayed at an angle showing both the front screen and side profile..."
```

**Custom Analysis Prompt**:

```
User: "Extract the text from this receipt image"

Agent:
→ Calls describe_image(
    image_filename="receipt.png",
    prompt="Extract all text from this receipt, including store name, items, prices, and total"
  )
→ Returns structured text extraction
```

**Specific Version Analysis**:

```python
describe_image(
    image_filename="document.png:3",  # Analyze version 3 specifically
    prompt="Identify any changes compared to previous versions"
)
```

#### Advanced Use Cases

**Quality Inspection**:
```yaml
prompt: "Inspect this product image for defects, scratches, or inconsistencies"
```

**Content Moderation**:
```yaml
prompt: "Does this image contain any inappropriate or unsafe content?"
```

**Data Extraction**:
```yaml
prompt: "Extract all numbers, dates, and names visible in this document image"
```

---

### edit_image_with_gemini

Edit existing images using Google Gemini's AI-powered image editing capabilities.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image_filename` | string | Yes | - | Filename of the image artifact to edit |
| `edit_prompt` | string | Yes | - | Description of desired edits |
| `output_filename` | string | No | Auto-generated | Desired filename for edited image |

**Auto-generated filename format**: `edited_<original_name>_<uuid>.jpg`

#### Tool Configuration

```yaml
tools:
  - tool_type: builtin
    tool_name: "edit_image_with_gemini"
    tool_config:
      gemini_api_key: "${GOOGLE_API_KEY}"
      model: "gemini-2.0-flash-preview-image-generation"  # Optional, has default
```

**Required**: Google Gemini API key

#### Configuration Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `gemini_api_key` | string | Google Gemini API authentication key |
| `model` | string | Gemini model name (default: `gemini-2.0-flash-preview-image-generation`) |

#### Supported Input Formats

- PNG (`.png`)
- JPEG (`.jpg`, `.jpeg`)
- WebP (`.webp`)
- GIF (`.gif`)

#### Output Format

- **File Type**: JPEG (95% quality)
- **Color Mode**: RGB (RGBA images automatically converted)
- **Versioning**: Automatic artifact versioning

#### Return Value

```json
{
  "status": "success",
  "message": "Image edited and saved successfully.",
  "output_filename": "edited_photo_xyz.jpg",
  "output_version": 1,
  "result_preview": "Image edited successfully",
  "original_filename": "photo.png",
  "original_version": 1
}
```

#### Artifact Metadata

Edited images include comprehensive metadata:

```json
{
  "description": "Image edited with prompt: <edit_prompt>",
  "original_image": "photo.png",
  "original_version": 1,
  "edit_prompt": "Add a blue sky background",
  "editing_tool": "gemini",
  "editing_model": "gemini-2.0-flash-preview-image-generation",
  "request_timestamp": "2024-12-11T10:30:00Z",
  "original_requested_filename": "sunny_photo.jpg",
  "gemini_response_text": "I've added a vibrant blue sky..."
}
```

#### Example Usage

**Background Modification**:

```
User: "Change the background of 'portrait.jpg' to a beach scene"

Agent:
→ Calls edit_image_with_gemini(
    image_filename="portrait.jpg",
    edit_prompt="Replace the background with a tropical beach scene with palm trees and ocean",
    output_filename="portrait_beach.jpg"
  )
→ Returns edited image with beach background
```

**Object Addition**:

```python
edit_image_with_gemini(
    image_filename="room.png",
    edit_prompt="Add a modern floor lamp in the left corner and a potted plant on the table"
)
```

**Style Transfer**:

```python
edit_image_with_gemini(
    image_filename="photo.jpg",
    edit_prompt="Transform this photo into a watercolor painting style while preserving the subject"
)
```

**Color Adjustment**:

```python
edit_image_with_gemini(
    image_filename="product.png",
    edit_prompt="Enhance colors to make them more vibrant and adjust lighting to be brighter"
)
```

#### Best Practices

1. **Be Specific**: Detailed edit prompts yield better results
   ```yaml
   # Good
   edit_prompt: "Remove the person in the red shirt on the left side, fill the space with matching background"

   # Poor
   edit_prompt: "Remove person"
   ```

2. **Preserve Quality**: Start with high-resolution source images

3. **Iterative Editing**: Make incremental changes rather than complex multi-step edits in one prompt

4. **Version Control**: Use version specification to track edit history

---

### describe_audio

Analyze audio content using multimodal AI models. This tool is cross-listed with audio tools.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio_filename` | string | Yes | - | Filename of the audio artifact to analyze |
| `prompt` | string | No | `"What is in this recording?"` | Custom analysis prompt |

#### Tool Configuration

```yaml
tools:
  - tool_type: builtin
    tool_name: "describe_audio"
    tool_config:
      model: "gpt-4-turbo"
      api_key: "${OPENAI_API_KEY}"
      api_base: "https://api.openai.com"
```

#### Supported Audio Formats

- WAV (`.wav`)
- MP3 (`.mp3`)

#### Return Value

```json
{
  "status": "success",
  "message": "Audio described successfully",
  "description": "The audio contains a conversation between two people...",
  "audio_filename": "recording.wav",
  "audio_version": 1,
  "tokens_used": {
    "prompt_tokens": 800,
    "completion_tokens": 120,
    "total_tokens": 920
  }
}
```

#### Example Usage

**Content Analysis**:

```
User: "What's in the audio file 'meeting.wav'?"

Agent:
→ Calls describe_audio(
    audio_filename="meeting.wav",
    prompt="Summarize the key discussion points from this meeting recording"
  )
→ Returns summary of meeting content
```

**Audio Quality Assessment**:

```python
describe_audio(
    audio_filename="podcast.mp3",
    prompt="Assess the audio quality, identify any background noise or distortions"
)
```

---

## Configuration Examples

### Complete Agent with Image Tools

```yaml
apps:
  - name: creative_agent
    app_module: solace_agent_mesh.agent.sac.app
    app_config:
      namespace: "creative/prod"
      agent_name: "CreativeDesignAgent"
      instruction: |
        You are a creative design assistant. You can:
        - Generate images from descriptions
        - Analyze existing images
        - Edit and enhance images
        - Provide design feedback

      model: "gemini-1.5-pro"

      tools:
        # Enable all image tools
        - tool_type: builtin-group
          group_name: "image"

        # Or enable individually with custom configs
        - tool_type: builtin
          tool_name: "create_image_from_description"
          tool_config:
            model: "dall-e-3"
            api_key: "${OPENAI_API_KEY}"
            api_base: "https://api.openai.com"
            extra_params:
              size: "1792x1024"
              quality: "hd"

        - tool_type: builtin
          tool_name: "describe_image"
          tool_config:
            model: "gpt-4-vision-preview"
            api_key: "${OPENAI_API_KEY}"
            api_base: "https://api.openai.com"

        - tool_type: builtin
          tool_name: "edit_image_with_gemini"
          tool_config:
            gemini_api_key: "${GOOGLE_API_KEY}"

        # Artifact management for image workflows
        - tool_type: builtin-group
          group_name: "artifact_management"
```

### Environment Variables Setup

```bash
# .env file
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIzaSy...

# For production, use secret management
# AWS Secrets Manager, Google Secret Manager, etc.
```

### Tool Group Configuration

Enable all image tools at once:

```yaml
tools:
  - tool_type: builtin-group
    group_name: "image"
    # Enables: create_image_from_description, describe_image,
    #          edit_image_with_gemini, describe_audio
```

---

## Security and Access Control

### Required Scopes

Image tools require specific scopes for access control:

| Tool | Required Scope |
|------|----------------|
| `create_image_from_description` | `tool:image:create` |
| `describe_image` | `tool:image:describe` |
| `edit_image_with_gemini` | `tool:image:edit` |
| `describe_audio` | `tool:audio:describe` |

### RBAC Configuration

Restrict image tool access by user role:

```yaml
# roles.yaml
roles:
  - name: "creative_team"
    scopes:
      - "tool:image:*"  # All image tools
      - "tool:artifact:*"

  - name: "basic_user"
    scopes:
      - "tool:image:describe"  # Analysis only, no generation/editing
```