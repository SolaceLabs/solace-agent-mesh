from google.adk.tools import ToolContext
from google.genai import types as adk_types
import base64
import binascii


def calculate_square(number: float) -> float:
    """Calculates the square of the input number."""
    return number * number


def add_two_numbers(
    number1: float,
    number2: float,
) -> dict:
    """
    Calculator tool that adds two numbers together.
    
    This tool performs basic addition of two numbers and returns the result.
    Supports integers and floating-point numbers, including negative values.
    
    Args:
        number1: The first number to add.
        number2: The second number to add.
        
    Returns:
        A dictionary containing the calculation result and metadata.
    """
    try:
        # Validate inputs
        if not isinstance(number1, (int, float)) or not isinstance(number2, (int, float)):
            return {
                "status": "error",
                "message": f"Invalid input types. Expected numbers, got {type(number1).__name__} and {type(number2).__name__}.",
                "result": None
            }
        
        # Handle potential overflow or very large numbers
        if abs(number1) > 1e308 or abs(number2) > 1e308:
            return {
                "status": "error", 
                "message": "Input numbers are too large to process safely.",
                "result": None
            }
        
        # Perform the addition
        result = number1 + number2
        
        # Check for overflow in result
        if abs(result) > 1e308:
            return {
                "status": "error",
                "message": "Result is too large to represent.",
                "result": None
            }
        
        return {
            "status": "success",
            "message": f"Successfully added {number1} + {number2}",
            "result": result,
            "operation": "addition",
            "operands": [number1, number2]
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Calculation failed: {str(e)}",
            "result": None
        }


def create_file(
    filename: str,
    mimeType: str,
    content: str,
    return_immediately: bool,
    tool_context: ToolContext = None,
) -> dict:
    """
    EXAMPLE TOOL: Creates a file using the artifact service.

    This is an *example* tool. The actual built-in tool used by the host
    has similar functionality but also handles signaling for immediate return.
    This example tool does NOT perform signaling.

    Args:
        filename: The name of the file to create.
        mimeType: The MIME type of the file content (e.g., 'text/plain', 'image/png', 'application/json').
        content: The content of the file, potentially base64 encoded if binary.
        return_immediately: If True, indicates the caller *wants* this artifact
                            returned immediately (but this example tool doesn't act on it).
                            Must be explicitly provided.
        tool_context: The context provided by the ADK framework.

    Returns:
        A dictionary confirming the file creation and its version or an error.
        Includes filename and version as required.
    """
    if not tool_context:
        print("Error: ToolContext is missing in create_file example tool.")
        return {
            "status": "error",
            "filename": filename,
            "message": "ToolContext is missing.",
        }

    try:
        file_bytes: bytes
        final_mime_type = mimeType
        is_likely_binary = (
            mimeType
            and not mimeType.startswith("text/")
            and mimeType != "application/json"
            and mimeType != "application/yaml"
            and mimeType != "application/xml"
        )

        if is_likely_binary:
            try:
                file_bytes = base64.b64decode(content, validate=True)
                final_mime_type = mimeType
            except (binascii.Error, ValueError) as decode_error:
                print(
                    f"Warning: Failed to base64 decode content for mimeType '{mimeType}'. Treating as text/plain. Error: {decode_error}"
                )
                file_bytes = content.encode("utf-8")
                final_mime_type = "text/plain"
        else:
            file_bytes = content.encode("utf-8")
            if not mimeType or not (
                mimeType.startswith("text/")
                or mimeType
                in [
                    "application/json",
                    "application/yaml",
                    "application/xml",
                    "application/csv",
                ]
            ):
                print(
                    f"Warning: Provided mimeType '{mimeType}' doesn't look like text. Using 'text/plain'."
                )
                final_mime_type = "text/plain"
            else:
                final_mime_type = mimeType

        artifact_part = adk_types.Part.from_bytes(
            data=file_bytes, mime_type=final_mime_type
        )
        version = tool_context.save_artifact(filename=filename, artifact=artifact_part)

        if return_immediately:
            print(
                f"Info: Example create_file called with return_immediately=True for '{filename}', but this example tool does not signal."
            )

        return {
            "status": "success",
            "filename": filename,
            "version": version,
            "mimeType": final_mime_type,
            "message": f"File '{filename}' (version {version}, type {final_mime_type}) saved successfully by example tool.",
        }
    except Exception as e:
        print(f"Error creating file '{filename}' in example tool: {e}")
        return {
            "status": "error",
            "filename": filename,
            "message": f"Failed to create file in example tool: {e}",
        }
