"""
Custom Solace AI Connector Component to host the FastAPI server for the Universal Webhook Gateway.
"""

import asyncio
import base64
import mimetypes
import secrets
import uuid
import json
import yaml
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Tuple, Union, Callable, Coroutine

import uvicorn
from fastapi import (
    FastAPI,
    Request as FastAPIRequest,
    Response as FastAPIResponse,
    HTTPException,
    status,
    UploadFile,
)
from fastapi.responses import JSONResponse

from solace_ai_connector.common.log import log
from solace_ai_connector.common.message import Message as SolaceMessage

from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
from solace_agent_mesh.common.types import (
    Part as A2APart,
    TextPart,
    Task,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    JSONRPCError,
)

from solace_agent_mesh.agent.utils.artifact_helpers import save_artifact_with_metadata


info = {
    "class_name": "WebhookGatewayComponent",
    "description": (
        "Hosts a FastAPI server to provide dynamic webhook endpoints, "
        "translates incoming HTTP requests into A2A tasks, and manages "
        "immediate HTTP acknowledgments. Configuration is derived from "
        "WebhookGatewayApp's app_config."
    ),
    "config_parameters": [
        # Configuration parameters are defined and validated by WebhookGatewayApp.app_schema.
    ],
    "input_schema": {
        "type": "object",
        "description": "Not typically used; component reacts to events from its input queue (if any) or HTTP requests.",
        "properties": {},
    },
    "output_schema": {
        "type": "object",
        "description": "Not typically used; component sends data via HTTP responses and A2A messages.",
        "properties": {},
    },
}


class WebhookGatewayComponent(BaseGatewayComponent):
    """
    Hosts the FastAPI server for the Universal Webhook Gateway.
    """

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        log.info("%s Initializing Webhook Gateway Component...", self.log_identifier)

        try:
            self.webhook_server_host: str = self.get_config(
                "webhook_server_host", "0.0.0.0"
            )
            self.webhook_server_port: int = self.get_config("webhook_server_port", 8080)
            self.cors_allowed_origins: List[str] = self.get_config(
                "cors_allowed_origins", ["*"]
            )
            self.webhook_endpoints_config: List[Dict[str, Any]] = self.get_config(
                "webhook_endpoints", []
            )

            log.info(
                "%s Webhook server config: Host=%s, Port=%d, CORS Origins=%s",
                self.log_identifier,
                self.webhook_server_host,
                self.webhook_server_port,
                self.cors_allowed_origins,
            )
            log.info(
                "%s Loaded %d webhook endpoint configurations.",
                self.log_identifier,
                len(self.webhook_endpoints_config),
            )

        except Exception as e:
            log.error(
                "%s Failed to retrieve essential webhook configuration: %s",
                self.log_identifier,
                e,
            )
            raise ValueError(f"Webhook configuration retrieval error: {e}") from e

        self.fastapi_app: Optional[FastAPI] = None
        self.uvicorn_server: Optional[uvicorn.Server] = None

        log.info(
            "%s Webhook Gateway Component initialized successfully.",
            self.log_identifier,
        )

    def _create_webhook_handler(
        self, endpoint_config: Dict[str, Any]
    ) -> Callable[[FastAPIRequest], Coroutine[Any, Any, FastAPIResponse]]:
        """
        Factory function to create a unique request handler for each webhook endpoint.
        """
        log_id_prefix = f"{self.log_identifier}[Handler:{endpoint_config.get('path')}]"

        async def dynamic_handler(request: FastAPIRequest) -> FastAPIResponse:
            log.info(
                "%s Received request: %s %s from %s",
                log_id_prefix,
                request.method,
                request.url.path,
                request.client.host if request.client else "unknown",
            )
            try:
                event_data_with_config = {
                    "request": request,
                    "endpoint_config": endpoint_config,
                }
                user_identity = await self.authenticate_and_enrich_user(
                    event_data_with_config
                )
                if user_identity is None:
                    log.warning("%s Authentication failed.", log_id_prefix)
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication failed or not permitted for this endpoint.",
                    )
                log.info(
                    "%s Authenticated user identity: %s",
                    log_id_prefix,
                    user_identity.get("id", "unknown"),
                )

                target_agent_name, a2a_parts, external_request_context = (
                    await self._translate_external_input(
                        request, endpoint_config, user_identity
                    )
                )
                log.info(
                    "%s Input translated. Target agent: %s, A2A Parts: %d",
                    log_id_prefix,
                    target_agent_name,
                    len(a2a_parts),
                )

                task_id = await self.submit_a2a_task(
                    target_agent_name=target_agent_name,
                    a2a_parts=a2a_parts,
                    external_request_context=external_request_context,
                    user_identity=user_identity,
                    is_streaming=False,
                )
                log.info(
                    "%s A2A task submitted successfully. TaskID: %s",
                    log_id_prefix,
                    task_id,
                )

                response_content = {
                    "taskId": task_id,
                    "message": "Webhook request received and acknowledged.",
                    "endpoint_path": endpoint_config.get("path"),
                    "target_agent": target_agent_name,
                }
                return JSONResponse(
                    content=response_content, status_code=status.HTTP_202_ACCEPTED
                )

            except HTTPException as http_exc:
                log.warning(
                    "%s HTTPException in handler: %s", log_id_prefix, http_exc.detail
                )
                raise http_exc
            except ValueError as ve:
                log.error(
                    "%s Value error in handler: %s", log_id_prefix, ve, exc_info=True
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve)
                )
            except PermissionError as pe:
                log.error(
                    "%s Permission error in handler: %s",
                    log_id_prefix,
                    pe,
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail=str(pe)
                )
            except Exception as e:
                log.exception(
                    "%s Unexpected error in dynamic webhook handler: %s",
                    log_id_prefix,
                    e,
                )
                error_detail = (
                    f"An unexpected server error occurred: {type(e).__name__}."
                )
                if str(e):
                    error_detail += f" Details: {str(e)}"
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=error_detail,
                )

        return dynamic_handler

    def _start_listener(self) -> None:
        """
        GDK Hook: Starts the FastAPI/Uvicorn server and dynamically adds routes.
        This method is called by BaseGatewayComponent.run() within the self.async_loop.
        """
        log.info(
            "%s [_start_listener] Attempting to start FastAPI/Uvicorn server...",
            self.log_identifier,
        )
        if self.uvicorn_server and self.uvicorn_server.started:
            log.warning("%s FastAPI server already started.", self.log_identifier)
            return

        try:
            from .main import app as fastapi_app_instance, setup_dependencies

            self.fastapi_app = fastapi_app_instance
            setup_dependencies(self)

            if self.fastapi_app:
                for endpoint_config in self.webhook_endpoints_config:
                    try:
                        path = endpoint_config.get("path")
                        method = endpoint_config.get("method", "POST").upper()

                        if not path or not path.startswith("/"):
                            log.warning(
                                "%s Skipping endpoint: Invalid path '%s'. Path must start with '/'. Config: %s",
                                self.log_identifier,
                                path,
                                endpoint_config,
                            )
                            continue
                        if not method:
                            log.warning(
                                "%s Skipping endpoint with missing method: %s",
                                self.log_identifier,
                                endpoint_config,
                            )
                            continue

                        handler_function = self._create_webhook_handler(endpoint_config)

                        self.fastapi_app.add_api_route(
                            path,
                            handler_function,
                            methods=[method],
                            tags=["Dynamic Webhooks"],
                            summary=f"Webhook for {endpoint_config.get('target_agent_name', 'agent')}",
                        )
                        log.info(
                            "%s Added dynamic route: %s %s -> target: %s",
                            self.log_identifier,
                            method,
                            path,
                            endpoint_config.get("target_agent_name"),
                        )

                    except Exception as route_err:
                        log.error(
                            "%s Error processing endpoint config %s: %s",
                            self.log_identifier,
                            endpoint_config.get("path", "<unknown_path>"),
                            route_err,
                            exc_info=True,
                        )
            else:
                log.error(
                    "%s FastAPI app instance not available for adding routes.",
                    self.log_identifier,
                )

            config = uvicorn.Config(
                app=self.fastapi_app,
                host=self.webhook_server_host,
                port=self.webhook_server_port,
                log_level="info",
                loop="asyncio",
                lifespan="on",
            )
            self.uvicorn_server = uvicorn.Server(config)

            if self.async_loop:
                log.info(
                    "%s Scheduling Uvicorn server on existing async_loop: %s",
                    self.log_identifier,
                    self.async_loop,
                )
                asyncio.ensure_future(self.uvicorn_server.serve(), loop=self.async_loop)
                log.info(
                    "%s FastAPI/Uvicorn server scheduled to run on http://%s:%d",
                    self.log_identifier,
                    self.webhook_server_host,
                    self.webhook_server_port,
                )
            else:
                log.error(
                    "%s self.async_loop not available. Cannot start Uvicorn server.",
                    self.log_identifier,
                )
                raise RuntimeError("Asyncio event loop not available for Uvicorn.")

        except ImportError as ie:
            log.exception(
                "%s Failed to import FastAPI app or setup_dependencies from .main: %s. Ensure main.py is correctly structured.",
                self.log_identifier,
                ie,
            )
            self.stop_signal.set()
            raise
        except Exception as e:
            log.exception(
                "%s Failed to start FastAPI/Uvicorn server: %s",
                self.log_identifier,
                e,
            )
            self.stop_signal.set()
            raise

    def _stop_listener(self) -> None:
        """
        GDK Hook: Signals the Uvicorn server to shut down.
        This method is called by BaseGatewayComponent.cleanup().
        """
        log.info(
            "%s _stop_listener called. Signaling Uvicorn server to exit...",
            self.log_identifier,
        )
        if self.uvicorn_server:
            self.uvicorn_server.should_exit = True
        log.info("%s Uvicorn server signaled to exit.", self.log_identifier)

    async def _extract_initial_claims(
        self, external_event_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Extracts the primary identity claims from a webhook request
        based on the endpoint's authentication configuration.
        """
        request: FastAPIRequest = external_event_data["request"]
        endpoint_config: Dict[str, Any] = external_event_data["endpoint_config"]
        log_id_prefix = (
            f"{self.log_identifier}[ExtractClaims:{endpoint_config.get('path')}]"
        )

        auth_config = endpoint_config.get("auth", {"type": "none"})
        auth_type = auth_config.get("type", "none").lower()
        assumed_identity_str = endpoint_config.get("assumed_user_identity")

        log.debug(
            "%s Attempting authentication with type: %s", log_id_prefix, auth_type
        )

        if auth_type == "none":
            user_id = assumed_identity_str or "webhook_anonymous_user"
            claims = {"id": user_id, "source": "webhook_anonymous"}
            log.info(
                "%s Authentication type 'none'. Using claims: %s", log_id_prefix, claims
            )
            return claims

        elif auth_type == "token":
            token_cfg = auth_config.get("token_config")
            if not token_cfg:
                log.error(
                    "%s 'token_config' missing for token authentication.", log_id_prefix
                )
                return None

            token_location = token_cfg.get("location", "header").lower()
            token_name = token_cfg.get("name")
            expected_token_value = token_cfg.get("value")

            if not token_name or not expected_token_value:
                log.error(
                    "%s 'name' or 'value' missing in token_config.", log_id_prefix
                )
                return None

            received_token: Optional[str] = None
            if token_location == "header":
                received_token = request.headers.get(token_name)
            elif token_location == "query_param":
                received_token = request.query_params.get(token_name)
            else:
                log.error(
                    "%s Invalid token location: %s", log_id_prefix, token_location
                )
                return None

            if not received_token:
                log.warning(
                    "%s Token not found in %s named '%s'.",
                    log_id_prefix,
                    token_location,
                    token_name,
                )
                return None

            if secrets.compare_digest(received_token, expected_token_value):
                user_id = assumed_identity_str or f"token_user:{token_name}"
                claims = {"id": user_id, "source": "webhook_token"}
                log.info(
                    "%s Token authentication successful. Using claims: %s",
                    log_id_prefix,
                    claims,
                )
                return claims
            else:
                log.warning(
                    "%s Token authentication failed. Mismatch for token '%s'.",
                    log_id_prefix,
                    token_name,
                )
                return None

        elif auth_type == "basic":
            basic_cfg = auth_config.get("basic_auth_config")
            if not basic_cfg:
                log.error(
                    "%s 'basic_auth_config' missing for basic authentication.",
                    log_id_prefix,
                )
                return None

            expected_credentials_str = basic_cfg.get("credentials")
            if not expected_credentials_str:
                log.error(
                    "%s 'credentials' missing in basic_auth_config.", log_id_prefix
                )
                return None

            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.lower().startswith("basic "):
                log.warning(
                    "%s Basic authentication header missing or malformed.",
                    log_id_prefix,
                )
                return None

            try:
                encoded_creds = auth_header.split(" ", 1)[1]
                decoded_creds_bytes = base64.b64decode(encoded_creds)
                received_creds_str = decoded_creds_bytes.decode("utf-8")

                if secrets.compare_digest(received_creds_str, expected_credentials_str):
                    username = received_creds_str.split(":", 1)[0]
                    user_id = assumed_identity_str or username
                    claims = {
                        "id": user_id,
                        "username": username,
                        "source": "webhook_basic_auth",
                    }
                    log.info(
                        "%s Basic authentication successful for user '%s'. Using claims: %s",
                        log_id_prefix,
                        username,
                        claims,
                    )
                    return claims
                else:
                    log.warning(
                        "%s Basic authentication failed. Credentials mismatch.",
                        log_id_prefix,
                    )
                    return None
            except (
                IndexError,
                ValueError,
                base64.binascii.Error,
                UnicodeDecodeError,
            ) as e:
                log.warning(
                    "%s Error decoding Basic authentication credentials: %s",
                    log_id_prefix,
                    e,
                )
                return None
        else:
            log.error(
                "%s Unknown authentication type '%s' configured for endpoint.",
                log_id_prefix,
                auth_type,
            )
            return None

    async def _save_file_as_artifact(
        self,
        content_bytes: bytes,
        filename: str,
        mime_type: str,
        user_identity: str,
        a2a_session_id: str,
        log_id_prefix: str,
        is_main_payload_artifact: bool = False,
    ) -> Optional[str]:
        """Helper to save bytes as an artifact and return its URI."""
        if not self.shared_artifact_service:
            log.error(
                "%s Cannot save file '%s': shared_artifact_service is not available.",
                log_id_prefix,
                filename,
            )
            return None
        try:
            artifact_metadata_to_store = {
                "source": (
                    "webhook_gateway_file_upload"
                    if not is_main_payload_artifact
                    else "webhook_gateway_payload"
                ),
                "original_filename": filename,
                "upload_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            save_result = await asyncio.to_thread(
                save_artifact_with_metadata,
                artifact_service=self.shared_artifact_service,
                app_name=self.gateway_id,
                user_id=str(user_identity),
                session_id=a2a_session_id,
                filename=filename,
                content_bytes=content_bytes,
                mime_type=mime_type,
                metadata_dict=artifact_metadata_to_store,
                timestamp=datetime.now(timezone.utc),
            )
            if save_result["status"] not in ["success", "partial_success"]:
                log.error(
                    "%s Failed to save file '%s' as artifact: %s",
                    log_id_prefix,
                    filename,
                    save_result.get("message"),
                )
                return None

            data_version = save_result.get("data_version", 0)
            artifact_uri = f"artifact://{self.gateway_id}/{user_identity}/{a2a_session_id}/{filename}?version={data_version}"
            log.info(
                "%s Saved file '%s' as artifact: %s",
                log_id_prefix,
                filename,
                artifact_uri,
            )
            return artifact_uri
        except Exception as e:
            log.exception(
                "%s Error saving file '%s' as artifact: %s", log_id_prefix, filename, e
            )
            return None

    async def _translate_external_input(
        self,
        request: FastAPIRequest,
        endpoint_config: Dict[str, Any],
        user_identity: Dict[str, Any],
    ) -> Tuple[str, List[A2APart], Dict[str, Any]]:
        """
        Translates webhook data (FastAPIRequest) into A2A task parameters.
        Parses payload based on 'payload_format', optionally saves as artifact,
        and applies 'input_template'.
        """
        log_id_prefix = (
            f"{self.log_identifier}[TranslateInput:{endpoint_config.get('path')}]"
        )
        user_id_for_log = user_identity.get("id", "unknown")
        log.debug(
            "%s Translating input for user '%s'. Endpoint config: %s",
            log_id_prefix,
            user_id_for_log,
            endpoint_config.get("path"),
        )

        target_agent_name = endpoint_config.get("target_agent_name")
        input_template_str = endpoint_config.get("input_template")
        payload_format = endpoint_config.get("payload_format", "json").lower()
        save_as_artifact_flag = endpoint_config.get("save_payload_as_artifact", False)
        artifact_filename_tmpl = endpoint_config.get("artifact_filename_template")
        mime_override = endpoint_config.get("artifact_mime_type_override")

        if not target_agent_name:
            raise ValueError("target_agent_name is missing in endpoint configuration.")
        if not input_template_str:
            raise ValueError("input_template is missing in endpoint configuration.")

        sac_message = SolaceMessage()
        sac_message.topic = request.url.path
        sac_message.user_properties = dict(request.query_params)

        client_host = request.client.host if request.client else "unknown"

        sac_message.set_private_data("headers", dict(request.headers))
        sac_message.set_private_data("client_host", client_host)
        sac_message.set_private_data("method", request.method)

        a2a_session_id = f"webhook-session-{uuid.uuid4().hex}"

        raw_body_bytes: Optional[bytes] = None

        if payload_format == "form_data":
            form_data = await request.form()
            non_file_fields = {}
            uploaded_file_infos = []

            for key, value in form_data.items():
                if isinstance(value, UploadFile):
                    file_content_bytes = await value.read()
                    file_mime_type = value.content_type or "application/octet-stream"
                    file_artifact_uri = await self._save_file_as_artifact(
                        content_bytes=file_content_bytes,
                        filename=value.filename or f"upload_{uuid.uuid4().hex}",
                        mime_type=file_mime_type,
                        user_identity=user_identity.get("id"),
                        a2a_session_id=a2a_session_id,
                        log_id_prefix=log_id_prefix,
                    )
                    if file_artifact_uri:
                        uploaded_file_infos.append(
                            {
                                "field_name": key,
                                "filename": value.filename,
                                "mime_type": file_mime_type,
                                "uri": file_artifact_uri,
                                "size": len(file_content_bytes),
                            }
                        )
                    await value.close()
                else:
                    non_file_fields[key] = value

            sac_message.set_private_data("uploaded_files", uploaded_file_infos)

            if save_as_artifact_flag:
                form_fields_json_bytes = json.dumps(non_file_fields).encode("utf-8")
                main_artifact_filename = "form_fields.json"
                if artifact_filename_tmpl:
                    sac_message.payload = non_file_fields
                    try:
                        main_artifact_filename = (
                            sac_message.get_data(f"template:{artifact_filename_tmpl}")
                            or main_artifact_filename
                        )
                    except Exception:
                        pass
                    sac_message.payload = {}

                main_artifact_uri = await self._save_file_as_artifact(
                    content_bytes=form_fields_json_bytes,
                    filename=main_artifact_filename,
                    mime_type="application/json",
                    user_identity=user_identity.get("id"),
                    a2a_session_id=a2a_session_id,
                    log_id_prefix=log_id_prefix,
                    is_main_payload_artifact=True,
                )
                if main_artifact_uri:
                    sac_message.set_private_data(
                        "webhook_payload_artifact_uri", main_artifact_uri
                    )
                    sac_message.set_private_data(
                        "webhook_payload_artifact_filename", main_artifact_filename
                    )
                    sac_message.set_private_data(
                        "webhook_payload_artifact_mime_type", "application/json"
                    )
                sac_message.payload = {}
            else:
                sac_message.payload = non_file_fields

        elif payload_format == "binary":
            raw_body_bytes = await request.body()
            binary_filename = "binary_payload.bin"
            if artifact_filename_tmpl:
                sac_message.payload = {
                    "raw_preview": raw_body_bytes[:100].decode("utf-8", "ignore")
                }
                try:
                    binary_filename = (
                        sac_message.get_data(f"template:{artifact_filename_tmpl}")
                        or binary_filename
                    )
                except Exception:
                    pass
                sac_message.payload = {}

            binary_mime_type = (
                mime_override
                or request.headers.get("Content-Type")
                or "application/octet-stream"
            )

            binary_artifact_uri = await self._save_file_as_artifact(
                content_bytes=raw_body_bytes,
                filename=binary_filename,
                mime_type=binary_mime_type,
                user_identity=user_identity.get("id"),
                a2a_session_id=a2a_session_id,
                log_id_prefix=log_id_prefix,
                is_main_payload_artifact=True,
            )
            if binary_artifact_uri:
                sac_message.set_private_data(
                    "binary_payload_artifact_uri", binary_artifact_uri
                )
                sac_message.set_private_data(
                    "binary_payload_artifact_filename", binary_filename
                )
                sac_message.set_private_data(
                    "binary_payload_artifact_mime_type", binary_mime_type
                )
            sac_message.payload = {}

        elif save_as_artifact_flag:
            raw_body_bytes = await request.body()
            determined_mime_type = mime_override or request.headers.get("Content-Type")
            if not determined_mime_type:
                if payload_format == "json":
                    determined_mime_type = "application/json"
                elif payload_format == "yaml":
                    determined_mime_type = "application/yaml"
                elif payload_format == "text":
                    determined_mime_type = "text/plain"
                elif payload_format == "xml":
                    determined_mime_type = "application/xml"

            filename_for_artifact = f"{uuid.uuid4().hex}.dat"
            if artifact_filename_tmpl:
                sac_message.payload = {
                    "raw_preview": raw_body_bytes[:100].decode("utf-8", "ignore")
                }
                try:
                    filename_for_artifact = (
                        sac_message.get_data(f"template:{artifact_filename_tmpl}")
                        or filename_for_artifact
                    )
                except Exception as e:
                    log.error(
                        "%s Error processing artifact filename template: %s",
                        log_id_prefix,
                        e,
                    )
                    pass
                sac_message.payload = {}

            if not determined_mime_type and "." in filename_for_artifact:
                guessed_type, _ = mimetypes.guess_type(filename_for_artifact)
                if guessed_type:
                    determined_mime_type = guessed_type
            if not determined_mime_type:
                determined_mime_type = "application/octet-stream"

            main_artifact_uri = await self._save_file_as_artifact(
                content_bytes=raw_body_bytes,
                filename=filename_for_artifact,
                mime_type=determined_mime_type,
                user_identity=user_identity.get("id"),
                a2a_session_id=a2a_session_id,
                log_id_prefix=log_id_prefix,
                is_main_payload_artifact=True,
            )
            if main_artifact_uri:
                sac_message.set_private_data(
                    "webhook_payload_artifact_uri", main_artifact_uri
                )
                sac_message.set_private_data(
                    "webhook_payload_artifact_filename", filename_for_artifact
                )
                sac_message.set_private_data(
                    "webhook_payload_artifact_mime_type", determined_mime_type
                )
            sac_message.payload = {}
        else:
            raw_body_bytes = await request.body()
            try:
                if payload_format == "json":
                    sac_message.payload = json.loads(raw_body_bytes.decode("utf-8"))
                elif payload_format == "yaml":
                    sac_message.payload = yaml.safe_load(raw_body_bytes)
                elif payload_format in ["text", "xml"]:
                    sac_message.payload = raw_body_bytes.decode(
                        "utf-8", errors="replace"
                    )
                else:
                    sac_message.payload = raw_body_bytes.decode(
                        "utf-8", errors="replace"
                    )
                    log.warning(
                        "%s Unknown payload_format '%s' when not saving artifact. Treating as text.",
                        log_id_prefix,
                        payload_format,
                    )
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON payload: {e}")
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML payload: {e}")
            except Exception as e:
                log.error(
                    "%s Error parsing body for format '%s': %s",
                    log_id_prefix,
                    payload_format,
                    e,
                )
                sac_message.payload = f"[Error parsing request body: {e}]"

        try:
            templated_text = sac_message.get_data(f"template:{input_template_str}")
            log.debug(
                "%s Processed input_template. Result length: %d",
                log_id_prefix,
                len(templated_text or ""),
            )
        except Exception as template_err:
            log.error(
                "%s Error processing input_template: %s",
                log_id_prefix,
                template_err,
                exc_info=True,
            )
            raise ValueError(
                f"Error processing input_template: {template_err}"
            ) from template_err

        a2a_parts: List[A2APart] = []
        if templated_text is not None:
            a2a_parts.append(TextPart(text=str(templated_text)))

        external_request_context = {
            "webhook_path": request.url.path,
            "target_agent_name": target_agent_name,
            "user_id_for_a2a": user_identity.get("id"),
            "app_name_for_artifacts": self.gateway_id,
            "user_id_for_artifacts": user_identity.get("id"),
            "a2a_session_id": a2a_session_id,
        }
        log.debug(
            "%s Translation complete. Target: %s, Parts: %d, Context: %s",
            log_id_prefix,
            target_agent_name,
            len(a2a_parts),
            external_request_context,
        )
        return target_agent_name, a2a_parts, external_request_context

    async def _send_update_to_external(
        self,
        external_request_context: Dict[str, Any],
        event_data: Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent],
        is_final_chunk_of_update: bool,
    ) -> None:
        log_id_prefix = f"{self.log_identifier}[SendUpdate]"
        a2a_task_id = event_data.id
        log.debug(
            "%s _send_update_to_external called for task %s. Webhook gateway already ACKed. Update Type: %s. Final Chunk: %s. Context: %s",
            log_id_prefix,
            a2a_task_id,
            type(event_data).__name__,
            is_final_chunk_of_update,
            external_request_context,
        )

    async def _send_final_response_to_external(
        self, external_request_context: Dict[str, Any], task_data: Task
    ) -> None:
        log_id_prefix = f"{self.log_identifier}[SendFinalResponse]"
        a2a_task_id = task_data.id
        log.debug(
            "%s _send_final_response_to_external called for task %s. Webhook gateway already ACKed. Task Status: %s. Context: %s",
            log_id_prefix,
            a2a_task_id,
            task_data.status.state,
            external_request_context,
        )

    async def _send_error_to_external(
        self, external_request_context: Dict[str, Any], error_data: JSONRPCError
    ) -> None:
        log_id_prefix = f"{self.log_identifier}[SendError]"
        log.debug(
            "%s _send_error_to_external called. Webhook gateway already ACKed. Error Code: %s, Message: %s. Context: %s",
            log_id_prefix,
            error_data.code,
            error_data.message,
            external_request_context,
        )
