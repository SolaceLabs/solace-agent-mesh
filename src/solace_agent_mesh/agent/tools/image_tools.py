"""
Collection of Python tools for image generation, manipulation, and multimodal content analysis.
Includes tools for image description and audio description using vision and audio APIs.
"""

import logging
import asyncio
import base64
import inspect
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from google.adk.tools import ToolContext

from ..utils.artifact_helpers import (
    save_artifact_with_metadata,
    DEFAULT_SCHEMA_MAX_KEYS,
)
from ..utils.context_helpers import get_original_session_id

from google.genai import types as adk_types
from .tool_definition import BuiltinTool
from .registry import tool_registry

log = logging.getLogger(__name__)

async def create_image_from_description(
    image_description: str,
    output_filename: Optional[str] = None,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generates an image based on a textual description using LiteLLM and saves it as a PNG artifact.
    Configuration for LiteLLM (model, api_key, etc.) is expected in `tool_config`.

    Args:
        image_description: The textual prompt to use for image generation.
        output_filename: Optional. The desired filename for the output PNG image.
                         If not provided, a unique name like 'generated_image_<uuid>.png' will be used.
        tool_context: The context provided by the ADK framework.
        tool_config: Optional dictionary containing specific configuration for this tool.

    Returns:
        A dictionary containing:
        - "status": "success" or "error".
        - "message": A descriptive message about the outcome.
        - "output_filename": The name of the saved image artifact (if successful).
        - "output_version": The version of the saved image artifact (if successful).
        - "result_preview": A brief preview message (if successful).
    """
    log_identifier = f"[ImageTools:create_image_from_description]"
    if not tool_context:
        log.error(f"{log_identifier} ToolContext is missing.")
        return {"status": "error", "message": "ToolContext is missing."}

    try:
        inv_context = tool_context._invocation_context
        if not inv_context:
            raise ValueError("InvocationContext is not available.")

        app_name = getattr(inv_context, "app_name", None)
        user_id = getattr(inv_context, "user_id", None)
        session_id = get_original_session_id(inv_context)
        artifact_service = getattr(inv_context, "artifact_service", None)

        if not all([app_name, user_id, session_id, artifact_service]):
            missing_parts = [
                part
                for part, val in [
                    ("app_name", app_name),
                    ("user_id", user_id),
                    ("session_id", session_id),
                    ("artifact_service", artifact_service),
                ]
                if not val
            ]
            raise ValueError(
                f"Missing required context parts: {', '.join(missing_parts)}"
            )

        log.info(f"{log_identifier} Processing request for session {session_id}.")

        current_tool_config = tool_config if tool_config is not None else {}

        if not current_tool_config:
            log.warning(
                f"{log_identifier} Tool-specific configuration (tool_config) is empty."
            )

        model_name = current_tool_config.get("model")
        api_key = current_tool_config.get("api_key")
        api_base = current_tool_config.get("api_base")
        extra_params = current_tool_config.get("extra_params", {})

        if not model_name:
            raise ValueError("'model' configuration is missing in tool_config.")
        if not api_key:
            raise ValueError("'api_key' configuration is missing in tool_config.")
        if not api_base:
            raise ValueError("'api_base' configuration is missing in tool_config.")

        if "/" in model_name:
            original_model_name = model_name
            model_name = model_name.split("/", 1)[-1]
            log.debug(
                f"{log_identifier} Original model name '{original_model_name}' processed to '{model_name}' for API call."
            )

        log.debug(
            f"{log_identifier} Using image generation model: {model_name} via direct API call to: {api_base}"
        )

        api_url = f"{api_base.rstrip('/')}/v1/images/generations"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {"model": model_name, "prompt": image_description, **extra_params}

        log.debug(
            f"{log_identifier} Calling image generation API with prompt: '{image_description[:100]}...' and payload: {json.dumps(payload)}"
        )

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                http_response = await client.post(
                    api_url, headers=headers, json=payload
                )
                http_response.raise_for_status()
                response_data = http_response.json()
        except httpx.HTTPStatusError as hse:
            log.error(
                f"{log_identifier} HTTP error calling image generation API {hse.request.url}: {hse.response.status_code} - {hse.response.text}"
            )
            return {
                "status": "error",
                "message": f"API error generating image: {hse.response.status_code} - {hse.response.text}",
            }
        except httpx.RequestError as re:
            log.error(
                f"{log_identifier} Request error calling image generation API {re.request.url}: {re}"
            )
            return {
                "status": "error",
                "message": f"Request error generating image: {re}",
            }
        except Exception as e:
            log.error(f"{log_identifier} Error calling image generation API: {e}")
            return {"status": "error", "message": f"Error generating image: {e}"}

        log.debug(f"{log_identifier} Image generation API response received.")

        if (
            not response_data
            or not response_data.get("data")
            or not response_data["data"][0]
        ):
            log.error(
                f"{log_identifier} API did not return valid image data. Response: {json.dumps(response_data)}"
            )
            raise ValueError("Image generation API did not return valid image data.")

        image_data_item = response_data["data"][0]
        image_bytes = None

        if image_data_item.get("url"):
            image_url = image_data_item["url"]
            log.info(f"{log_identifier} Fetching image from URL: {image_url}")
            async with httpx.AsyncClient() as client:
                http_response = await client.get(image_url, timeout=30.0)
                http_response.raise_for_status()
                image_bytes = http_response.content
            log.info(f"{log_identifier} Image fetched successfully from URL.")
        elif image_data_item.get("b64_json"):
            log.info(f"{log_identifier} Decoding image from b64_json.")
            image_bytes = base64.b64decode(image_data_item["b64_json"])
            log.info(f"{log_identifier} Image decoded successfully from b64_json.")
        else:
            raise ValueError(
                "No valid image data (URL or b64_json) found in LiteLLM response."
            )

        if not image_bytes:
            raise ValueError("Failed to retrieve image bytes.")

        final_output_filename = ""
        if output_filename:
            if not output_filename.lower().endswith(".png"):
                final_output_filename = f"{output_filename}.png"
            else:
                final_output_filename = output_filename
        else:
            final_output_filename = f"generated_image_{uuid.uuid4()}.png"
        log.debug(
            f"{log_identifier} Determined output filename: {final_output_filename}"
        )

        output_mime_type = "image/png"
        current_timestamp_iso = datetime.now(timezone.utc).isoformat()

        metadata_dict = {
            "description": f"Image generated from prompt: {image_description}",
            "source_prompt": image_description,
            "generation_tool": "direct_api",
            "generation_model": model_name,
            "request_timestamp": current_timestamp_iso,
            "original_requested_filename": (
                output_filename if output_filename else "N/A"
            ),
        }
        if extra_params:
            metadata_dict["api_request_params"] = json.dumps(extra_params)

        log.info(
            f"{log_identifier} Saving artifact '{final_output_filename}' with mime_type '{output_mime_type}'."
        )
        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=final_output_filename,
            content_bytes=image_bytes,
            mime_type=output_mime_type,
            metadata_dict=metadata_dict,
            timestamp=datetime.now(timezone.utc),
            schema_max_keys=DEFAULT_SCHEMA_MAX_KEYS,
            tool_context=tool_context,
        )

        if save_result.get("status") == "error":
            raise IOError(
                f"Failed to save image artifact: {save_result.get('message', 'Unknown error')}"
            )

        log.info(
            f"{log_identifier} Artifact '{final_output_filename}' v{save_result['data_version']} saved successfully."
        )

        return {
            "status": "success",
            "message": "Image generated and saved successfully.",
            "output_filename": final_output_filename,
            "output_version": save_result["data_version"],
            "result_preview": f"Image '{final_output_filename}' (v{save_result['data_version']}) created from prompt: \"{image_description[:50]}...\"",
        }

    except ValueError as ve:
        log.error(f"{log_identifier} Value error: {ve}")
        return {"status": "error", "message": str(ve)}
    except httpx.HTTPStatusError as hse:
        log.error(
            f"{log_identifier} HTTP error fetching image from URL {hse.request.url}: {hse.response.status_code} - {hse.response.text}"
        )
        return {
            "status": "error",
            "message": f"HTTP error fetching image: {hse.response.status_code}",
        }
    except httpx.RequestError as re:
        log.error(
            f"{log_identifier} Request error fetching image from URL {re.request.url}: {re}"
        )
        return {"status": "error", "message": f"Request error fetching image: {re}"}
    except IOError as ioe:
        log.error(f"{log_identifier} IO error: {ioe}")
        return {"status": "error", "message": str(ioe)}
    except Exception as e:
        log.exception(
            f"{log_identifier} Unexpected error in create_image_from_description: {e}"
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def _get_image_mime_type(filename: str) -> str:
    """Get MIME type from file extension."""
    ext = os.path.splitext(filename)[1].lower()
    mime_mapping = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return mime_mapping.get(ext, "application/octet-stream")


def _is_supported_image_format(filename: str) -> bool:
    """Check if the image format is supported."""
    ext = os.path.splitext(filename)[1].lower()
    supported_formats = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    return ext in supported_formats


def _create_data_url(image_bytes: bytes, mime_type: str) -> str:
    """Create base64 data URL from image bytes."""
    base64_data = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{base64_data}"


async def describe_image(
    image_filename: str,
    prompt: str = "What is in this image?",
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Describes an image using an OpenAI-compatible vision API.

    Args:
        image_filename: The filename (and optional :version) of the input image artifact.
        prompt: Custom prompt for image analysis (default: "What is in this image?").
        tool_context: The context provided by the ADK framework.
        tool_config: Configuration dictionary containing model, api_base, api_key.

    Returns:
        A dictionary containing:
        - "status": "success" or "error".
        - "message": A descriptive message about the outcome.
        - "description": The image description from the API (if successful).
        - "image_filename": The name of the input image artifact (if successful).
        - "image_version": The version of the input image artifact (if successful).
        - "tokens_used": Token usage information from the API (if available).
    """
    log_identifier = f"[ImageTools:describe_image:{image_filename}]"
    if not tool_context:
        log.error(f"{log_identifier} ToolContext is missing.")
        return {"status": "error", "message": "ToolContext is missing."}

    try:
        inv_context = tool_context._invocation_context
        if not inv_context:
            raise ValueError("InvocationContext is not available.")

        app_name = getattr(inv_context, "app_name", None)
        user_id = getattr(inv_context, "user_id", None)
        session_id = get_original_session_id(inv_context)
        artifact_service = getattr(inv_context, "artifact_service", None)

        if not all([app_name, user_id, session_id, artifact_service]):
            missing_parts = [
                part
                for part, val in [
                    ("app_name", app_name),
                    ("user_id", user_id),
                    ("session_id", session_id),
                    ("artifact_service", artifact_service),
                ]
                if not val
            ]
            raise ValueError(
                f"Missing required context parts: {', '.join(missing_parts)}"
            )

        log.info(f"{log_identifier} Processing request for session {session_id}.")

        current_tool_config = tool_config if tool_config is not None else {}

        if not current_tool_config:
            log.warning(
                f"{log_identifier} Tool-specific configuration (tool_config) is empty."
            )

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

        parts = image_filename.rsplit(":", 1)
        filename_base_for_load = parts[0]
        version_str = parts[1] if len(parts) > 1 else None
        version_to_load = int(version_str) if version_str else None

        if not _is_supported_image_format(filename_base_for_load):
            raise ValueError(
                f"Unsupported image format. Supported formats: .png, .jpg, .jpeg, .webp, .gif"
            )

        if version_to_load is None:
            list_versions_method = getattr(artifact_service, "list_versions")
            if inspect.iscoroutinefunction(list_versions_method):
                versions = await list_versions_method(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename_base_for_load,
                )
            else:
                versions = await asyncio.to_thread(
                    list_versions_method,
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename_base_for_load,
                )
            if not versions:
                raise FileNotFoundError(
                    f"Image artifact '{filename_base_for_load}' not found."
                )
            version_to_load = max(versions)
            log.debug(
                f"{log_identifier} Using latest version for input: {version_to_load}"
            )

        load_artifact_method = getattr(artifact_service, "load_artifact")
        if inspect.iscoroutinefunction(load_artifact_method):
            image_artifact_part = await load_artifact_method(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename_base_for_load,
                version=version_to_load,
            )
        else:
            image_artifact_part = await asyncio.to_thread(
                load_artifact_method,
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename_base_for_load,
                version=version_to_load,
            )

        if not image_artifact_part or not image_artifact_part.inline_data:
            raise FileNotFoundError(
                f"Content for image artifact '{filename_base_for_load}' v{version_to_load} not found."
            )

        image_bytes = image_artifact_part.inline_data.data
        log.debug(f"{log_identifier} Loaded image artifact: {len(image_bytes)} bytes")

        mime_type = _get_image_mime_type(filename_base_for_load)
        data_url = _create_data_url(image_bytes, mime_type)
        log.debug(f"{log_identifier} Created data URL with MIME type: {mime_type}")

        api_url = f"{api_base.rstrip('/')}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        request_data = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        }

        log.debug(
            f"{log_identifier} Calling vision API with prompt: '{prompt[:100]}...'"
        )

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(api_url, headers=headers, json=request_data)
            response.raise_for_status()
            response_data = response.json()
        log.debug(f"{log_identifier} Vision API response received.")

        if not response_data.get("choices") or not response_data["choices"]:
            raise ValueError("API response does not contain valid choices.")

        choice = response_data["choices"][0]
        if not choice.get("message") or not choice["message"].get("content"):
            raise ValueError("API response does not contain valid message content.")

        description = choice["message"]["content"]

        tokens_used = response_data.get("usage", {})

        log.info(
            f"{log_identifier} Image described successfully. Description length: {len(description)} characters"
        )

        return {
            "status": "success",
            "message": "Image described successfully",
            "description": description,
            "image_filename": filename_base_for_load,
            "image_version": version_to_load,
            "tokens_used": tokens_used,
        }

    except FileNotFoundError as e:
        log.warning(f"{log_identifier} File not found error: {e}")
        return {"status": "error", "message": str(e)}
    except ValueError as ve:
        log.error(f"{log_identifier} Value error: {ve}")
        return {"status": "error", "message": str(ve)}
    except httpx.HTTPStatusError as hse:
        log.error(
            f"{log_identifier} HTTP error calling vision API: {hse.response.status_code} - {hse.response.text}"
        )
        return {"status": "error", "message": f"API error: {hse.response.status_code}"}
    except httpx.RequestError as re:
        log.error(f"{log_identifier} Request error calling vision API: {re}")
        return {"status": "error", "message": f"Request error: {re}"}
    except json.JSONDecodeError as jde:
        log.error(f"{log_identifier} JSON decode error: {jde}")
        return {"status": "error", "message": "Invalid JSON response from API"}
    except Exception as e:
        log.exception(f"{log_identifier} Unexpected error in describe_image: {e}")
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def _get_audio_format(filename: str) -> str:
    """Get audio format from file extension."""
    ext = os.path.splitext(filename)[1].lower()
    format_mapping = {".wav": "wav", ".mp3": "mp3"}
    return format_mapping.get(ext, "wav")


def _is_supported_audio_format(filename: str) -> bool:
    """Check if the audio format is supported."""
    ext = os.path.splitext(filename)[1].lower()
    supported_formats = {".wav", ".mp3"}
    return ext in supported_formats


def _encode_audio_to_base64(audio_bytes: bytes) -> str:
    """Encode audio bytes to base64 string."""
    return base64.b64encode(audio_bytes).decode("utf-8")


async def describe_audio(
    audio_filename: str,
    prompt: str = "What is in this recording?",
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Describes an audio recording using an OpenAI-compatible audio API.

    Args:
        audio_filename: The filename (and optional :version) of the input audio artifact.
        prompt: Custom prompt for audio analysis (default: "What is in this recording?").
        tool_context: The context provided by the ADK framework.
        tool_config: Configuration dictionary containing model, api_base, api_key.

    Returns:
        A dictionary containing:
        - "status": "success" or "error".
        - "message": A descriptive message about the outcome.
        - "description": The audio description from the API (if successful).
        - "audio_filename": The name of the input audio artifact (if successful).
        - "audio_version": The version of the input audio artifact (if successful).
        - "tokens_used": Token usage information from the API (if available).
    """
    log_identifier = f"[ImageTools:describe_audio:{audio_filename}]"
    if not tool_context:
        log.error(f"{log_identifier} ToolContext is missing.")
        return {"status": "error", "message": "ToolContext is missing."}

    try:
        inv_context = tool_context._invocation_context
        if not inv_context:
            raise ValueError("InvocationContext is not available.")

        app_name = getattr(inv_context, "app_name", None)
        user_id = getattr(inv_context, "user_id", None)
        session_id = get_original_session_id(inv_context)
        artifact_service = getattr(inv_context, "artifact_service", None)

        if not all([app_name, user_id, session_id, artifact_service]):
            missing_parts = [
                part
                for part, val in [
                    ("app_name", app_name),
                    ("user_id", user_id),
                    ("session_id", session_id),
                    ("artifact_service", artifact_service),
                ]
                if not val
            ]
            raise ValueError(
                f"Missing required context parts: {', '.join(missing_parts)}"
            )

        log.info(f"{log_identifier} Processing request for session {session_id}.")

        current_tool_config = tool_config if tool_config is not None else {}

        if not current_tool_config:
            log.warning(
                f"{log_identifier} Tool-specific configuration (tool_config) is empty."
            )

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

        parts = audio_filename.rsplit(":", 1)
        filename_base_for_load = parts[0]
        version_str = parts[1] if len(parts) > 1 else None
        version_to_load = int(version_str) if version_str else None

        if not _is_supported_audio_format(filename_base_for_load):
            raise ValueError(f"Unsupported audio format. Supported formats: .wav, .mp3")

        if version_to_load is None:
            list_versions_method = getattr(artifact_service, "list_versions")
            if inspect.iscoroutinefunction(list_versions_method):
                versions = await list_versions_method(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename_base_for_load,
                )
            else:
                versions = await asyncio.to_thread(
                    list_versions_method,
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename_base_for_load,
                )
            if not versions:
                raise FileNotFoundError(
                    f"Audio artifact '{filename_base_for_load}' not found."
                )
            version_to_load = max(versions)
            log.debug(
                f"{log_identifier} Using latest version for input: {version_to_load}"
            )

        load_artifact_method = getattr(artifact_service, "load_artifact")
        if inspect.iscoroutinefunction(load_artifact_method):
            audio_artifact_part = await load_artifact_method(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename_base_for_load,
                version=version_to_load,
            )
        else:
            audio_artifact_part = await asyncio.to_thread(
                load_artifact_method,
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename_base_for_load,
                version=version_to_load,
            )

        if not audio_artifact_part or not audio_artifact_part.inline_data:
            raise FileNotFoundError(
                f"Content for audio artifact '{filename_base_for_load}' v{version_to_load} not found."
            )

        audio_bytes = audio_artifact_part.inline_data.data
        log.debug(f"{log_identifier} Loaded audio artifact: {len(audio_bytes)} bytes")

        audio_format = _get_audio_format(filename_base_for_load)
        base64_audio = _encode_audio_to_base64(audio_bytes)
        log.debug(
            f"{log_identifier} Encoded audio to base64 with format: {audio_format}"
        )

        api_url = f"{api_base.rstrip('/')}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        request_data = {
            "model": model_name,
            "modalities": ["audio", "text"],
            "audio": {"voice": "alloy", "format": audio_format},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": base64_audio,
                                "format": audio_format,
                            },
                        },
                    ],
                }
            ],
        }

        log.debug(
            f"{log_identifier} Calling audio API with prompt: '{prompt[:100]}...'"
        )

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(api_url, headers=headers, json=request_data)
            response.raise_for_status()
            response_data = response.json()

        log.debug(f"{log_identifier} Audio API response received.")

        if not response_data.get("choices") or not response_data["choices"]:
            raise ValueError("API response does not contain valid choices.")

        choice = response_data["choices"][0]
        if not choice.get("message") or not choice["message"].get("content"):
            raise ValueError("API response does not contain valid message content.")

        description = choice["message"]["content"]

        tokens_used = response_data.get("usage", {})

        log.info(
            f"{log_identifier} Audio described successfully. Description length: {len(description)} characters"
        )

        return {
            "status": "success",
            "message": "Audio described successfully",
            "description": description,
            "audio_filename": filename_base_for_load,
            "audio_version": version_to_load,
            "tokens_used": tokens_used,
        }

    except FileNotFoundError as e:
        log.warning(f"{log_identifier} File not found error: {e}")
        return {"status": "error", "message": str(e)}
    except ValueError as ve:
        log.error(f"{log_identifier} Value error: {ve}")
        return {"status": "error", "message": str(ve)}
    except httpx.HTTPStatusError as hse:
        log.error(
            f"{log_identifier} HTTP error calling audio API: {hse.response.status_code} - {hse.response.text}"
        )
        return {"status": "error", "message": f"API error: {hse.response.status_code}"}
    except httpx.RequestError as re:
        log.error(f"{log_identifier} Request error calling audio API: {re}")
        return {"status": "error", "message": f"Request error: {re}"}
    except json.JSONDecodeError as jde:
        log.error(f"{log_identifier} JSON decode error: {jde}")
        return {"status": "error", "message": "Invalid JSON response from API"}
    except Exception as e:
        log.exception(f"{log_identifier} Unexpected error in describe_audio: {e}")
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


async def edit_image_with_gemini(
    image_filename: str,
    edit_prompt: str,
    output_filename: Optional[str] = None,
    use_pro_model: bool = False,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Edits an existing image based on a text prompt using Google's Gemini image generation models.
    
    Two models are available (configured via tool_config):
    - Standard model: Default, optimized for speed, efficiency, and lower cost.
    - Pro model: Professional quality for complex tasks requiring advanced reasoning,
      high-fidelity text rendering, and up to 4K resolution. More expensive, so use only
      when truly necessary for infographics, charts, diagrams, technical illustrations,
      or tasks requiring precise text placement.

    Args:
        image_filename: The filename (and optional :version) of the input image artifact.
        edit_prompt: Text description of the desired edits to apply to the image.
        output_filename: Optional. The desired filename for the output edited image.
                        If not provided, a unique name like 'edited_image_<uuid>.jpg' will be used.
        use_pro_model: If True, uses the pro model for professional quality output with
                      advanced reasoning and high-fidelity text rendering. More expensive.
                      If False (default), uses the standard model which is faster and cheaper.
        tool_context: The context provided by the ADK framework.
        tool_config: Configuration dictionary containing gemini_api_key, model, and optionally pro_model.

    Returns:
        A dictionary containing:
        - "status": "success" or "error".
        - "message": A descriptive message about the outcome.
        - "output_filename": The name of the saved edited image artifact (if successful).
        - "output_version": The version of the saved edited image artifact (if successful).
        - "result_preview": A brief preview message (if successful).
        - "original_filename": The name of the input image artifact (if successful).
        - "original_version": The version of the input image artifact (if successful).
        - "model_used": The model that was used for the edit (if successful).
    """
    log_identifier = f"[ImageTools:edit_image_with_gemini:{image_filename}]"
    if not tool_context:
        log.error(f"{log_identifier} ToolContext is missing.")
        return {"status": "error", "message": "ToolContext is missing."}

    try:
        try:
            from google import genai
            from google.genai import types
            from PIL import Image as PILImage
            from io import BytesIO
        except ImportError as ie:
            log.error(f"{log_identifier} Required dependencies not available: {ie}")
            return {
                "status": "error",
                "message": f"Required dependencies not available: {ie}",
            }

        inv_context = tool_context._invocation_context
        if not inv_context:
            raise ValueError("InvocationContext is not available.")

        app_name = getattr(inv_context, "app_name", None)
        user_id = getattr(inv_context, "user_id", None)
        session_id = get_original_session_id(inv_context)
        artifact_service = getattr(inv_context, "artifact_service", None)

        if not all([app_name, user_id, session_id, artifact_service]):
            missing_parts = [
                part
                for part, val in [
                    ("app_name", app_name),
                    ("user_id", user_id),
                    ("session_id", session_id),
                    ("artifact_service", artifact_service),
                ]
                if not val
            ]
            raise ValueError(
                f"Missing required context parts: {', '.join(missing_parts)}"
            )

        log.info(
            f"{log_identifier} Processing image edit request for session {session_id}."
        )

        current_tool_config = tool_config if tool_config is not None else {}

        if not current_tool_config:
            log.warning(
                f"{log_identifier} Tool-specific configuration (tool_config) is empty."
            )

        gemini_api_key = current_tool_config.get("gemini_api_key")
        # Standard model - optimized for speed, efficiency, and lower cost
        default_model = current_tool_config.get(
            "model", "gemini-2.5-flash-image"
        )
        # Pro model - for professional asset production with advanced reasoning,
        # high-fidelity text rendering, and up to 4K resolution. More expensive.
        pro_model = current_tool_config.get(
            "pro_model", "gemini-3-pro-image-preview"
        )

        if not gemini_api_key:
            raise ValueError(
                "'gemini_api_key' configuration is missing in tool_config."
            )

        # Model selection is determined by the calling LLM via use_pro_model parameter
        model_name = pro_model if use_pro_model else default_model
        
        log.info(
            f"{log_identifier} Model selection: using {'pro' if use_pro_model else 'standard'} model "
            f"({model_name})"
        )

        parts = image_filename.rsplit(":", 1)
        filename_base_for_load = parts[0]
        version_str = parts[1] if len(parts) > 1 else None
        version_to_load = int(version_str) if version_str else None

        if not _is_supported_image_format(filename_base_for_load):
            raise ValueError(
                f"Unsupported image format. Supported formats: .png, .jpg, .jpeg, .webp, .gif"
            )

        if version_to_load is None:
            list_versions_method = getattr(artifact_service, "list_versions")
            if inspect.iscoroutinefunction(list_versions_method):
                versions = await list_versions_method(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename_base_for_load,
                )
            else:
                versions = await asyncio.to_thread(
                    list_versions_method,
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename_base_for_load,
                )
            if not versions:
                raise FileNotFoundError(
                    f"Image artifact '{filename_base_for_load}' not found."
                )
            version_to_load = max(versions)
            log.debug(
                f"{log_identifier} Using latest version for input: {version_to_load}"
            )

        load_artifact_method = getattr(artifact_service, "load_artifact")
        if inspect.iscoroutinefunction(load_artifact_method):
            image_artifact_part = await load_artifact_method(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename_base_for_load,
                version=version_to_load,
            )
        else:
            image_artifact_part = await asyncio.to_thread(
                load_artifact_method,
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename_base_for_load,
                version=version_to_load,
            )

        if not image_artifact_part or not image_artifact_part.inline_data:
            raise FileNotFoundError(
                f"Content for image artifact '{filename_base_for_load}' v{version_to_load} not found."
            )

        image_bytes = image_artifact_part.inline_data.data
        log.debug(f"{log_identifier} Loaded image artifact: {len(image_bytes)} bytes")

        try:
            from PIL import UnidentifiedImageError

            pil_image = PILImage.open(BytesIO(image_bytes))
            log.debug(
                f"{log_identifier} Converted to PIL Image: {pil_image.size}, mode: {pil_image.mode}"
            )
        except UnidentifiedImageError as e:
            log.error(f"{log_identifier} Unidentified image error: {e}")
            raise ValueError(f"Cannot identify image file: {e}")
        except IOError as e:
            log.error(f"{log_identifier} IO error: {e}")
            raise ValueError(f"Cannot identify image file: {e}")
        except Exception as e:
            raise ValueError(f"Failed to process image data: {e}")

        try:
            client = genai.Client(api_key=gemini_api_key)
            log.debug(f"{log_identifier} Initialized Gemini client")
        except Exception as e:
            raise ValueError(f"Failed to initialize Gemini client: {e}")

        text_input = (edit_prompt,)

        log.debug(
            f"{log_identifier} Calling Gemini API with edit prompt: '{edit_prompt[:100]}...'"
        )

        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=[text_input, pil_image],
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"]
                ),
            )
            log.debug(f"{log_identifier} Gemini API response received.")
        except Exception as e:
            raise ValueError(f"Gemini API call failed: {e}")

        edited_image_bytes = None
        response_text = None

        if not response.candidates or not response.candidates[0].content.parts:
            raise ValueError("Gemini API did not return valid content.")

        for part in response.candidates[0].content.parts:
            if part.text is not None:
                response_text = part.text
                log.debug(
                    f"{log_identifier} Received text response: {response_text[:100]}..."
                )
            elif part.inline_data is not None:
                edited_pil_image = PILImage.open(BytesIO(part.inline_data.data))
                output_buffer = BytesIO()
                if edited_pil_image.mode == "RGBA":
                    rgb_image = PILImage.new(
                        "RGB", edited_pil_image.size, (255, 255, 255)
                    )
                    rgb_image.paste(edited_pil_image, mask=edited_pil_image.split()[-1])
                    rgb_image.save(output_buffer, format="JPEG", quality=95)
                else:
                    edited_pil_image.save(output_buffer, format="JPEG", quality=95)
                edited_image_bytes = output_buffer.getvalue()
                log.debug(
                    f"{log_identifier} Processed edited image: {len(edited_image_bytes)} bytes"
                )

        if not edited_image_bytes:
            raise ValueError("No edited image data received from Gemini API.")

        final_output_filename = ""
        if output_filename:
            sane_filename = os.path.basename(output_filename)
            if not sane_filename.lower().endswith((".jpg", ".jpeg")):
                final_output_filename = f"{sane_filename}.jpg"
            else:
                final_output_filename = sane_filename
        else:
            base_name = os.path.splitext(filename_base_for_load)[0]
            final_output_filename = f"edited_{base_name}_{uuid.uuid4().hex[:8]}.jpg"

        log.debug(
            f"{log_identifier} Determined output filename: {final_output_filename}"
        )

        output_mime_type = "image/jpeg"
        current_timestamp_iso = datetime.now(timezone.utc).isoformat()

        metadata_dict = {
            "description": f"Image edited with prompt: {edit_prompt}",
            "original_image": filename_base_for_load,
            "original_version": version_to_load,
            "edit_prompt": edit_prompt,
            "editing_tool": "gemini",
            "editing_model": model_name,
            "request_timestamp": current_timestamp_iso,
            "original_requested_filename": (
                output_filename if output_filename else "N/A"
            ),
        }
        if response_text:
            metadata_dict["gemini_response_text"] = response_text

        log.info(
            f"{log_identifier} Saving edited image artifact '{final_output_filename}' with mime_type '{output_mime_type}'."
        )
        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=final_output_filename,
            content_bytes=edited_image_bytes,
            mime_type=output_mime_type,
            metadata_dict=metadata_dict,
            timestamp=datetime.now(timezone.utc),
            schema_max_keys=DEFAULT_SCHEMA_MAX_KEYS,
            tool_context=tool_context,
        )

        if save_result.get("status") == "error":
            raise IOError(
                f"Failed to save edited image artifact: {save_result.get('message', 'Unknown error')}"
            )

        log.info(
            f"{log_identifier} Edited image artifact '{final_output_filename}' v{save_result['data_version']} saved successfully."
        )

        return {
            "status": "success",
            "message": "Image edited and saved successfully.",
            "output_filename": final_output_filename,
            "output_version": save_result["data_version"],
            "result_preview": f"Edited image '{final_output_filename}' (v{save_result['data_version']}) created from '{filename_base_for_load}' with prompt: \"{edit_prompt[:50]}...\"",
            "original_filename": filename_base_for_load,
            "original_version": version_to_load,
            "model_used": model_name,
            "used_pro_model": use_pro_model,
        }

    except FileNotFoundError as e:
        log.warning(f"{log_identifier} File not found error: {e}")
        return {"status": "error", "message": str(e)}
    except ValueError as ve:
        log.error(f"{log_identifier} Value error: {ve}")
        return {"status": "error", "message": str(ve)}
    except IOError as ioe:
        log.error(f"{log_identifier} IO error: {ioe}")
        return {"status": "error", "message": str(ioe)}
    except Exception as e:
        log.exception(
            f"{log_identifier} Unexpected error in edit_image_with_gemini: {e}"
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


async def generate_image_with_gemini(
    image_description: str,
    output_filename: Optional[str] = None,
    use_pro_model: bool = False,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generates an image from a text description using Google's Gemini image generation models.
    
    Two models are available (configured via tool_config):
    - Standard model: Default, optimized for speed, efficiency, and lower cost.
    - Pro model: Professional quality for complex tasks requiring advanced reasoning,
      high-fidelity text rendering, and up to 4K resolution. More expensive, so use only
      when truly necessary for infographics, charts, diagrams, technical illustrations,
      or tasks requiring precise text placement.

    Args:
        image_description: The textual prompt to use for image generation.
        output_filename: Optional. The desired filename for the output image.
                        If not provided, a unique name like 'generated_image_<uuid>.png' will be used.
        use_pro_model: If True, uses the pro model for professional quality output with
                      advanced reasoning and high-fidelity text rendering. More expensive.
                      If False (default), uses the standard model which is faster and cheaper.
        tool_context: The context provided by the ADK framework.
        tool_config: Configuration dictionary containing gemini_api_key, model, and optionally pro_model.

    Returns:
        A dictionary containing:
        - "status": "success" or "error".
        - "message": A descriptive message about the outcome.
        - "output_filename": The name of the saved image artifact (if successful).
        - "output_version": The version of the saved image artifact (if successful).
        - "result_preview": A brief preview message (if successful).
        - "model_used": The model that was used for generation (if successful).
        - "used_pro_model": Whether the pro model was used (if successful).
    """
    log_identifier = f"[ImageTools:generate_image_with_gemini]"
    if not tool_context:
        log.error(f"{log_identifier} ToolContext is missing.")
        return {"status": "error", "message": "ToolContext is missing."}

    try:
        try:
            from google import genai
            from google.genai import types
            from PIL import Image as PILImage
            from io import BytesIO
        except ImportError as ie:
            log.error(f"{log_identifier} Required dependencies not available: {ie}")
            return {
                "status": "error",
                "message": f"Required dependencies not available: {ie}",
            }

        inv_context = tool_context._invocation_context
        if not inv_context:
            raise ValueError("InvocationContext is not available.")

        app_name = getattr(inv_context, "app_name", None)
        user_id = getattr(inv_context, "user_id", None)
        session_id = get_original_session_id(inv_context)
        artifact_service = getattr(inv_context, "artifact_service", None)

        if not all([app_name, user_id, session_id, artifact_service]):
            missing_parts = [
                part
                for part, val in [
                    ("app_name", app_name),
                    ("user_id", user_id),
                    ("session_id", session_id),
                    ("artifact_service", artifact_service),
                ]
                if not val
            ]
            raise ValueError(
                f"Missing required context parts: {', '.join(missing_parts)}"
            )

        log.info(
            f"{log_identifier} Processing image generation request for session {session_id}."
        )

        current_tool_config = tool_config if tool_config is not None else {}

        if not current_tool_config:
            log.warning(
                f"{log_identifier} Tool-specific configuration (tool_config) is empty."
            )

        gemini_api_key = current_tool_config.get("gemini_api_key")
        # Standard model - optimized for speed, efficiency, and lower cost
        default_model = current_tool_config.get(
            "model", "gemini-2.5-flash-image"
        )
        # Pro model - for professional asset production with advanced reasoning,
        # high-fidelity text rendering, and up to 4K resolution. More expensive.
        pro_model = current_tool_config.get(
            "pro_model", "gemini-3-pro-image-preview"
        )

        if not gemini_api_key:
            raise ValueError(
                "'gemini_api_key' configuration is missing in tool_config."
            )

        # Model selection is determined by the calling LLM via use_pro_model parameter
        model_name = pro_model if use_pro_model else default_model
        
        log.info(
            f"{log_identifier} Model selection: using {'pro' if use_pro_model else 'standard'} model "
            f"({model_name})"
        )

        try:
            client = genai.Client(api_key=gemini_api_key)
            log.debug(f"{log_identifier} Initialized Gemini client")
        except Exception as e:
            raise ValueError(f"Failed to initialize Gemini client: {e}")

        log.debug(
            f"{log_identifier} Calling Gemini API with prompt: '{image_description[:100]}...'"
        )

        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=[image_description],
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"]
                ),
            )
            log.debug(f"{log_identifier} Gemini API response received.")
        except Exception as e:
            raise ValueError(f"Gemini API call failed: {e}")

        generated_image_bytes = None
        response_text = None

        if not response.candidates or not response.candidates[0].content.parts:
            raise ValueError("Gemini API did not return valid content.")

        for part in response.candidates[0].content.parts:
            if part.text is not None:
                response_text = part.text
                log.debug(
                    f"{log_identifier} Received text response: {response_text[:100]}..."
                )
            elif part.inline_data is not None:
                generated_pil_image = PILImage.open(BytesIO(part.inline_data.data))
                output_buffer = BytesIO()
                # Save as PNG for generated images
                generated_pil_image.save(output_buffer, format="PNG")
                generated_image_bytes = output_buffer.getvalue()
                log.debug(
                    f"{log_identifier} Processed generated image: {len(generated_image_bytes)} bytes"
                )

        if not generated_image_bytes:
            raise ValueError("No image data received from Gemini API.")

        final_output_filename = ""
        if output_filename:
            sane_filename = os.path.basename(output_filename)
            if not sane_filename.lower().endswith(".png"):
                final_output_filename = f"{sane_filename}.png"
            else:
                final_output_filename = sane_filename
        else:
            final_output_filename = f"generated_image_{uuid.uuid4()}.png"

        log.debug(
            f"{log_identifier} Determined output filename: {final_output_filename}"
        )

        output_mime_type = "image/png"
        current_timestamp_iso = datetime.now(timezone.utc).isoformat()

        metadata_dict = {
            "description": f"Image generated from prompt: {image_description}",
            "source_prompt": image_description,
            "generation_tool": "gemini",
            "generation_model": model_name,
            "used_pro_model": use_pro_model,
            "request_timestamp": current_timestamp_iso,
            "original_requested_filename": (
                output_filename if output_filename else "N/A"
            ),
        }
        if response_text:
            metadata_dict["gemini_response_text"] = response_text

        log.info(
            f"{log_identifier} Saving generated image artifact '{final_output_filename}' with mime_type '{output_mime_type}'."
        )
        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=final_output_filename,
            content_bytes=generated_image_bytes,
            mime_type=output_mime_type,
            metadata_dict=metadata_dict,
            timestamp=datetime.now(timezone.utc),
            schema_max_keys=DEFAULT_SCHEMA_MAX_KEYS,
            tool_context=tool_context,
        )

        if save_result.get("status") == "error":
            raise IOError(
                f"Failed to save generated image artifact: {save_result.get('message', 'Unknown error')}"
            )

        log.info(
            f"{log_identifier} Generated image artifact '{final_output_filename}' v{save_result['data_version']} saved successfully."
        )

        return {
            "status": "success",
            "message": "Image generated and saved successfully.",
            "output_filename": final_output_filename,
            "output_version": save_result["data_version"],
            "result_preview": f"Image '{final_output_filename}' (v{save_result['data_version']}) created from prompt: \"{image_description[:50]}...\"",
            "model_used": model_name,
            "used_pro_model": use_pro_model,
        }

    except ValueError as ve:
        log.error(f"{log_identifier} Value error: {ve}")
        return {"status": "error", "message": str(ve)}
    except IOError as ioe:
        log.error(f"{log_identifier} IO error: {ioe}")
        return {"status": "error", "message": str(ioe)}
    except Exception as e:
        log.exception(
            f"{log_identifier} Unexpected error in generate_image_with_gemini: {e}"
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


create_image_from_description_tool_def = BuiltinTool(
    name="create_image_from_description",
    implementation=create_image_from_description,
    description="Generates an image based on a textual description using a configured image generation model (e.g., via LiteLLM) and saves it as a PNG artifact.",
    category="image",
    required_scopes=["tool:image:create"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "image_description": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The textual prompt to use for image generation.",
            ),
            "output_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional. The desired filename for the output PNG image.",
                nullable=True,
            ),
        },
        required=["image_description"],
    ),
    examples=[],
)

describe_image_tool_def = BuiltinTool(
    name="describe_image",
    implementation=describe_image,
    description="Describes an image using an OpenAI-compatible vision API.",
    category="image",
    required_scopes=["tool:image:describe"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "image_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The filename (and optional :version) of the input image artifact.",
            ),
            "prompt": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Custom prompt for image analysis.",
                nullable=True,
            ),
        },
        required=["image_filename"],
    ),
    examples=[],
)

describe_audio_tool_def = BuiltinTool(
    name="describe_audio",
    implementation=describe_audio,
    description="Describes an audio recording using a multimodal API.",
    category="image",
    required_scopes=["tool:audio:describe"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "audio_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The filename (and optional :version) of the input audio artifact.",
            ),
            "prompt": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Custom prompt for audio analysis.",
                nullable=True,
            ),
        },
        required=["audio_filename"],
    ),
    examples=[],
)

edit_image_with_gemini_tool_def = BuiltinTool(
    name="edit_image_with_gemini",
    implementation=edit_image_with_gemini,
    description=(
        "Edits an existing image based on a text prompt using Google's Gemini image generation models. "
        "Two models are available: a standard model (fast, efficient, and cheaper) and a pro model "
        "(professional quality but more expensive). Use the pro model only when truly necessary for "
        "complex tasks like infographics, charts, diagrams, or images requiring precise text placement."
    ),
    category="image",
    required_scopes=["tool:image:edit"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "image_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The filename (and optional :version) of the input image artifact.",
            ),
            "edit_prompt": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Text description of the desired edits to apply to the image.",
            ),
            "output_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional. The desired filename for the output edited image.",
                nullable=True,
            ),
            "use_pro_model": adk_types.Schema(
                type=adk_types.Type.BOOLEAN,
                description=(
                    "Set to true to use the pro model for professional quality output with advanced reasoning, "
                    "high-fidelity text rendering, and up to 4K resolution. The pro model is MORE EXPENSIVE, "
                    "so only use it when truly necessary for: infographics, charts, diagrams, technical "
                    "illustrations, or complex visual content requiring precise text placement. "
                    "Set to false (default) to use the standard model which is faster, efficient, and cheaper."
                ),
                nullable=True,
            ),
        },
        required=["image_filename", "edit_prompt"],
    ),
    examples=[],
)

generate_image_with_gemini_tool_def = BuiltinTool(
    name="generate_image_with_gemini",
    implementation=generate_image_with_gemini,
    description=(
        "Generates an image from a text description using Google's Gemini image generation models. "
        "Two models are available: a standard model (fast, efficient, and cheaper) and a pro model "
        "(professional quality but more expensive). Use the pro model only when truly necessary for "
        "complex tasks like infographics, charts, diagrams, or images requiring precise text placement."
    ),
    category="image",
    required_scopes=["tool:image:create"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "image_description": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The textual prompt to use for image generation.",
            ),
            "output_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional. The desired filename for the output PNG image.",
                nullable=True,
            ),
            "use_pro_model": adk_types.Schema(
                type=adk_types.Type.BOOLEAN,
                description=(
                    "Set to true to use the pro model for professional quality output with advanced reasoning, "
                    "high-fidelity text rendering, and up to 4K resolution. The pro model is MORE EXPENSIVE, "
                    "so only use it when truly necessary for: infographics, charts, diagrams, technical "
                    "illustrations, or complex visual content requiring precise text placement. "
                    "Set to false (default) to use the standard model which is faster, efficient, and cheaper."
                ),
                nullable=True,
            ),
        },
        required=["image_description"],
    ),
    examples=[],
)

tool_registry.register(create_image_from_description_tool_def)
tool_registry.register(describe_image_tool_def)
tool_registry.register(describe_audio_tool_def)
tool_registry.register(edit_image_with_gemini_tool_def)
tool_registry.register(generate_image_with_gemini_tool_def)
