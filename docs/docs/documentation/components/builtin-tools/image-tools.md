---
title: Image Tools
sidebar_position: 35
---

# Image Tools

## Overview

The image tools provide agents with capabilities for generating, editing, and analyzing images. These tools enable multimodal workflows where agents can create visual content, enhance existing images, and extract information from visual data.

### Available Tools

- **create_image_from_description**: Generate images from text descriptions
- **describe_image**: Analyze and describe image contents
- **edit_image_with_gemini**: Edit existing images using AI
- **describe_audio**: Analyze audio content (cross-listed with audio tools)

## Tool Reference

### create_image_from_description

Generate images from textual descriptions using AI image generation models.

#### Tool Configuration

Configure the image generation service in your agent's tool configuration:

```yaml
tools:
  - tool_type: builtin
    tool_name: "create_image_from_description"
    tool_config:
      model: "imagen-4-ultra"       # Image generation model
      api_key: "${API_KEY}"         # API authentication
      api_base: "https://ENDPOINT"   # API endpoint
```

#### Configuration Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | string | Image generation model identifier |
| `api_key` | string | API authentication key (use environment variables) |
| `api_base` | string | Base URL for the API endpoint |


#### Output Format

- **File Type**: PNG

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
        model: "imagen-4-ultra"
        api_key: "${OPENAI_API_KEY}"
        api_base: "https://api.openai.com"
```

---

### describe_image

Analyze and describe the contents of an image using vision-capable AI models.

#### Tool Configuration

```yaml
tools:
  - tool_type: builtin
    tool_name: "describe_image"
    tool_config:
      model: "gemini-2.5-flash"       # Vision model
      api_key: "${API_KEY}"
      api_base: "https://ENDPOINT"
```

#### Supported Image Formats

- PNG (`.png`)
- JPEG (`.jpg`, `.jpeg`)
- WebP (`.webp`)
- GIF (`.gif`)


### edit_image_with_gemini

Edit existing images using Google Gemini's AI-powered image editing capabilities.

#### Tool Configuration

```yaml
tools:
  - tool_type: builtin
    tool_name: "edit_image_with_gemini"
    tool_config:
      gemini_api_key: "${GOOGLE_API_KEY}"
      model: "gemini-2.5-flash-image"
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


### Tool Group Configuration

Enable all image tools at once:

```yaml
tools:
  - tool_type: builtin-group
    group_name: "image"
```
