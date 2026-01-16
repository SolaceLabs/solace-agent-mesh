"""
Resolves template blocks within artifact content.
"""

import logging
import re
from typing import Any

from .liquid_renderer import render_liquid_template

log = logging.getLogger(__name__)

# Regex to match template blocks: «««template: params\ncontent\n»»» or «««template_liquid: params\ncontent\n»»»
# Supports both 'template:' (legacy) and 'template_liquid:' (new)
TEMPLATE_BLOCK_REGEX = re.compile(
    r'«««template(?:_liquid)?:\s*([^\n]+)\n((?:(?!»»»).)*?)»»»',
    re.DOTALL
)

# Regex to parse parameters from template block header
TEMPLATE_PARAMS_REGEX = re.compile(r'(\w+)\s*=\s*"([^"]*)"')


async def resolve_template_blocks_in_string(
    text: str,
    artifact_service: Any,
    session_context: dict[str, str],
    log_identifier: str = "[TemplateResolver]",
) -> str:
    """
    Finds and resolves all template blocks in the given text.

    Template blocks have the format:
    «««template: data="filename.ext" jsonpath="$.path" limit="10"
    ...template content...
    »»»

    Args:
        text: The text containing potential template blocks
        artifact_service: Service to load data artifacts
        session_context: Dict with app_name, user_id, session_id
        log_identifier: Identifier for logging

    Returns:
        Text with all template blocks resolved to their rendered output
    """
    # Import here to avoid circular dependency
    from ....agent.utils.artifact_helpers import load_artifact_content_or_metadata

    # Find all template blocks
    matches = list(TEMPLATE_BLOCK_REGEX.finditer(text))

    if not matches:
        return text

    log.info(
        "%s Found %d template block(s) to resolve",
        log_identifier,
        len(matches),
    )

    # Process each match and collect replacements
    replacements = []
    for match in matches:
        params_str = match.group(1)
        template_content = match.group(2)

        # Parse parameters
        params = dict(TEMPLATE_PARAMS_REGEX.findall(params_str))

        log.info(
            "%s Resolving template block with params: %s",
            log_identifier,
            params,
        )

        data_artifact_spec = params.get("data")
        if not data_artifact_spec:
            error_msg = "[Template Error: Missing 'data' parameter]"
            log.error("%s %s", log_identifier, error_msg)
            replacements.append((match.start(), match.end(), error_msg))
            continue

        # Parse data artifact spec (filename or filename:version)
        artifact_parts = data_artifact_spec.split(":", 1)
        filename = artifact_parts[0]
        version = int(artifact_parts[1]) if len(artifact_parts) > 1 else "latest"

        try:
            # Load the data artifact with a large max_content_length (2MB)
            # to ensure full JSON/YAML content is loaded for template rendering
            artifact_data = await load_artifact_content_or_metadata(
                artifact_service,
                **session_context,
                filename=filename,
                version=version,
                load_metadata_only=False,
                max_content_length=2_000_000,  # 2MB limit for template data
            )

            if artifact_data.get("status") != "success":
                error_msg = f"[Template Error: Failed to load data artifact '{filename}']"
                log.error("%s %s", log_identifier, error_msg)
                replacements.append((match.start(), match.end(), error_msg))
                continue

            # Get artifact content and MIME type
            artifact_content = artifact_data.get("content")
            artifact_mime = artifact_data.get("mime_type", "text/plain")

            # Parse optional parameters
            jsonpath = params.get("jsonpath")
            limit_str = params.get("limit")
            limit = int(limit_str) if limit_str else None

            # Render the template
            rendered_output, render_error = render_liquid_template(
                template_content=template_content,
                data_artifact_content=artifact_content,
                data_mime_type=artifact_mime,
                jsonpath=jsonpath,
                limit=limit,
                log_identifier=log_identifier,
            )

            if render_error:
                log.error(
                    "%s Template rendering failed: %s",
                    log_identifier,
                    render_error,
                )
                replacements.append((match.start(), match.end(), rendered_output))
            else:
                log.info(
                    "%s Template rendered successfully. Output length: %d",
                    log_identifier,
                    len(rendered_output),
                )
                replacements.append((match.start(), match.end(), rendered_output))

        except Exception as e:
            error_msg = f"[Template Error: {str(e)}]"
            log.exception(
                "%s Exception during template resolution: %s",
                log_identifier,
                e,
            )
            replacements.append((match.start(), match.end(), error_msg))

    # Apply all replacements from end to start to maintain positions
    result = text
    for start, end, replacement in reversed(replacements):
        result = result[:start] + replacement + result[end:]

    log.info(
        "%s Resolved %d template block(s)",
        log_identifier,
        len(replacements),
    )

    return result
