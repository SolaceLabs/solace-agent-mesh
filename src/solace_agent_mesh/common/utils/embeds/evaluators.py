"""
Contains individual evaluator functions for different embed types
and the mapping dictionary.
"""

import logging
import json
from datetime import datetime
import uuid
from typing import Any, Callable, Dict, Optional, Tuple
from asteval import Interpreter
import math, random

from ....agent.utils.artifact_helpers import format_metadata_for_llm
from .constants import EMBED_CHAIN_DELIMITER

log = logging.getLogger(__name__)

MATH_SAFE_SYMBOLS = {
    # Basic math operations
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    # Math module functions
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "sqrt": math.sqrt,
    "pow": math.pow,
    "exp": math.exp,
    "log": math.log,
    "log10": math.log10,
    "pi": math.pi,
    "e": math.e,
    "inf": math.inf,
    "ceil": math.ceil,
    "floor": math.floor,
    # Trigonometric helpers
    "radians": math.radians,
    # Combinatorics/Statistical
    "factorial": math.factorial,
    "sum": sum,
    # Hyperbolic functions
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    # Random functions
    "random": random.random,
    "randint": random.randint,
    "uniform": random.uniform,
}


def _evaluate_math_embed(
    expression: str,
    context: Any,
    log_identifier: str,
    format_spec: Optional[str] = None,
) -> Tuple[str, Optional[str], int]:
    """
    Evaluates a 'math' embed using asteval.
    Applies format_spec if the result is numeric and format_spec is provided.
    Returns (string_value, error_message, size_of_string_value).
    """
    try:
        user_symtable = MATH_SAFE_SYMBOLS.copy()

        local_interpreter = Interpreter(symtable=user_symtable)
        result = local_interpreter.eval(expression.strip())

        if local_interpreter.error:
            error_messages = [err.msg for err in local_interpreter.error]
            error_msg_str = "; ".join(error_messages)
            err_str = f"[Error: Math evaluation error: {error_msg_str}]"
            return err_str, error_msg_str, len(err_str.encode("utf-8"))

        str_value: str
        if isinstance(result, (int, float)) and format_spec:
            try:
                str_value = format(result, format_spec)
            except ValueError as fmt_err:
                log.warning(
                    "%s Invalid format_spec '%s' for math result %s: %s. Falling back to str().",
                    log_identifier,
                    format_spec,
                    result,
                    fmt_err,
                )
                str_value = str(result)
        else:
            str_value = str(result)

        return str_value, None, len(str_value.encode("utf-8"))
    except ImportError:
        err_msg = "Math evaluation skipped: 'asteval' not installed"
        log.warning("%s %s", log_identifier, err_msg)
        err_str = f"[Error: {err_msg}]"
        return err_str, err_msg, len(err_str.encode("utf-8"))
    except Exception as e:
        err_msg = f"Math evaluation error: {e}"
        err_str = f"[Error: {err_msg}]"
        return err_str, err_msg, len(err_str.encode("utf-8"))


def _evaluate_datetime_embed(
    expression: str,
    context: Any,
    log_identifier: str,
    format_spec: Optional[str] = None,
) -> Tuple[str, Optional[str], int]:
    """
    Evaluates a 'datetime' embed. Ignores format_spec from '|' syntax.
    Returns (string_value, error_message, size_of_string_value).
    """
    format_str = expression.strip()
    now = datetime.now()
    try:
        value = None
        if not format_str or format_str.lower() in ["now", "iso"]:
            value = now.isoformat()
        elif format_str.lower() == "timestamp":
            value = str(now.timestamp())
        elif format_str.lower() == "date":
            value = now.strftime("%Y-%m-%d")
        elif format_str.lower() == "time":
            value = now.strftime("%H:%M:%S")
        else:
            value = now.strftime(format_str)
        return value, None, len(value.encode("utf-8"))
    except Exception as e:
        err_msg = f"Datetime formatting error: {e}"
        err_str = f"[Error: {err_msg}]"
        return err_str, err_msg, len(err_str.encode("utf-8"))


def _evaluate_uuid_embed(
    expression: str,
    context: Any,
    log_identifier: str,
    format_spec: Optional[str] = None,
) -> Tuple[str, Optional[str], int]:
    """
    Evaluates a 'uuid' embed. Ignores format_spec.
    Returns (string_value, error_message, size_of_string_value).
    """
    value = str(uuid.uuid4())
    return value, None, len(value.encode("utf-8"))


async def _evaluate_artifact_meta_embed(
    expression: str,
    context: Dict[str, Any],
    log_identifier: str,
    format_spec: Optional[str] = None,
) -> Tuple[str, Optional[str], int]:
    """
    Evaluates an 'artifact_meta' embed (early stage). Ignores format_spec.
    Context is expected to be a dictionary containing 'artifact_service'
    and 'session_context' (which itself is a dict with app_name, user_id, session_id).
    Returns (string_value, error_message, size_of_string_value).
    """
    if not isinstance(context, dict):
        err_msg = "Invalid context type for artifact_meta, expected dict."
        return f"[Error: {err_msg}]", err_msg, 0

    artifact_service = context.get("artifact_service")
    session_ctx_dict = context.get("session_context")

    if not artifact_service:
        err_msg = "ArtifactService not available in context for artifact_meta"
        return f"[Error: {err_msg}]", err_msg, 0
    if not session_ctx_dict or not isinstance(session_ctx_dict, dict):
        err_msg = (
            "Session context dictionary not available in context for artifact_meta"
        )
        return f"[Error: {err_msg}]", err_msg, 0

    app_name = session_ctx_dict.get("app_name")
    user_id = session_ctx_dict.get("user_id")
    session_id = session_ctx_dict.get("session_id")

    if not all([app_name, user_id, session_id]):
        err_msg = "Missing app_name, user_id, or session_id in session_context for artifact_meta"
        return f"[Error: {err_msg}]", err_msg, 0

    parts = expression.strip().split(":", 1)
    filename = parts[0]
    version_str = parts[1] if len(parts) > 1 else None
    version = None

    if not filename:
        err_msg = "Filename missing for artifact_meta"
        return f"[Error: {err_msg}]", err_msg, 0

    version_to_load: Optional[int] = None
    try:
        if version_str:
            version_to_load = int(version_str)
        else:
            versions = await artifact_service.list_versions(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename,
            )
            if not versions:
                err_msg = f"Artifact '{filename}' not found (no versions available)"
                return f"[Error: {err_msg}]", err_msg, 0
            version_to_load = max(versions)

        if version_to_load is None:
            err_msg = f"Could not determine version for artifact_meta '{filename}'"
            return f"[Error: {err_msg}]", err_msg, 0

        data_artifact_part = await artifact_service.load_artifact(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            version=version_to_load,
        )

        if not data_artifact_part or not data_artifact_part.inline_data:
            err_msg = (
                f"Data artifact '{filename}' v{version_to_load} not found or empty"
            )
            return f"[Error: {err_msg}]", err_msg, 0

        data_mime_type = (
            data_artifact_part.inline_data.mime_type or "application/octet-stream"
        )
        data_size = len(data_artifact_part.inline_data.data)

        custom_metadata_from_file = {}
        metadata_filename = f"{filename}.metadata.json"
        try:
            companion_metadata_part = await artifact_service.load_artifact(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=metadata_filename,
                version=version_to_load,
            )
            if companion_metadata_part and companion_metadata_part.inline_data:
                try:
                    custom_metadata_from_file = json.loads(
                        companion_metadata_part.inline_data.data.decode("utf-8")
                    )
                except json.JSONDecodeError as json_err:
                    log.warning(
                        f"{log_identifier} Failed to parse companion metadata JSON for '{metadata_filename}' v{version_to_load}: {json_err}"
                    )
        except Exception as e_meta_load:
            log.debug(
                f"{log_identifier} Could not load companion metadata file '{metadata_filename}' v{version_to_load} (this is often normal): {e_meta_load}"
            )

        full_metadata_dict = {
            "filename": filename,
            "version": version_to_load,
            "mime_type": data_mime_type,
            "size": data_size,
            **custom_metadata_from_file,
        }

        formatted_text = format_metadata_for_llm(full_metadata_dict)
        return formatted_text, None, len(formatted_text.encode("utf-8"))

    except ValueError as ve:
        err_msg = (
            f"Invalid version specified for artifact_meta: '{version_str}'. Error: {ve}"
        )
        return f"[Error: {err_msg}]", err_msg, 0
    except Exception as e:
        err_msg = f"Error evaluating artifact_meta for '{filename}' v{version_str or 'latest'}: {e}"
        log.error(f"{log_identifier} {err_msg}", exc_info=True)
        return f"[Error: {err_msg}]", err_msg, 0


async def _evaluate_artifact_content_embed(
    expression: str, context: Any, log_identifier: str, config: Optional[Dict] = None
) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    """
    Evaluates an 'artifact_content' embed (late stage).
    Loads the raw artifact content (bytes) and its mime type.
    Returns (content_bytes, mime_type, None) on success,
    or (None, None, error_message) on failure.
    The 'expression' here should ONLY be the artifact specifier (filename[:version]).
    """
    if EMBED_CHAIN_DELIMITER in expression:
        err_msg = f"Internal Error: _evaluate_artifact_content_embed received expression containing chain delimiter ('{EMBED_CHAIN_DELIMITER}'). This indicates an upstream parsing issue. Expression: '{expression}'"
        log.error("%s %s", log_identifier, err_msg)
        return None, None, err_msg

    if not isinstance(context, dict):
        return None, None, "Invalid context for artifact_content embed"

    artifact_service = context.get("artifact_service")
    session_context = context.get("session_context")
    if not artifact_service or not session_context:
        return None, None, "ArtifactService or session context not available"

    app_name = session_context.get("app_name")
    user_id = session_context.get("user_id")
    session_id = session_context.get("session_id")
    if not all([app_name, user_id, session_id]):
        return None, None, "Missing required session identifiers in context"

    artifact_spec = expression.strip()
    parts = artifact_spec.split(":", 1)
    filename = parts[0]
    version_str = parts[1] if len(parts) > 1 else None
    version_to_load: Optional[int] = None

    if not filename:
        return None, None, "Filename missing for artifact_content"

    try:
        if version_str:
            try:
                version_to_load = int(version_str)
            except ValueError:
                err_msg = f"Invalid version format in artifact specifier '{artifact_spec}'. Expected 'filename' or 'filename:integer_version'."
                log.warning("%s %s", log_identifier, err_msg)
                return None, None, err_msg
        else:
            versions = await artifact_service.list_versions(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename,
            )
            if not versions:
                return (
                    None,
                    None,
                    f"Artifact '{filename}' not found (no versions available)",
                )
            version_to_load = max(versions)

        if version_to_load is None:
            return None, None, f"Could not determine version for artifact '{filename}'"

        artifact_part = await artifact_service.load_artifact(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            version=version_to_load,
        )

        if not artifact_part or not artifact_part.inline_data:
            return (
                None,
                None,
                f"Artifact '{filename}' v{version_to_load} not found or empty",
            )

        content_bytes = artifact_part.inline_data.data
        mime_type = artifact_part.inline_data.mime_type

        limit_bytes = (
            config.get("gateway_max_artifact_resolve_size_bytes", -1) if config else -1
        )
        if limit_bytes >= 0 and len(content_bytes) > limit_bytes:
            error_msg = f"Artifact '{filename}' v{version_to_load} exceeds maximum size limit ({len(content_bytes)} > {limit_bytes} bytes)"
            log.warning("%s %s", log_identifier, error_msg)
            return None, None, error_msg

        return content_bytes, mime_type, None

    except FileNotFoundError:
        return None, None, f"Artifact '{filename}' v{version_str or 'latest'} not found"
    except Exception as e:
        log.exception(
            "%s Error loading artifact content for '%s' v%s: %s",
            log_identifier,
            filename,
            version_str or "latest",
            e,
        )
        return (
            None,
            None,
            f"Error loading artifact content for '{filename}' v{version_str or 'latest'}: {e}",
        )


EMBED_EVALUATORS: Dict[str, Callable[..., Tuple[Any, Optional[str]]]] = {
    "math": _evaluate_math_embed,
    "datetime": _evaluate_datetime_embed,
    "uuid": _evaluate_uuid_embed,
    "artifact_meta": _evaluate_artifact_meta_embed,
}
