"""
Collection of Python tools for web-related tasks, such as making HTTP requests.
"""

import asyncio
import logging
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import ipaddress
from urllib.parse import urlparse
import socket

import httpx
from markdownify import markdownify as md
from bs4 import BeautifulSoup

from google.adk.tools import ToolContext

from ...agent.utils.artifact_helpers import (
    save_artifact_with_metadata,
    DEFAULT_SCHEMA_MAX_KEYS,
)
from ...agent.utils.context_helpers import get_original_session_id

from google.genai import types as adk_types
from .tool_definition import BuiltinTool
from .registry import tool_registry

log = logging.getLogger(__name__)

CATEGORY_NAME = "Web Access"
CATEGORY_DESCRIPTION = "Access the web to find information to complete user requests."

# Response size limits (in bytes)
DEFAULT_MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # 10 MB default
ABSOLUTE_MAX_RESPONSE_SIZE = 50 * 1024 * 1024  # 50 MB hard cap (cannot be exceeded even via config)

def _is_safe_url(url: str) -> bool:
    """
    Checks if a URL is safe to request by resolving its hostname and checking
    if the IP address is in a private, reserved, or loopback range.
    """
    try:
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        if not hostname:
            log.warning(f"URL has no hostname: {url}")
            return False

        try:
            ip_str = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(ip_str)
        except socket.gaierror:
            log.warning(f"Could not resolve hostname: {hostname}")
            return False

        if ip.is_private or ip.is_reserved or ip.is_loopback:
            log.warning(f"URL {url} resolved to a blocked IP: {ip}")
            return False

        return True

    except Exception as e:
        log.error(f"Error during URL safety check for {url}: {e}", exc_info=True)
        return False


async def web_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[str] = None,
    output_artifact_filename: Optional[str] = None,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
    max_retries: int = 2,
) -> Dict[str, Any]:
    """
    Makes an HTTP request to the specified URL with retry logic, processes the content (e.g., HTML to Markdown),
    and saves the result as an artifact.

    Args:
        url: The URL to fetch.
        method: HTTP method (e.g., "GET", "POST"). Defaults to "GET".
        headers: Optional dictionary of request headers.
        body: Optional request body string for methods like POST/PUT. If sending JSON, this should be a valid JSON string.
        output_artifact_filename: Optional. Desired filename for the output artifact.
        tool_context: The context provided by the ADK framework.
        tool_config: Optional. Configuration passed by the ADK. Supports:
            - allow_loopback: bool - Allow requests to loopback addresses (for testing)
            - max_response_size_bytes: int - Maximum response size in bytes (default: 10MB, max: 50MB)
        max_retries: Maximum number of retry attempts for failed requests. Defaults to 2.

    Returns:
        A dictionary with status, message, and artifact details if successful.
    """
    log_identifier = f"[WebTools:web_request:{method}:{url}]"
    if not tool_context:
        log.error(f"{log_identifier} ToolContext is missing.")
        return {"status": "error", "message": "ToolContext is missing."}

    # Check if loopback URLs are allowed (for testing)
    allow_loopback = False
    max_response_size = DEFAULT_MAX_RESPONSE_SIZE
    
    if tool_config:
        allow_loopback = tool_config.get("allow_loopback", False)
        # Get max response size from config, but enforce hard cap
        configured_size = tool_config.get("max_response_size_bytes")
        if configured_size is not None:
            max_response_size = min(int(configured_size), ABSOLUTE_MAX_RESPONSE_SIZE)
            log.debug(f"{log_identifier} Using configured max_response_size: {max_response_size} bytes")
    
    if not allow_loopback and not _is_safe_url(url):
        log.error(f"{log_identifier} URL is not safe to request: {url}")
        return {"status": "error", "message": "URL is not safe to request."}

    if headers is None:
        headers = {}

    if not any(h.lower() == "user-agent" for h in headers):
        headers["User-Agent"] = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
        )

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

        request_body_bytes = None
        if body:
            request_body_bytes = body.encode("utf-8")

        # Retry logic with exponential backoff
        last_error = None
        response = None
        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    log.info(
                        f"{log_identifier} Attempt {attempt}/{max_retries}: Making {method} request to {url}"
                    )
                    
                    # Use streaming to check Content-Length and limit response size
                    async with client.stream(
                        method=method.upper(),
                        url=url,
                        headers=headers,
                        content=request_body_bytes,
                    ) as stream_response:
                        # Check Content-Length header if available
                        content_length = stream_response.headers.get("content-length")
                        if content_length:
                            content_length_int = int(content_length)
                            if content_length_int > max_response_size:
                                log.warning(
                                    f"{log_identifier} Response Content-Length ({content_length_int} bytes) exceeds "
                                    f"max_response_size ({max_response_size} bytes). Rejecting request."
                                )
                                return {
                                    "status": "error",
                                    "message": f"Response too large: {content_length_int} bytes exceeds limit of {max_response_size} bytes ({max_response_size // (1024*1024)} MB). "
                                               f"Consider using a more specific URL or a different approach."
                                }
                        
                        # Read response with size limit using streaming
                        chunks = []
                        total_size = 0
                        async for chunk in stream_response.aiter_bytes():
                            total_size += len(chunk)
                            if total_size > max_response_size:
                                log.warning(
                                    f"{log_identifier} Response size ({total_size} bytes) exceeded "
                                    f"max_response_size ({max_response_size} bytes) during streaming. Truncating."
                                )
                                # Keep what we have so far but stop reading
                                break
                            chunks.append(chunk)
                        
                        # Create a response-like object with the data we need
                        class StreamedResponse:
                            def __init__(self, stream_resp, content_bytes):
                                self.status_code = stream_resp.status_code
                                self.headers = stream_resp.headers
                                self.content = content_bytes
                        
                        response = StreamedResponse(stream_response, b"".join(chunks))
                        
                        log.info(
                            f"{log_identifier} Received response with status code: {response.status_code}, "
                            f"size: {len(response.content)} bytes"
                        )
                    
                    # Success - break out of retry loop
                    break
                    
            except (httpx.ReadTimeout, httpx.ConnectTimeout) as timeout_error:
                last_error = timeout_error
                log.warning(
                    f"{log_identifier} Attempt {attempt}/{max_retries} timed out: {timeout_error}"
                )
                
                if attempt < max_retries:
                    # Exponential backoff with jitter
                    import random
                    base_delay = 3.0 * (2 ** (attempt - 1))  # 3s, 6s, 12s...
                    jitter = random.uniform(0, 1.0)
                    delay = base_delay + jitter
                    log.info(f"{log_identifier} Waiting {delay:.1f}s before retry {attempt + 1}/{max_retries}")
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    error_message = f"Request timed out after {max_retries} attempts (30s timeout per attempt)"
                    log.error(f"{log_identifier} {error_message}")
                    return {
                        "status": "error",
                        "message": f"{error_message}. The website may be slow or blocking automated requests."
                    }
                    
            except httpx.RequestError as req_error:
                last_error = req_error
                log.warning(
                    f"{log_identifier} Attempt {attempt}/{max_retries} failed with request error: {req_error}"
                )
                
                if attempt < max_retries:
                    import random
                    base_delay = 3.0 * (2 ** (attempt - 1))
                    jitter = random.uniform(0, 1.0)
                    delay = base_delay + jitter
                    log.info(f"{log_identifier} Waiting {delay:.1f}s before retry {attempt + 1}/{max_retries}")
                    await asyncio.sleep(delay)
                else:
                    # Will be handled by the outer exception handler
                    raise

        response_content_bytes = response.content
        response_status_code = response.status_code
        original_content_type = (
            response.headers.get("content-type", "application/octet-stream")
            .split(";")[0]
            .strip()
        )

        final_content_to_save_str = ""
        final_content_to_save_bytes = response_content_bytes
        processed_content_type = original_content_type

        if response_status_code < 400:
            if original_content_type.startswith("text/html"):
                soup = BeautifulSoup(response_content_bytes, "html.parser")

                # Remove images before conversion
                for img in soup.find_all('img'):
                    img.decompose()

                final_content_to_save_str = md(str(soup), heading_style="ATX")
                final_content_to_save_bytes = final_content_to_save_str.encode("utf-8")
                processed_content_type = "text/markdown"
                log.debug(f"{log_identifier} Converted HTML to Markdown.")
            elif original_content_type.startswith("text/") or original_content_type in [
                "application/json",
                "application/xml",
                "application/javascript",
            ]:
                try:
                    final_content_to_save_str = response_content_bytes.decode("utf-8")
                    log.debug(
                        f"{log_identifier} Decoded text-based content: {original_content_type}"
                    )
                except UnicodeDecodeError:
                    log.warning(
                        f"{log_identifier} Could not decode content as UTF-8. Original type: {original_content_type}. Saving raw bytes."
                    )

        else:
            log.warning(
                f"{log_identifier} HTTP request returned status {response_status_code}. Saving raw response content."
            )
            if original_content_type.startswith("text/") or original_content_type in [
                "application/json",
                "application/xml",
                "application/javascript",
            ]:
                try:
                    final_content_to_save_str = response_content_bytes.decode(
                        "utf-8", errors="replace"
                    )
                except Exception:
                    final_content_to_save_str = "[Binary or undecodable content]"

        file_extension = ".bin"
        if processed_content_type == "text/markdown":
            file_extension = ".md"
        elif processed_content_type == "application/json":
            file_extension = ".json"
        elif processed_content_type == "application/xml":
            file_extension = ".xml"
        elif processed_content_type.startswith("text/"):
            file_extension = ".txt"
        elif processed_content_type == "image/jpeg":
            file_extension = ".jpg"
        elif processed_content_type == "image/png":
            file_extension = ".png"
        elif processed_content_type == "image/gif":
            file_extension = ".gif"
        elif processed_content_type == "application/pdf":
            file_extension = ".pdf"

        if output_artifact_filename:
            if "." not in output_artifact_filename.split("/")[-1]:
                final_artifact_filename = f"{output_artifact_filename}{file_extension}"
            else:
                final_artifact_filename = output_artifact_filename
        else:
            final_artifact_filename = f"web_content_{uuid.uuid4()}{file_extension}"

        metadata_dict = {
            "url": url,
            "method": method.upper(),
            "request_headers": json.dumps(
                {k: v for k, v in headers.items() if k.lower() != "authorization"}
            ),
            "response_status_code": response_status_code,
            "response_headers": json.dumps(dict(response.headers)),
            "original_content_type": original_content_type,
            "processed_content_type": processed_content_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        log.info(
            f"{log_identifier} Saving artifact '{final_artifact_filename}' with mime_type '{processed_content_type}'."
        )
        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=final_artifact_filename,
            content_bytes=final_content_to_save_bytes,
            mime_type=processed_content_type,
            metadata_dict=metadata_dict,
            timestamp=datetime.now(timezone.utc),
            schema_max_keys=DEFAULT_SCHEMA_MAX_KEYS,
            tool_context=tool_context,
        )

        if save_result.get("status") == "error":
            raise IOError(
                f"Failed to save web content artifact: {save_result.get('message', 'Unknown error')}"
            )

        log.info(
            f"{log_identifier} Artifact '{final_artifact_filename}' v{save_result['data_version']} saved successfully."
        )

        preview_text = f"Content from {url} (status: {response_status_code}) saved as '{final_artifact_filename}' v{save_result['data_version']}."
        if final_content_to_save_str:
            preview_text += (
                f"\nPreview (first 200 chars): {final_content_to_save_str[:200]}"
            )
            if len(final_content_to_save_str) > 200:
                preview_text += "..."
        elif response_status_code >= 400:
            preview_text += f"\nError response content (first 200 chars): {response_content_bytes[:200].decode('utf-8', errors='replace')}"
            if len(response_content_bytes) > 200:
                preview_text += "..."

        return {
            "status": "success",
            "message": f"Successfully fetched content from {url} (status: {response_status_code}). "
            f"Saved as artifact '{final_artifact_filename}' v{save_result['data_version']}. "
            f"Analyze the content of '{final_artifact_filename}' before providing a final answer to the user.",
            "output_filename": final_artifact_filename,
            "output_version": save_result["data_version"],
            "response_status_code": response_status_code,
            "original_content_type": original_content_type,
            "processed_content_type": processed_content_type,
            "result_preview": preview_text,
        }

    except httpx.HTTPStatusError as hse:
        error_message = f"HTTP error {hse.response.status_code} while fetching {url}: {hse.response.text[:500]}"
        log.error(f"{log_identifier} {error_message}", exc_info=True)
        try:
            error_filename = f"error_response_{uuid.uuid4()}.txt"
            error_metadata = {
                "url": url,
                "method": method.upper(),
                "error_type": "HTTPStatusError",
                "status_code": hse.response.status_code,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await save_artifact_with_metadata(
                artifact_service,
                app_name,
                user_id,
                session_id,
                error_filename,
                hse.response.text.encode("utf-8", errors="replace"),
                "text/plain",
                error_metadata,
                datetime.now(timezone.utc),
                tool_context=tool_context,
            )
            return {
                "status": "error",
                "message": error_message,
                "error_artifact": error_filename,
            }
        except Exception as e_save:
            log.error(
                f"{log_identifier} Could not save HTTPStatusError response: {e_save}"
            )
            return {"status": "error", "message": error_message}

    except httpx.RequestError as re:
        error_message = f"Request error while fetching {url} after {max_retries} attempts: {re}"
        log.error(f"{log_identifier} {error_message}", exc_info=True)
        return {
            "status": "error",
            "message": f"{error_message}. The website may be unreachable or blocking requests."
        }
    except ValueError as ve:
        log.error(f"{log_identifier} Value error: {ve}", exc_info=True)
        return {"status": "error", "message": str(ve)}
    except IOError as ioe:
        log.error(f"{log_identifier} IO error: {ioe}", exc_info=True)
        return {"status": "error", "message": str(ioe)}
    except Exception as e:
        log.exception(f"{log_identifier} Unexpected error in web_request: {e}")
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


web_request_tool_def = BuiltinTool(
    name="web_request",
    implementation=web_request,
    description="Makes an HTTP request to a URL, processes content (e.g., HTML to Markdown), and saves the result as an artifact.",
    category="web",
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["tool:web:request"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "url": adk_types.Schema(
                type=adk_types.Type.STRING, description="The URL to fetch."
            ),
            "method": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="HTTP method (e.g., 'GET', 'POST'). Defaults to 'GET'.",
                nullable=True,
            ),
            "headers": adk_types.Schema(
                type=adk_types.Type.OBJECT,
                description="Optional dictionary of request headers.",
                nullable=True,
            ),
            "body": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional request body string for methods like POST/PUT.",
                nullable=True,
            ),
            "output_artifact_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional. Desired filename for the output artifact.",
                nullable=True,
            ),
        },
        required=["url"],
    ),
    examples=[],
)

tool_registry.register(web_request_tool_def)
