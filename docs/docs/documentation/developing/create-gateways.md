---
title: Create Gateways
sidebar_position: 40
---

# Create Gateways

Gateways in Solace Agent Mesh serve as bridges between external systems and the A2A (Agent-to-Agent) ecosystem. They enable your agents to receive information from and send responses to diverse external platforms like chat systems, web applications, IoT devices, APIs, and file systems.

This guide walks you through the steps of creating custom gateways, from basic concepts to advanced implementations.

## What Are Gateways?

A gateway acts as a translator and coordinator that:

1. **Receives** events, messages, or data from external systems
2. **Authenticates** and authorizes external interactions
3. **Translates** external data into standardized A2A `Task` format
4. **Submits** tasks to target A2A agents for processing
5. **Receives** responses and status updates from agents
6. **Translates** A2A responses back to external system format
7. **Sends** results back to the originating external system

## Quick Start: Creating Your First Gateway

You can create a gateway directly using the Solace Agent Mesh CLI `sam add gateway`:

```bash
sam add gateway my-custom-gateway
```

This command:
- Launches an interactive setup (or use `--gui` for browser-based configuration)
- Generates the necessary files and configuration
- Sets up the basic gateway structure

### CLI Options

You can customize the gateway creation with these options:

```bash
sam add gateway my-gateway \
    --namespace "myorg/dev" \
    --gateway-id "my-custom-gw-id" \
    --artifact-service-type "filesystem" \
    --artifact-service-base-path "var/data/my-gateway-artifacts" \
    --system-purpose "This gateway processes external data feeds" \
    --response-format "Agents should respond with structured JSON"
```

For a complete list of options, run:
```bash
sam add gateway --help
```
## Gateway Architecture

Every Solace Agent Mesh gateway consists of two main components:

### Gateway App
Gateway App (`app.py`):
- Defines configuration schema
- Manages gateway-level settings
- Links to the gateway component

### Gateway Component
Gateway Component (`component.py`):
- Contains the core business logic
- Handles external system integration
- Implements required abstract methods

## Step-by-Step Tutorial

Let's create a practical example, **Directory Monitor Gateway**, a gateway that monitors a directory for new files and sends them to agents for processing.

You can create a gateway using either `sam add gateway <your_gateway_name>` command directly or `sam plugin create <your_gateway_plugin_name> --type gateway` command as gateway plugin.

:::tip[Gateway as plugin]

Gateways can also be implemented as plugins. This allows you to easily package your gateway logic and reuse it across different projects. 

To create a plugin of type gateway, use the `sam plugin create <your_gateway_plugin_name> --type gateway` command.

For a complete list of options, run:
```bash
sam plugin create --help
```

To create a gateway instance based on a plugin, use the `sam plugin add <your_gateway_name> --plugin <your_gateway_plugin>` command.

For a complete list of options, run:
```bash
sam plugin add --help
```

Although the specific directory structure may differ from standalone gateways, the core concepts remain the same. The core files remain the same: app.py, component.py, and the YAML configuration file.
:::


### Step 1: Generate the Gateway Structure

This tutorial shows you how to create a new gateway with the `sam add gateway` command.

```bash
sam add gateway dir-monitor
```

This creates:
- `configs/gateways/dir_monitor_config.yaml` - Configuration file
- `src/dir_monitor/app.py` - Gateway app class
- `src/dir_monitor/component.py` - Gateway component class

### Step 2: Define Configuration Schema

Define Configuration Schema (`app.py`)

```python
# src/dir_monitor/app.py
from typing import Any, Dict, List, Type
from solace_ai_connector.common.log import log
from solace_agent_mesh.gateway.base.app import BaseGatewayApp
from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
from .component import DirMonitorGatewayComponent

# Module info required by SAC
info = {
    "class_name": "DirMonitorGatewayApp",
    "description": "Custom App class for the A2A DirMonitor Gateway.",
}

class DirMonitorGatewayApp(BaseGatewayApp):
    """
    Directory Monitor Gateway App
    Extends BaseGatewayApp with directory monitoring specific configuration.
    """

    # Define gateway-specific configuration parameters
    SPECIFIC_APP_SCHEMA_PARAMS: List[Dict[str, Any]] = [
        {
            "name": "directory_path",
            "required": True,
            "type": "string",
            "description": "The directory path to monitor for changes.",
        },
        {
            "name": "target_agent_name",
            "required": False,
            "type": "string",
            "default": "OrchestratorAgent",
            "description": "The A2A agent to send tasks to.",
        },
        {
            "name": "default_user_identity",
            "required": False,
            "type": "string",
            "default": "dir_monitor_user",
            "description": "Default user identity for A2A tasks.",
        },
        {
            "name": "error_directory_path",
            "required": True,
            "type": "string",
            "description": "Directory to move files if processing fails.",
        },
    ]

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        log_prefix = app_info.get("name", "DirMonitorGatewayApp")
        log.info("[%s] Initializing Directory Monitor Gateway App...", log_prefix)
        super().__init__(app_info=app_info, **kwargs)
        log.info("[%s] Directory Monitor Gateway App initialized.", self.name)

    def _get_gateway_component_class(self) -> Type[BaseGatewayComponent]:
        """Returns the gateway component class for this app."""
        return DirMonitorGatewayComponent
```

### Step 3: Implement Core Logic

Implement Core Logic (`component.py`)

```python
# src/dir_monitor/component.py
import asyncio
import os
import shutil
import mimetypes
import threading
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime, timezone

from solace_ai_connector.common.log import log

# Import watchdog for file system monitoring
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = None

from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
from solace_agent_mesh.common.types import (
    Part as A2APart,
    TextPart,
    FilePart,
    Task,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    JSONRPCError,
    FileContent,
)
from solace_agent_mesh.agent.utils.artifact_helpers import save_artifact_with_metadata

# Component info
info = {
    "class_name": "DirMonitorGatewayComponent",
    "description": "Monitors directories for new files and processes them via A2A agents.",
}

class DirMonitorGatewayComponent(BaseGatewayComponent):
    """
    Directory Monitor Gateway Component
    Watches a directory and creates A2A tasks for new files.
    """

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        log.info("%s Initializing Directory Monitor Gateway Component...", self.log_identifier)

        # Check if watchdog is available
        if not WATCHDOG_AVAILABLE:
            log.error("%s Watchdog library not found. Install with: pip install watchdog", 
                     self.log_identifier)
            raise ImportError("Watchdog library required for directory monitoring")

        # Load configuration
        try:
            self.directory_path = self.get_config("directory_path")
            self.target_agent_name = self.get_config("target_agent_name", "OrchestratorAgent")
            self.default_user_identity_id = self.get_config("default_user_identity", "dir_monitor_user")
            self.error_directory_path = self.get_config("error_directory_path")

            # Validate directories
            if not os.path.isdir(self.directory_path):
                raise ValueError(f"Monitor directory not found: {self.directory_path}")
            
            os.makedirs(self.error_directory_path, exist_ok=True)
            log.info("%s Monitoring: %s, Error dir: %s", 
                    self.log_identifier, self.directory_path, self.error_directory_path)

        except Exception as e:
            log.error("%s Configuration error: %s", self.log_identifier, e)
            raise

        # Initialize monitoring components
        self.observer: Optional[Observer] = None
        self.watchdog_thread: Optional[threading.Thread] = None

        log.info("%s Directory Monitor Gateway Component initialized.", self.log_identifier)

    class DirWatchEventHandler(FileSystemEventHandler):
        """Handles file system events from Watchdog."""
        
        def __init__(self, component_ref: 'DirMonitorGatewayComponent'):
            super().__init__()
            self.component_ref = component_ref
            self.log_identifier = f"{component_ref.log_identifier}[FileHandler]"

        def on_created(self, event):
            if event.is_directory:
                return

            file_path = event.src_path
            log.info("%s New file detected: %s", self.log_identifier, file_path)

            # Bridge to async loop
            if self.component_ref.async_loop and self.component_ref.async_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.component_ref._process_new_file(file_path),
                    self.component_ref.async_loop
                )
            else:
                log.error("%s Async loop not available for file: %s", 
                         self.log_identifier, file_path)

    def generate_uuid(self) -> str:
        """Generate a unique identifier."""
        import uuid
        return str(uuid.uuid4())

    def _start_listener(self) -> None:
        """Start the directory monitoring listener."""
        log_id_prefix = f"{self.log_identifier}[StartListener]"
        log.info("%s Starting directory monitor for: %s", log_id_prefix, self.directory_path)

        if not WATCHDOG_AVAILABLE:
            log.error("%s Watchdog not available", log_id_prefix)
            self.stop_signal.set()
            return

        # Set up file system observer
        self.observer = Observer()
        event_handler = self.DirWatchEventHandler(self)
        self.observer.schedule(event_handler, self.directory_path, recursive=False)

        # Start observer in separate thread
        self.watchdog_thread = threading.Thread(
            target=self._run_observer,
            name=f"{self.name}_WatchdogThread",
            daemon=True
        )
        self.watchdog_thread.start()
        log.info("%s Directory monitor started", log_id_prefix)

    def _run_observer(self):
        """Run the watchdog observer."""
        if not self.observer:
            return
            
        log_id_prefix = f"{self.log_identifier}[Observer]"
        try:
            log.info("%s Starting file system observer...", log_id_prefix)
            self.observer.start()
            
            # Wait for stop signal
            while not self.stop_signal.is_set() and self.observer.is_alive():
                self.stop_signal.wait(timeout=1)
                
            log.info("%s Observer loop exiting", log_id_prefix)
        except Exception as e:
            log.exception("%s Observer error: %s", log_id_prefix, e)
            self.stop_signal.set()
        finally:
            if self.observer.is_alive():
                self.observer.stop()
            self.observer.join()
            log.info("%s Observer stopped", log_id_prefix)

    def _stop_listener(self) -> None:
        """Stop the directory monitoring listener."""
        log_id_prefix = f"{self.log_identifier}[StopListener]"
        log.info("%s Stopping directory monitor...", log_id_prefix)
        
        if self.observer and self.observer.is_alive():
            log.info("%s Stopping observer...", log_id_prefix)
            self.observer.stop()
        
        if self.watchdog_thread and self.watchdog_thread.is_alive():
            log.info("%s Joining observer thread...", log_id_prefix)
            self.watchdog_thread.join(timeout=5)
            if self.watchdog_thread.is_alive():
                log.warning("%s Observer thread did not join cleanly", log_id_prefix)
        
        log.info("%s Directory monitor stopped", log_id_prefix)

    async def _process_new_file(self, file_path: str):
        """Process a newly detected file."""
        log_id_prefix = f"{self.log_identifier}[ProcessFile:{os.path.basename(file_path)}]"
        log.info("%s Processing new file: %s", log_id_prefix, file_path)
        
        error_context = {
            "file_path": file_path,
            "a2a_session_id": f"dir_monitor-error-{self.generate_uuid()}"
        }

        try:
            # Step 1: Authenticate and enrich user
            user_identity_profile = await self.authenticate_and_enrich_user(file_path)
            if not user_identity_profile:
                log.error("%s Authentication failed for file: %s", log_id_prefix, file_path)
                error_obj = JSONRPCError(code=-32001, message="Authentication failed")
                await self._send_error_to_external(error_context, error_obj)
                return

            # Step 2: Translate external input to A2A format
            target_agent_name, a2a_parts, external_request_context = await self._translate_external_input(
                file_path, user_identity_profile
            )

            if not target_agent_name or not a2a_parts:
                log.error("%s Failed to translate file to A2A task: %s", log_id_prefix, file_path)
                error_obj = JSONRPCError(code=-32002, message="Failed to translate file to A2A task")
                final_error_context = {**error_context, **external_request_context}
                await self._send_error_to_external(final_error_context, error_obj)
                return

            # Step 3: Submit A2A task
            log.info("%s Submitting A2A task for file: %s to agent: %s", 
                    log_id_prefix, file_path, target_agent_name)
            await self.submit_a2a_task(
                target_agent_name=target_agent_name,
                a2a_parts=a2a_parts,
                external_request_context=external_request_context,
                user_identity=user_identity_profile
            )
            log.info("%s A2A task submitted for file: %s", log_id_prefix, file_path)

        except FileNotFoundError:
            log.error("%s File not found during processing: %s", log_id_prefix, file_path)
        except Exception as e:
            log.exception("%s Unexpected error processing file %s: %s", log_id_prefix, file_path, e)
            error_obj = JSONRPCError(code=-32000, message=f"Unexpected error: {e}")
            await self._send_error_to_external(error_context, error_obj)

    async def _extract_initial_claims(self, external_event_data: Any) -> Optional[Dict[str, Any]]:
        """Extract user identity claims from file event."""
        file_path = str(external_event_data)
        log_id_prefix = f"{self.log_identifier}[ExtractClaims:{os.path.basename(file_path)}]"
        
        claims = {
            "id": self.default_user_identity_id,
            "source": "dir_monitor",
            "file_path": file_path
        }
        log.debug("%s Extracted claims for file %s: %s", log_id_prefix, file_path, claims)
        return claims

    async def _translate_external_input(
        self, external_event_data: Any, authenticated_user_identity: Dict[str, Any]
    ) -> Tuple[Optional[str], List[A2APart], Dict[str, Any]]:
        """Translate file event to A2A task format."""
        file_path = str(external_event_data)
        log_id_prefix = f"{self.log_identifier}[TranslateInput:{os.path.basename(file_path)}]"

        user_id_for_a2a = authenticated_user_identity.get("id", self.default_user_identity_id)
        a2a_session_id = f"dir_monitor-session-{self.generate_uuid()}"
        
        # Prepare external request context
        external_request_context: Dict[str, Any] = {
            "file_path": file_path,
            "user_id_for_a2a": user_id_for_a2a,
            "app_name_for_artifacts": self.gateway_id,
            "user_id_for_artifacts": user_id_for_a2a,
            "a2a_session_id": a2a_session_id,
        }
        a2a_parts: List[A2APart] = []

        try:
            # Check if file exists
            if not os.path.exists(file_path):
                log.error("%s File does not exist: %s", log_id_prefix, file_path)
                raise FileNotFoundError(f"File not found: {file_path}")

            # Read file content
            with open(file_path, "rb") as f:
                content_bytes = f.read()
            
            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type is None:
                mime_type = "application/octet-stream"

            # Save file as artifact
            if not self.shared_artifact_service:
                log.error("%s Artifact service not available for file: %s", 
                         log_id_prefix, os.path.basename(file_path))
                return None, [], external_request_context

            artifact_metadata = {
                "source": "dir_monitor_gateway",
                "original_filename": os.path.basename(file_path),
                "detected_mime_type": mime_type,
                "processing_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }

            log.debug("%s Saving artifact for file: %s", log_id_prefix, file_path)
            save_result = await save_artifact_with_metadata(
                artifact_service=self.shared_artifact_service,
                app_name=self.gateway_id,
                user_id=str(user_id_for_a2a),
                session_id=a2a_session_id,
                filename=os.path.basename(file_path),
                content_bytes=content_bytes,
                mime_type=mime_type,
                metadata_dict=artifact_metadata,
                timestamp=datetime.now(timezone.utc),
            )

            if save_result["status"] not in ["success", "partial_success"]:
                log.error("%s Failed to save file as artifact: %s", 
                         log_id_prefix, save_result.get("message"))
                return None, [], external_request_context

            # Create artifact URI
            data_version = save_result.get("data_version", 0)
            artifact_uri = f"artifact://{self.gateway_id}/{str(user_id_for_a2a)}/{a2a_session_id}/{os.path.basename(file_path)}?version={data_version}"
            
            log.info("%s Saved file as artifact: %s", log_id_prefix, artifact_uri)

            # Create A2A parts
            file_content_obj = FileContent(
                name=os.path.basename(file_path),
                uri=artifact_uri,
                mimeType=mime_type
            )
            a2a_parts.append(FilePart(file=file_content_obj))
            a2a_parts.append(TextPart(
                text=f"Please analyze and summarize the content of: {os.path.basename(file_path)}"
            ))

            log.info("%s Successfully translated file %s into A2A parts", log_id_prefix, file_path)
            return self.target_agent_name, a2a_parts, external_request_context

        except Exception as e:
            log.exception("%s Error translating file %s: %s", log_id_prefix, file_path, e)
            return None, [], external_request_context

    async def _send_final_response_to_external(
        self, external_request_context: Dict[str, Any], task_data: Task
    ) -> None:
        """Handle final response from A2A agent."""
        log_id_prefix = f"{self.log_identifier}[SendFinalResponse]"
        file_path = external_request_context.get("file_path", "Unknown file")
        task_id = task_data.id

        # Extract summary from response
        summary_text = "Summary not available."
        if task_data.status and task_data.status.message and task_data.status.message.parts:
            for part in task_data.status.message.parts:
                if isinstance(part, TextPart):
                    summary_text = part.text
                    break
        
        log.info("%s Task %s completed for file '%s'. Status: %s", 
                log_id_prefix, task_id, os.path.basename(file_path), 
                task_data.status.state if task_data.status else "Unknown")
        log.info("%s Summary: %s", log_id_prefix, summary_text[:200] + "..." if len(summary_text) > 200 else summary_text)

    async def _send_error_to_external(
        self, external_request_context: Dict[str, Any], error_data: JSONRPCError
    ) -> None:
        """Handle errors by moving files to error directory."""
        log_id_prefix = f"{self.log_identifier}[SendError]"
        file_path = external_request_context.get("file_path")
        
        log.error("%s A2A Error for file '%s'. Code: %s, Message: %s",
                 log_id_prefix, 
                 os.path.basename(file_path) if file_path else "Unknown file",
                 error_data.code, error_data.message)

        # Move problematic file to error directory
        if file_path and os.path.exists(file_path):
            try:
                os.makedirs(self.error_directory_path, exist_ok=True)
                base_name = os.path.basename(file_path)
                error_file_path = os.path.join(self.error_directory_path, base_name)
                
                # Handle filename conflicts
                counter = 0
                while os.path.exists(error_file_path):
                    counter += 1
                    name, ext = os.path.splitext(base_name)
                    error_file_path = os.path.join(self.error_directory_path, f"{name}_error_{counter}{ext}")

                shutil.move(file_path, error_file_path)
                log.info("%s Moved problematic file %s to %s", log_id_prefix, file_path, error_file_path)
            except Exception as e:
                log.exception("%s Failed to move file %s to error directory: %s",
                             log_id_prefix, file_path, e)

    async def _send_update_to_external(
        self,
        external_request_context: Dict[str, Any],
        event_data: Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent],
        is_final_chunk_of_update: bool,
    ) -> None:
        """Handle intermediate updates (optional for this gateway)."""
        log_id_prefix = f"{self.log_identifier}[SendUpdate]"
        task_id = event_data.id
        file_path = external_request_context.get("file_path", "Unknown file")
        
        log.debug("%s Received update for task %s (file %s). Updates not processed by this gateway.",
                 log_id_prefix, task_id, os.path.basename(file_path))

    def cleanup(self):
        """Clean up resources."""
        log.info("%s Cleaning up Directory Monitor Gateway Component...", self.log_identifier)
        super().cleanup()
        log.info("%s Directory Monitor Gateway Component cleanup finished.", self.log_identifier)
```

### Step 4: Configure the Gateway

Configure the Gateway (`dir_monitor_config.yaml`)

```yaml
# configs/gateways/dir_monitor_config.yaml
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: "dir_monitor_gateway.log"

!include ../shared_config.yaml

apps:
  - name: dir_monitor_gateway_app
    app_base_path: .
    app_module: src.dir_monitor.app

    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      gateway_id: dir-monitor-gateway
      
      # Artifact service configuration
      artifact_service: *default_artifact_service

      # Authorization service
      authorization_service:
        type: "none"

      # System purpose for A2A context
      system_purpose: >
        This system monitors directories for new files and processes them automatically.
        Analyze and summarize file contents. Always provide useful insights about the files.
        Your external name is Directory Monitor Agent.

      response_format: >
        Responses should be clear, concise, and professionally formatted.
        Provide structured analysis of file contents in Markdown format.

      # Gateway-specific configuration
      directory_path: /path/to/monitor/directory
      error_directory_path: /path/to/error/directory
      target_agent_name: "OrchestratorAgent"
      default_user_identity: "dir_monitor_system"
```

### Step 5: Install Dependencies

Add required dependencies to your project:

```bash
pip install watchdog
```

### Step 6: Run Your Gateway

```bash
sam run configs/gateways/dir_monitor_config.yaml
```

## Advanced Gateway Patterns

### Authentication and Authorization

Gateways can implement sophisticated authentication:

```python
async def _extract_initial_claims(self, external_event_data: Any) -> Optional[Dict[str, Any]]:
    """Extract user claims with API key validation."""
    request = external_event_data.get("request")
    
    # Validate API key
    api_key = request.headers.get("X-API-Key")
    if not api_key or not self._validate_api_key(api_key):
        return None
    
    # Extract user information
    user_id = request.headers.get("X-User-ID", "anonymous")
    
    return {
        "id": user_id,
        "source": "api_gateway",
        "api_key_hash": hashlib.sha256(api_key.encode()).hexdigest()[:8],
        "roles": self._get_user_roles(user_id)
    }
```

### File Handling with Artifacts

For gateways that handle files:

```python
async def _save_file_as_artifact(self, file_content: bytes, filename: str, 
                                mime_type: str, session_id: str) -> Optional[str]:
    """Save file content as artifact and return URI."""
    if not self.shared_artifact_service:
        return None
    
    try:
        save_result = await save_artifact_with_metadata(
            artifact_service=self.shared_artifact_service,
            app_name=self.gateway_id,
            user_id="system",
            session_id=session_id,
            filename=filename,
            content_bytes=file_content,
            mime_type=mime_type,
            metadata_dict={
                "source": "my_gateway",
                "upload_timestamp": datetime.now(timezone.utc).isoformat()
            },
            timestamp=datetime.now(timezone.utc)
        )
        
        if save_result["status"] in ["success", "partial_success"]:
            version = save_result.get("data_version", 0)
            return f"artifact://{self.gateway_id}/system/{session_id}/{filename}?version={version}"
            
    except Exception as e:
        log.error("Failed to save artifact: %s", e)
    
    return None
```

### Streaming Responses

Handle streaming responses from agents:

```python
async def _send_update_to_external(
    self, external_request_context: Dict[str, Any],
    event_data: Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent],
    is_final_chunk_of_update: bool
) -> None:
    """Send streaming updates to external system."""
    if isinstance(event_data, TaskStatusUpdateEvent):
        if event_data.status and event_data.status.message:
            for part in event_data.status.message.parts:
                if isinstance(part, TextPart):
                    # Send partial text to external system
                    await self._send_partial_response(
                        external_request_context,
                        part.text,
                        is_final=is_final_chunk_of_update
                    )
```

### Error Handling and Retry Logic

Implement robust error handling:

```python
async def _process_with_retry(self, data: Any, max_retries: int = 3):
    """Process data with retry logic."""
    for attempt in range(max_retries):
        try:
            return await self._process_data(data)
        except TemporaryError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                log.warning("Attempt %d failed, retrying in %ds: %s", 
                           attempt + 1, wait_time, e)
                await asyncio.sleep(wait_time)
            else:
                raise
        except PermanentError:
            # Don't retry permanent errors
            raise
```


## Best Practices

### 1. Configuration Management
- Use environment variables for sensitive data
- Provide sensible defaults
- Validate configuration at startup

### 2. Error Handling
- Implement comprehensive error handling
- Use appropriate HTTP status codes
- Log errors with sufficient context
- Provide meaningful error messages

### 3. Security
- Validate all external inputs
- Use secure authentication methods
- Implement rate limiting where appropriate
- Store secrets securely (use environment variables)
- Follow principle of least privilege

### 4. Performance
- Use async/await for I/O operations
- Implement connection pooling for external APIs
- Monitor resource usage
- Handle backpressure appropriately

### 5. Monitoring and Logging
- Use structured logging
- Include correlation IDs
- Monitor key metrics (latency, error rates, throughput)
- Set up health checks

## Common Gateway Patterns

### HTTP/REST API Gateway

For HTTP-based integrations:

```python
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer

class HTTPAPIGatewayComponent(BaseGatewayComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = FastAPI()
        self.security = HTTPBearer()
        self._setup_routes()
    
    def _setup_routes(self):
        @self.app.post("/webhook/{endpoint_id}")
        async def webhook_handler(endpoint_id: str, request: Request,
                                token: str = Depends(self.security)):
            # Authenticate request
            user_identity = await self.authenticate_and_enrich_user({
                "token": token,
                "endpoint_id": endpoint_id,
                "request": request
            })
            
            if not user_identity:
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            # Process webhook
            body = await request.json()
            target_agent, parts, context = await self._translate_external_input(
                body, user_identity
            )
            
            task_id = await self.submit_a2a_task(
                target_agent_name=target_agent,
                a2a_parts=parts,
                external_request_context=context,
                user_identity=user_identity
            )
            
            return {"task_id": task_id, "status": "accepted"}
```

### WebSocket Gateway

For real-time bidirectional communication:

```python
import websockets
import json

class WebSocketGatewayComponent(BaseGatewayComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connections = {}
    
    async def _start_listener(self):
        """Start WebSocket server."""
        self.server = await websockets.serve(
            self.handle_websocket,
            self.get_config("websocket_host", "localhost"),
            self.get_config("websocket_port", 8765)
        )
        log.info("%s WebSocket server started", self.log_identifier)
    
    async def handle_websocket(self, websocket, path):
        """Handle WebSocket connections."""
        connection_id = self.generate_uuid()
        self.connections[connection_id] = websocket
        
        try:
            async for message in websocket:
                data = json.loads(message)
                await self.process_websocket_message(connection_id, data)
        except websockets.exceptions.ConnectionClosed:
            log.info("%s WebSocket connection closed: %s", self.log_identifier, connection_id)
        finally:
            self.connections.pop(connection_id, None)
    
    async def process_websocket_message(self, connection_id: str, data: dict):
        """Process incoming WebSocket message."""
        user_identity = await self.authenticate_and_enrich_user({
            "connection_id": connection_id,
            "data": data
        })
        
        if user_identity:
            target_agent, parts, context = await self._translate_external_input(
                data, user_identity
            )
            context["connection_id"] = connection_id
            
            await self.submit_a2a_task(
                target_agent_name=target_agent,
                a2a_parts=parts,
                external_request_context=context,
                user_identity=user_identity
            )
    
    async def _send_final_response_to_external(self, context: Dict[str, Any], task_data: Task):
        """Send response back via WebSocket."""
        connection_id = context.get("connection_id")
        websocket = self.connections.get(connection_id)
        
        if websocket:
            response = {
                "task_id": task_data.id,
                "status": task_data.status.state.value if task_data.status else "unknown",
                "result": self._extract_text_from_task(task_data)
            }
            await websocket.send(json.dumps(response))
```

### Message Queue Gateway

For integration with message queues:

```python
import asyncio
import aio_pika

class MessageQueueGatewayComponent(BaseGatewayComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connection = None
        self.channel = None
    
    async def _start_listener(self):
        """Connect to message queue and start consuming."""
        connection_url = self.get_config("rabbitmq_url")
        queue_name = self.get_config("input_queue_name")
        
        self.connection = await aio_pika.connect_robust(connection_url)
        self.channel = await self.connection.channel()
        
        queue = await self.channel.declare_queue(queue_name, durable=True)
        await queue.consume(self.process_message)
        
        log.info("%s Started consuming from queue: %s", self.log_identifier, queue_name)
    
    async def process_message(self, message: aio_pika.IncomingMessage):
        """Process incoming queue message."""
        async with message.process():
            try:
                data = json.loads(message.body.decode())
                
                user_identity = await self.authenticate_and_enrich_user(data)
                if not user_identity:
                    log.warning("%s Authentication failed for message", self.log_identifier)
                    return
                
                target_agent, parts, context = await self._translate_external_input(
                    data, user_identity
                )
                context["message_id"] = message.message_id
                context["reply_to"] = message.reply_to
                
                await self.submit_a2a_task(
                    target_agent_name=target_agent,
                    a2a_parts=parts,
                    external_request_context=context,
                    user_identity=user_identity
                )
                
            except Exception as e:
                log.exception("%s Error processing message: %s", self.log_identifier, e)
    
    async def _send_final_response_to_external(self, context: Dict[str, Any], task_data: Task):
        """Send response back to reply queue."""
        reply_to = context.get("reply_to")
        if reply_to and self.channel:
            response = {
                "task_id": task_data.id,
                "status": task_data.status.state.value if task_data.status else "unknown",
                "result": self._extract_text_from_task(task_data)
            }
            
            await self.channel.default_exchange.publish(
                aio_pika.Message(json.dumps(response).encode()),
                routing_key=reply_to
            )
```

## Packaging as a Plugin

For distribution and reusability, package your gateway as a plugin:

### 1. Create Plugin Structure

The following structure is created when running the `sam plugin create my-gateway-plugin --type gateway` command:

```
my-gateway-plugin/
├── pyproject.toml
├── README.md
├── src/
│   └── sam_my_gateway/
│       ├── __init__.py
│       ├── app.py
│       ├── component.py
├── config.yaml
└── examples/
    └── my_gateway_example.yaml
```

### 2. Configure `pyproject.toml`

Update the `pyproject.toml` file to include your gateway dependencies:

```toml
...
dependencies = [
    "watchdog>=3.0.0",  # Add your specific dependencies
]
...
```

### 3. Build and Install

```bash
# Build the plugin
sam plugin build

# Install plugin from local wheel file
sam plugin add my-gateway --plugin dist/sam_my_gateway-0.1.0-py3-none-any.whl
```

## Troubleshooting

### Common Issues

#### Gateway Fails to Start
- Check configuration schema validation
- Verify all required parameters are provided
- Ensure external dependencies are installed

#### Tasks Not Reaching Agents
- Verify namespace configuration matches agents
- Check Solace broker connectivity
- Confirm agent names are correct

#### Authentication Failures
- Validate user identity extraction logic
- Check authorization service configuration
- Verify claims format matches expectations

#### File/Artifact Issues
- Ensure artifact service is properly configured
- Check file permissions and paths
- Verify artifact URI construction

### Debugging Tips

1. **Enable Debug Logging**:
   ```yaml
   log:
     stdout_log_level: DEBUG
     log_file_level: DEBUG
   ```

2. **Use Test Agents**:
   Create simple echo agents for testing gateway integration

3. **Monitor Solace Topics**:
   Use Solace monitoring tools to trace message flow

4. **Add Correlation IDs**:
   Include unique identifiers in logs for request tracing
