import re
import json
import base64
import zipfile
import gzip
import io

from solace_ai_connector.common.log import log
from .transformers import TRANSFORMERS

QUERY_OPTIONS = {
    "encoding": ["zip", "gzip", "base64", "datauri"],
}

for tr in TRANSFORMERS:
    for key, value in tr.queries.items():
        QUERY_OPTIONS[key] = value.get("type")

LLM_QUERY_OPTIONS = {
    **QUERY_OPTIONS,
    "resolve": "bool",
}


def encode_file(file: bytes, encoding: str, mime_type: str, file_name=str) -> bytes:
    """
    Encode a file using the specified encoding.

    Parameters:
    - file (bytes): The file content as bytes.
    - encoding (str): The encoding to use ('zip', 'gzip', 'base64', 'datauri').

    Returns:
    - bytes: The encoded file content.
    """
    try:
        if encoding == "zip":
            # Create a BytesIO buffer to hold the zip file
            zip_buffer = io.BytesIO()
            # Create a zip file in the buffer
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                # Add the file to the ZIP archive
                zip_file.writestr(file_name, file)
            # Get the byte buffer of the zip file
            zip_buffer.seek(0)  # Move to the beginning of the buffer
            return zip_buffer.read()

        elif encoding == "gzip":
            # Create a BytesIO buffer to hold the gzip file
            gzip_buffer = io.BytesIO()
            # Create a gzip file in the buffer
            with gzip.GzipFile(fileobj=gzip_buffer, mode="wb") as gzip_file:
                # Write the file content to the gzip archive
                gzip_file.write(file)
            return gzip_buffer.getvalue()

        elif encoding == "base64":
            return base64.b64encode(file).decode("utf-8")

        elif encoding == "datauri":
            return f"data:{mime_type};base64,{base64.b64encode(file).decode('utf-8')}"

    except Exception as e:
        log.error("Failed to encode file: %s", e)
        return file

    return file


def apply_file_transformations(
    file: bytes, metadata: dict, transformations: dict = {}
) -> bytes | str:
    """
    Apply transformations to a file.

    Parameters:
    - file (bytes): The file content as bytes.
    - metadata (dict): The file metadata.
    - transformations (dict): The transformations to apply.
    """
    if not transformations:
        return file
    text_mime_type_regex = r"text/.*|.*csv|.*json|.*xml|.*yaml|.*x-yaml|.*txt"
    mime_type = metadata.get("mime_type", "")
    if mime_type is None:
        mime_type = ""
    name = metadata.get("name", "unknown")
    other = {
        "mime_type": mime_type,
        "name": name,
    }
    data = file
    if not re.match(text_mime_type_regex, mime_type):
        for transformer in TRANSFORMERS:
            if transformer.is_binary_transformer:
                data = transformer.transform(file, data, transformations, other)                     

        # Should be last transformation
        if transformations.get("encoding"):
            try:
                byte_data = data if isinstance(data, bytes) else data.encode("utf-8")
                return encode_file(
                    byte_data, transformations.get("encoding"), mime_type, name
                )
            except Exception as e:
                log.error("Failed to encode to base64: %s", e)
                return file
        return data
    else:
        # File is text-based
        # Convert bytes to string if of type bytes
        decoded_data = file.decode("utf-8") if isinstance(file, bytes) else file
        data = decoded_data

        for transformer in TRANSFORMERS:
            if transformer.is_text_transformer:
                data = transformer.transform(file, data, transformations, other)

        # Should be last transformation
        if transformations.get("encoding"):
            try:
                byte_data = data if isinstance(data, bytes) else data.encode("utf-8")
                return encode_file(
                    byte_data, transformations["encoding"], mime_type, name
                )
            except Exception as e:
                log.error("Failed to encode to base64: %s", e)
                return file

        if not isinstance(data, str):
            # Convert bytes to string
            if isinstance(data, bytes):
                try:
                    data = data.decode("utf-8")
                except UnicodeDecodeError:
                    data = base64.b64encode(data).decode("utf-8")
                    data = f"data:{mime_type};base64,{data}"
            else:
                data = json.dumps(data)

        return data
