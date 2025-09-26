"""
Built-in ADK Tools for Data Analysis (SQL, JQ, Plotly).
"""

import logging
import json
from typing import Any, Dict, Tuple, Optional, Literal
from datetime import datetime, timezone

try:
    import yaml

    PYYAML_AVAILABLE = True
except ImportError:
    PYYAML_AVAILABLE = False

try:
    import plotly.io as pio
    import plotly.graph_objects as go

    PLOTLY_AVAILABLE = True
    try:
        import kaleido

        KALEIDO_AVAILABLE = True
    except ImportError:
        KALEIDO_AVAILABLE = False
except ImportError:
    PLOTLY_AVAILABLE = False
    KALEIDO_AVAILABLE = False


from google.adk.tools import ToolContext
from google.genai import types as adk_types

from ...agent.utils.artifact_helpers import (
    ensure_correct_extension,
    save_artifact_with_metadata,
    DEFAULT_SCHEMA_MAX_KEYS,
)

from ...agent.utils.context_helpers import get_original_session_id

from .tool_definition import BuiltinTool
from .registry import tool_registry

log = logging.getLogger(__name__)

CATEGORY_NAME = "Data Analysis"
CATEGORY_DESCRIPTION = "Create static chart images from data in JSON or YAML format."

async def create_chart_from_plotly_config(
    config_content: str,
    config_format: Literal["json", "yaml"],
    output_filename: str,
    output_format: Optional[str] = "png",
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    Generates a static chart image from a Plotly configuration provided as a string.

    Args:
        config_content: The Plotly configuration (JSON or YAML) as a string.
        config_format: The format of the config_content ('json' or 'yaml').
        output_filename: The desired filename for the output image artifact.
        output_format: The desired image format ('png', 'jpg', 'svg', 'pdf', etc.). Default 'png'.
        tool_context: The context provided by the ADK framework.

    Returns:
        A dictionary with status and output artifact details.
    """
    if not tool_context:
        return {"status": "error", "message": "ToolContext is missing."}
    if not PLOTLY_AVAILABLE:
        return {
            "status": "error",
            "message": "The plotly library is required for chart generation but it is not installed.",
        }
    if not KALEIDO_AVAILABLE:
        return {
            "status": "error",
            "message": "The kaleido library is required for chart generation but it is not installed.",
        }

    log_identifier = f"[DataTool:create_chart:{output_filename}]"
    log.info(
        "%s Processing request to create chart '%s' from %s config.",
        log_identifier,
        output_filename,
        config_format,
    )

    try:
        plotly_config_dict: Dict
        if config_format == "json":
            try:
                plotly_config_dict = json.loads(config_content)
            except json.JSONDecodeError as parse_err:
                raise ValueError(
                    f"Failed to parse Plotly config as JSON: {parse_err}"
                ) from parse_err
        elif config_format == "yaml":
            try:
                plotly_config_dict = yaml.safe_load(config_content)
                if not isinstance(plotly_config_dict, dict):
                    raise ValueError("YAML content did not parse into a dictionary.")
            except yaml.YAMLError as parse_err:
                raise ValueError(
                    f"Failed to parse Plotly config as YAML: {parse_err}"
                ) from parse_err
        else:
            raise ValueError(
                f"Invalid config_format: {config_format}. Expected 'json' or 'yaml'."
            )

        try:
            fig = go.Figure(plotly_config_dict)
        except Exception as fig_err:
            raise ValueError(
                f"Failed to create Plotly figure from config: {fig_err}"
            ) from fig_err

        try:
            image_bytes = pio.to_image(fig, format=output_format, engine="kaleido")
            log.info(
                "%s Successfully generated %s image bytes using Kaleido.",
                log_identifier,
                output_format,
            )
        except Exception as img_err:
            raise ValueError(
                f"Failed to generate {output_format} image using Plotly/Kaleido: {img_err}. Ensure 'kaleido' package is installed and functional."
            ) from img_err

        mime_map = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
            "svg": "image/svg+xml",
            "pdf": "application/pdf",
            "eps": "application/postscript",
        }
        output_mime_type = mime_map.get(output_format.lower(), f"image/{output_format}")

        inv_context = tool_context._invocation_context
        artifact_service = inv_context.artifact_service
        if not artifact_service:
            raise ValueError("ArtifactService is not available in the context.")
        host_component = getattr(inv_context.agent, "host_component", None)
        schema_max_keys = (
            host_component.get_config("schema_max_keys", DEFAULT_SCHEMA_MAX_KEYS)
            if host_component
            else DEFAULT_SCHEMA_MAX_KEYS
        )

        final_output_filename = ensure_correct_extension(output_filename, output_format)

        save_metadata_dict = {
            "description": f"Chart generated from Plotly config ({config_format})",
            "source_format": config_format,
        }
        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=inv_context.app_name,
            user_id=inv_context.user_id,
            session_id=get_original_session_id(inv_context),
            filename=final_output_filename,
            content_bytes=image_bytes,
            mime_type=output_mime_type,
            metadata_dict=save_metadata_dict,
            timestamp=datetime.now(timezone.utc),
            schema_max_keys=schema_max_keys,
            tool_context=tool_context,
        )

        if save_result["status"] == "error":
            raise IOError(
                f"Failed to save chart image artifact: {save_result.get('message', 'Unknown error')}"
            )
        log.info(
            "%s Successfully created chart artifact '%s' v%d.",
            log_identifier,
            final_output_filename,
            save_result["data_version"],
        )
        return {
            "status": "success",
            "message": f"Chart image '{final_output_filename}' v{save_result['data_version']} created successfully.",
            "output_filename": final_output_filename,
            "output_version": save_result["data_version"],
        }

    except ValueError as e:
        log.warning("%s Value error: %s", log_identifier, e)
        return {"status": "error", "message": str(e)}
    except ImportError as e:
        log.warning("%s Missing library error: %s", log_identifier, e)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        log.exception(
            "%s Unexpected error in create_chart_from_plotly_config: %s",
            log_identifier,
            e,
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


create_chart_from_plotly_config_tool_def = BuiltinTool(
    name="create_chart_from_plotly_config",
    implementation=create_chart_from_plotly_config,
    description="Generates a static chart image (PNG, JPG, SVG, PDF) from a Plotly configuration provided directly as a JSON or YAML string in `config_content`. Specify the format of the string in `config_format` and the desired output filename and image format.",
    category="data_analysis",
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["tool:data:chart"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "config_content": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The Plotly configuration (JSON or YAML) as a string.",
            ),
            "config_format": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The format of the config_content ('json' or 'yaml').",
                enum=["json", "yaml"],
            ),
            "output_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The desired filename for the output image artifact.",
            ),
            "output_format": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The desired image format ('png', 'jpg', 'svg', 'pdf', etc.). Defaults to 'png'.",
                nullable=True,
            ),
        },
        required=["config_content", "config_format", "output_filename"],
    ),
    examples=[],
)

tool_registry.register(create_chart_from_plotly_config_tool_def)
