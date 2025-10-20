"""
Test Static File Server for integration testing of web_request tool.
Serves static test files and supports dynamic response configuration.
"""

import asyncio
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse
from starlette.responses import FileResponse


class TestStaticFileServer:
    """
    A lightweight HTTP server for serving static test files during integration tests.
    
    Provides:
    - Static file serving from a test data directory
    - Dynamic response configuration for testing edge cases
    - Request capture for test assertions
    - Health check endpoint
    """

    def __init__(
        self, 
        host: str = "127.0.0.1", 
        port: int = 8089,
        content_dir: Optional[str] = None
    ):
        self.host = host
        self.port = port
        
        # Determine content directory
        if content_dir is None:
            # Default to test_data/web_content relative to this file
            pkg_dir = Path(__file__).parent.parent
            self.content_dir = pkg_dir / "test_data" / "web_content"
        else:
            self.content_dir = Path(content_dir)
        
        self.content_dir.mkdir(parents=True, exist_ok=True)
        
        # Server state
        self._uvicorn_server: Optional[uvicorn.Server] = None
        self._server_thread: Optional[threading.Thread] = None
        self._app = FastAPI()
        
        # Request capture
        self.captured_requests: List[Dict[str, Any]] = []
        
        # Dynamic response configuration
        self._configured_responses: Dict[str, Dict[str, Any]] = {}
        self._response_lock = threading.Lock()
        
        # Setup logger
        self._setup_logger()
        
        # Setup routes
        self._setup_routes()
        
        self.logger.info(
            f"TestStaticFileServer initialized. Content dir: {self.content_dir}"
        )

    def _setup_logger(self):
        """Sets up a dedicated logger for the TestStaticFileServer."""
        self.logger = logging.getLogger("TestStaticFileServer")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Add file handler
        log_file_path = os.path.join(os.getcwd(), "test_static_file_server.log")
        file_handler = logging.FileHandler(log_file_path, mode="a")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        self.logger.addHandler(file_handler)
        self.logger.info(
            f"TestStaticFileServer logger initialized. Logging to: {log_file_path}"
        )

    def _setup_routes(self):
        """Sets up FastAPI routes."""
        
        @self._app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return JSONResponse({"status": "ok"})
        
        @self._app.post("/{path:path}")
        async def handle_post(path: str, request: Request):
            """Handles POST requests."""
            # Capture request
            body = await request.body()
            self.captured_requests.append({
                "path": f"/{path}",
                "method": "POST",
                "headers": dict(request.headers),
                "body": body.decode("utf-8", errors="replace"),
                "timestamp": time.time(),
            })
            
            self.logger.debug(f"POST request for: /{path}")
            
            # Check for configured response
            with self._response_lock:
                if f"/{path}" in self._configured_responses:
                    config = self._configured_responses[f"/{path}"]
                    self.logger.info(
                        f"Serving configured POST response for /{path} "
                        f"(status: {config['status_code']})"
                    )
                    
                    return Response(
                        content=config["content"],
                        status_code=config["status_code"],
                        media_type=config.get("content_type", "application/json"),
                    )
            
            # Default POST response (simulating a typical REST API)
            self.logger.info(f"Serving default POST response for /{path}")
            return JSONResponse(
                status_code=201,
                content={
                    "id": 101,
                    "created": True,
                    "message": "Resource created successfully"
                }
            )
        
        @self._app.get("/{filename:path}")
        async def serve_file(filename: str, request: Request):
            """Serves static files or configured responses."""
            # Capture request
            self.captured_requests.append({
                "path": f"/{filename}",
                "method": request.method,
                "headers": dict(request.headers),
                "timestamp": time.time(),
            })
            
            self.logger.debug(f"Request for: /{filename}")
            
            # Check for configured response
            with self._response_lock:
                if f"/{filename}" in self._configured_responses:
                    config = self._configured_responses[f"/{filename}"]
                    self.logger.info(
                        f"Serving configured response for /{filename} "
                        f"(status: {config['status_code']})"
                    )
                    
                    return Response(
                        content=config["content"],
                        status_code=config["status_code"],
                        media_type=config.get("content_type", "application/octet-stream"),
                    )
            
            # Serve static file
            file_path = self.content_dir / filename
            
            if not file_path.exists():
                self.logger.warning(f"File not found: {file_path}")
                return JSONResponse(
                    status_code=404,
                    content={"error": "File not found", "path": filename}
                )
            
            # Determine content type from extension
            content_type = self._get_content_type(file_path)
            
            self.logger.info(
                f"Serving file: {filename} (type: {content_type})"
            )
            
            return FileResponse(
                path=file_path,
                media_type=content_type,
            )

    def _get_content_type(self, file_path: Path) -> str:
        """Determines content type from file extension."""
        extension = file_path.suffix.lower()
        
        content_types = {
            ".json": "application/json",
            ".html": "text/html",
            ".htm": "text/html",
            ".txt": "text/plain",
            ".xml": "application/xml",
            ".csv": "text/csv",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".pdf": "application/pdf",
            ".zip": "application/zip",
        }
        
        return content_types.get(extension, "application/octet-stream")

    @property
    def url(self) -> str:
        """Returns the base URL of the running server."""
        return f"http://{self.host}:{self.port}"

    @property
    def started(self) -> bool:
        """Checks if the uvicorn server instance is started."""
        return self._uvicorn_server is not None and self._uvicorn_server.started

    def start(self):
        """Starts the FastAPI server in a separate thread."""
        if self._server_thread is not None and self._server_thread.is_alive():
            self.logger.warning("TestStaticFileServer is already running.")
            return

        config = uvicorn.Config(
            self._app, host=self.host, port=self.port, log_level="warning"
        )
        self._uvicorn_server = uvicorn.Server(config)

        async def async_serve_wrapper():
            """Coroutine to run the server's serve() method."""
            try:
                if self._uvicorn_server:
                    await self._uvicorn_server.serve()
            except asyncio.CancelledError:
                self.logger.info("Server.serve() task was cancelled.")
            except Exception as e:
                self.logger.error(f"Error during server.serve(): {e}", exc_info=True)

        def run_server_in_new_loop():
            """Target function for the server thread."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(async_serve_wrapper())
            except KeyboardInterrupt:
                self.logger.info("KeyboardInterrupt in server thread.")
            finally:
                try:
                    all_tasks = asyncio.all_tasks(loop)
                    if all_tasks:
                        for task in all_tasks:
                            task.cancel()
                        loop.run_until_complete(
                            asyncio.gather(*all_tasks, return_exceptions=True)
                        )
                    if hasattr(loop, "shutdown_asyncgens"):
                        loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception as e:
                    self.logger.error(
                        f"Error during loop shutdown: {e}", exc_info=True
                    )
                finally:
                    loop.close()
                    self.logger.info("Event loop in server thread closed.")

        self._server_thread = threading.Thread(
            target=run_server_in_new_loop, daemon=True
        )
        self._server_thread.start()

        self.logger.info(f"TestStaticFileServer starting on {self.url}...")

    def stop(self):
        """Stops the FastAPI server."""
        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True

        if self._server_thread and self._server_thread.is_alive():
            self.logger.info("TestStaticFileServer stopping, joining thread...")
            self._server_thread.join(timeout=5.0)
            if self._server_thread.is_alive():
                self.logger.warning("Server thread did not exit cleanly.")
        
        self._server_thread = None
        self._uvicorn_server = None
        self.logger.info("TestStaticFileServer stopped.")

    def configure_response(
        self,
        path: str,
        status_code: int,
        content: bytes,
        content_type: str = "application/octet-stream"
    ) -> None:
        """
        Configures a dynamic response for a specific path.
        
        Args:
            path: The path to configure (e.g., "/custom.json")
            status_code: HTTP status code to return
            content: Response content as bytes
            content_type: MIME type of the content
        """
        with self._response_lock:
            self._configured_responses[path] = {
                "status_code": status_code,
                "content": content,
                "content_type": content_type,
            }
        
        self.logger.info(
            f"Configured response for {path}: status={status_code}, "
            f"type={content_type}, size={len(content)} bytes"
        )

    def configure_error_response(self, path: str, status_code: int) -> None:
        """
        Configures an error response for a specific path.
        
        Args:
            path: The path to configure
            status_code: HTTP error status code (e.g., 404, 500)
        """
        error_content = {
            "error": f"HTTP {status_code}",
            "path": path,
        }
        
        self.configure_response(
            path=path,
            status_code=status_code,
            content=str(error_content).encode("utf-8"),
            content_type="application/json"
        )

    def clear_configured_responses(self) -> None:
        """Clears all configured responses."""
        with self._response_lock:
            count = len(self._configured_responses)
            self._configured_responses.clear()
        
        if count > 0:
            self.logger.debug(f"Cleared {count} configured responses.")

    def get_file_url(self, filename: str) -> str:
        """
        Returns the full URL for a file.
        
        Args:
            filename: Name of the file (e.g., "sample.json")
            
        Returns:
            Full URL to the file
        """
        return f"{self.url}/{filename}"

    def get_captured_requests(self) -> List[Dict[str, Any]]:
        """Returns all captured requests."""
        return self.captured_requests.copy()

    def clear_captured_requests(self) -> None:
        """Clears captured requests."""
        count = len(self.captured_requests)
        self.captured_requests.clear()
        
        if count > 0:
            self.logger.debug(f"Cleared {count} captured requests.")
