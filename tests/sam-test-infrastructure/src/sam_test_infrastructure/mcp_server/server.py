"""
Test MCP Server for integration testing.
This server is built using fastmcp and is designed to be configured dynamically
at runtime by directives passed from the test case.
"""

import argparse
import base64
import json
import re
import threading
import logging
from typing import Any, Dict, List

from fastmcp import Context, FastMCP
from fastmcp.tools.tool import ToolResult
from fastmcp.utilities.types import Audio, Image
from mcp.types import (
    BlobResourceContents,
    EmbeddedResource,
    TextContent,
    TextResourceContents,
)
from pydantic import AnyUrl
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


def _to_camel_case(snake_str: str) -> str:
    """Converts a snake_case string to camelCase."""
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def _convert_keys_to_camel_case(data: Any) -> Any:
    """Recursively converts all dictionary keys in a structure to camelCase."""
    if isinstance(data, dict):
        return {
            _to_camel_case(k): _convert_keys_to_camel_case(v) for k, v in data.items()
        }
    if isinstance(data, list):
        return [_convert_keys_to_camel_case(i) for i in data]
    return data


class TestMCPServer:
    """
    A generic, configurable MCP server for integration testing.
    It is configured dynamically via directives in the tool's input.
    """

    def __init__(self):
        self.mcp = FastMCP(
            name="TestMCPServer",
            instructions="A mock server for testing MCP tool integrations.",
        )

        # Register the generic tool under two different names for stdio and http
        self.mcp.tool(self.get_data, name="get_data_stdio")
        self.mcp.tool(self.get_data, name="get_data_http")
        self.mcp.custom_route("/health", methods=["GET"])(self.health_check)

    async def health_check(self, request: Request) -> Response:
        """Simple health check endpoint for HTTP mode."""
        return JSONResponse({"status": "ok"})

    async def get_data(self, response_to_return: Dict[str, Any], ctx: Context):
        """
        A generic tool that constructs a list of typed Python objects based on
        the 'content' list provided in its arguments. This allows tests to
        leverage fastmcp's automatic type-to-ContentBlock conversion, giving
        full control over the mocked MCP response.
        """
        # Add diagnostic logging for multi-call debugging
        logging.info(
            f"MCP Server: get_data called with response_to_return: {response_to_return}"
        )
        logging.info(
            f"MCP Server: Context info - session_id: {getattr(ctx, 'session_id', 'N/A')}"
        )
        content_list = response_to_return.get("content", [])
        if not isinstance(content_list, list):
            return [f"Error: Expected 'content' to be a list, got {type(content_list)}"]

        # Special handling for resource links to bypass fastmcp's serialization
        if len(content_list) == 1 and content_list[0].get("type") == "resource":
            resource_data = content_list[0].get("resource", {})
            uri = resource_data.get("uri")
            if uri:
                text_content = resource_data.get("text")
                blob_content_b64 = resource_data.get("blob")

                if blob_content_b64:
                    resource_contents = BlobResourceContents(
                        uri=AnyUrl(uri),
                        blob=blob_content_b64,
                        mimeType=resource_data.get(
                            "mimeType", "application/octet-stream"
                        ),
                    )
                else:
                    # The agent expects a resource block with NO text/blob to create a placeholder.
                    # An empty text string should work, as `if content:` will be false.
                    resource_contents = TextResourceContents(
                        uri=AnyUrl(uri), text=text_content or ""
                    )

                embedded_resource = EmbeddedResource(
                    type="resource", resource=resource_contents
                )
                return ToolResult(content=[embedded_resource])

        result_objects = []
        for item in content_list:
            item_type = item.get("type")
            if item_type == "text":
                result_objects.append(
                    TextContent(type="text", text=item.get("text", ""))
                )
            elif item_type == "image":
                try:
                    image_bytes = base64.b64decode(item.get("data", ""))
                    # Extract format from mimeType (e.g., "image/png" -> "png")
                    mime_type = item.get("mimeType", "image/png")
                    format_type = (
                        mime_type.split("/")[-1] if "/" in mime_type else "png"
                    )
                    result_objects.append(Image(data=image_bytes, format=format_type))
                except (ValueError, TypeError) as e:
                    result_objects.append(f"Error decoding image data: {e}")
            elif item_type == "audio":
                try:
                    audio_bytes = base64.b64decode(item.get("data", ""))
                    # Extract format from mimeType (e.g., "audio/mp3" -> "mp3")
                    mime_type = item.get("mimeType", "audio/mp3")
                    format_type = (
                        mime_type.split("/")[-1] if "/" in mime_type else "mp3"
                    )
                    result_objects.append(Audio(data=audio_bytes, format=format_type))
                except (ValueError, TypeError) as e:
                    result_objects.append(f"Error decoding audio data: {e}")
            else:
                # For unknown types, return the raw dictionary as structured content
                result_objects.append(item)

        if len(result_objects) == 1:
            # If there's only one item, return it directly
            return result_objects[0]

        return result_objects


def main():
    """Main entry point to run the server from the command line."""
    parser = argparse.ArgumentParser(description="Run the Test MCP Server.")
    parser.add_argument(
        "--transport",
        type=str,
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="The transport protocol to use.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="The port to use for the http transport.",
    )
    args = parser.parse_args()

    server_instance = TestMCPServer()
    if args.transport == "stdio":
        server_instance.mcp.run(transport=args.transport)
    else:
        server_instance.mcp.run(transport=args.transport, port=args.port)


if __name__ == "__main__":
    main()
