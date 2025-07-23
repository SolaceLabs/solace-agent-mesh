import asyncio
import httpx
import os
import json
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal, Tuple, IO


class SAMClientError(Exception):
    """Base exception for the SAM REST Client."""
    pass

class SAMTaskTimeoutError(SAMClientError):
    """Raised when a task polling exceeds the specified timeout."""
    pass

class SAMTaskFailedError(SAMClientError):
    """Raised when the agent returns a final error state for a task."""
    def __init__(self, message: str, error_details: Dict[str, Any]):
        super().__init__(message)
        self.error_details = error_details


class TaskIdResponse(BaseModel):
    taskId: str

class ArtifactInfo(BaseModel):
    name: Optional[str] = None
    mime_type: Optional[str] = Field(default=None, alias="mimeType")
    size: Optional[int] = None
    version: Optional[int] = None
    created: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class A2AError(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None

class TaskResult(BaseModel):
    id: str
    sessionId: Optional[str] = None
    status: Dict[str, Any]
    artifacts: List[ArtifactInfo] = []
    result: Optional[Any] = None
    error: Optional[A2AError] = None


class SAMArtifact:
    """A helper class representing a single artifact returned by a task."""
    def __init__(self, artifact_info: ArtifactInfo, client: 'SAMRestClient', session_id: str):
        self._info = artifact_info
        self._client = client
        self._session_id = session_id

    @property
    def name(self) -> Optional[str]:
        return self._info.name

    @property
    def mime_type(self) -> Optional[str]:
        return self._info.mime_type

    @property
    def size(self) -> Optional[int]:
        return self._info.size

    async def get_content(self, version: Optional[int] = None) -> bytes:
        """
        Downloads the artifact content.

        Args:
            version: The specific version number to download. If None, downloads the latest version.

        Returns:
            The artifact content as bytes.
        """
        params = {"session_id": self._session_id}
        if version is None:
            relative_url = f"/api/v2/artifacts/{self.name}"
        else:
            relative_url = f"/api/v2/artifacts/{self.name}/versions/{version}"

        return await self._client._download_artifact(relative_url, params)

    async def save_to_disk(self, path: str = "."):
        """Saves the artifact to a local file."""
        if not self.name:
            raise SAMClientError("Cannot save artifact as it has no name.")
        content = await self.get_content()
        file_path = os.path.join(path, self.name)
        with open(file_path, "wb") as f:
            f.write(content)

class SAMResult:
    """A helper class that wraps the final task result for easier access."""
    def __init__(self, task_data: TaskResult, client: 'SAMRestClient'):
        self._data = task_data
        self._client = client
        self.session_id = self._data.sessionId

    def is_success(self) -> bool:
        """Returns True if the task completed successfully."""
        return self._data.error is None

    def get_text(self) -> str:
        """Returns the combined text from all text parts in the result."""
        if not self.is_success() or not self._data.status.get("message"):
            return ""
        
        text_parts = [
            part.get("text", "")
            for part in self._data.status["message"].get("parts", [])
            if part.get("type") == "text"
        ]
        return "".join(text_parts)

    def get_artifacts(self) -> List[SAMArtifact]:
        """Returns a list of artifact helpers for downloading content."""
        if not self.session_id:
            return []
        return [SAMArtifact(info, self._client, self.session_id) for info in self._data.artifacts]

    @property
    def raw_result(self) -> Dict[str, Any]:
        """Returns the raw dictionary of the task result."""
        return self._data.model_dump(by_alias=True)


class SAMRestClient:
    """
    An asynchronous client for the Solace Agent Mesh (SAM) REST API Gateway.
    """
    def __init__(self, base_url: str, auth_token: Optional[str] = None, log_file_handle: Optional[IO] = None):
        if not base_url:
            raise ValueError("base_url must be provided.")
        
        self.base_url = base_url.rstrip('/')
        self._log_file_handle = log_file_handle
        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        
        self._client = httpx.AsyncClient(headers=headers, timeout=30.0)

    async def invoke(
        self,
        agent_name: str,
        prompt: str,
        files: Optional[List[Tuple[str, IO]]] = None,
        mode: Literal['async', 'sync'] = 'async',
        timeout_seconds: int = 120,
        polling_interval_seconds: int = 2,
    ) -> SAMResult:
        """
        Submits a task to an agent and retrieves the result.

        Args:
            agent_name: The name of the target agent.
            prompt: The text prompt for the agent.
            files: A list of tuples, where each tuple is (filename, file-like-object).
            mode: 'async' (default) uses the v2 API with polling. 'sync' uses the v1 blocking API.
            timeout_seconds: Total time to wait for a result in async mode.
            polling_interval_seconds: How often to poll for results in async mode.

        Returns:
            A SAMResult object containing the final task details.
        """
        if mode == 'sync':
            return await self._invoke_sync(agent_name, prompt, files)
        elif mode == 'async':
            return await self._invoke_async(agent_name, prompt, files, timeout_seconds, polling_interval_seconds)
        else:
            raise ValueError("mode must be either 'async' or 'sync'")

    async def _invoke_sync(self, agent_name: str, prompt: str, files: Optional[List[Tuple[str, IO]]]) -> SAMResult:
        """Handles the legacy v1 synchronous invocation."""
        url = f"{self.base_url}/api/v1/invoke"
        data = {"agent_name": agent_name, "prompt": prompt}
        
        file_list = [("files", (f[0], f[1])) for f in files] if files else None

        try:
            response = await self._client.post(url, data=data, files=file_list)

            if self._log_file_handle:
                try:
                    log_content = json.dumps(response.json(), indent=2)
                except json.JSONDecodeError:
                    log_content = response.text
                self._log_file_handle.write(f"--- SYNC RESPONSE ---\nURL: {url}\nSTATUS: {response.status_code}\n\n{log_content}\n\n")
                self._log_file_handle.flush()

            response.raise_for_status()
            task_data = TaskResult(**response.json())
            
            if task_data.error:
                raise SAMTaskFailedError(task_data.error.message, task_data.error.model_dump())
            
            return SAMResult(task_data, self)
        except httpx.HTTPStatusError as e:
            raise SAMClientError(f"HTTP Error: {e.response.status_code} - {e.response.text}") from e

    async def _invoke_async(self, agent_name: str, prompt: str, files: Optional[List[Tuple[str, IO]]], timeout: int, poll_interval: int) -> SAMResult:
        """Handles the modern v2 asynchronous invocation with polling."""
        submit_url = f"{self.base_url}/api/v2/tasks"
        data = {"agent_name": agent_name, "prompt": prompt}
        file_list = [("files", (f[0], f[1])) for f in files] if files else None

        try:
            submit_response = await self._client.post(submit_url, data=data, files=file_list)

            if self._log_file_handle:
                try:
                    log_content = json.dumps(submit_response.json(), indent=2)
                except json.JSONDecodeError:
                    log_content = submit_response.text
                self._log_file_handle.write(f"--- ASYNC SUBMIT RESPONSE ---\nURL: {submit_url}\nSTATUS: {submit_response.status_code}\n\n{log_content}\n\n")
                self._log_file_handle.flush()

            if submit_response.status_code != 202:
                raise SAMClientError(f"Failed to submit task. Status: {submit_response.status_code}, Body: {submit_response.text}")
            
            task_id_resp = TaskIdResponse(**submit_response.json())
            task_id = task_id_resp.taskId
        except httpx.HTTPStatusError as e:
            raise SAMClientError(f"HTTP Error on task submission: {e.response.status_code} - {e.response.text}") from e

        poll_url = f"{self.base_url}/api/v2/tasks/{task_id}"
        try:
            async with asyncio.timeout(timeout):
                while True:
                    poll_response = await self._client.get(poll_url)
                    
                    if self._log_file_handle:
                        try:
                            log_content = json.dumps(poll_response.json(), indent=2)
                        except json.JSONDecodeError:
                            log_content = poll_response.text
                        self._log_file_handle.write(f"--- ASYNC POLL RESPONSE ---\nURL: {poll_url}\nSTATUS: {poll_response.status_code}\n\n{log_content}\n\n")
                        self._log_file_handle.flush()

                    if poll_response.status_code == 200:
                        task_data = TaskResult(**poll_response.json())
                        if task_data.error:
                            raise SAMTaskFailedError(task_data.error.message, task_data.error.model_dump())
                        return SAMResult(task_data, self)
                    
                    elif poll_response.status_code != 202:
                        raise SAMClientError(f"Polling failed. Status: {poll_response.status_code}, Body: {poll_response.text}")
                    
                    await asyncio.sleep(poll_interval)
        except asyncio.TimeoutError:
            raise SAMTaskTimeoutError(f"Task {task_id} did not complete within {timeout} seconds.") from None

    async def _download_artifact(self, relative_url: str, params: Dict[str, Any]) -> bytes:
        """Internal helper to download artifact content from a relative URL with query params."""
        if not relative_url.startswith('/'):
            raise ValueError("Artifact URL must be a relative path starting with '/'")

        download_url = f"{self.base_url}{relative_url}"
        response = await self._client.get(download_url, params=params)
        response.raise_for_status()
        return response.content

    async def close(self):
        """Closes the underlying HTTP client."""
        await self._client.aclose()
