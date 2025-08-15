import httpx
from httpx_sse import connect_sse
from typing import Any, AsyncIterable
from a2a.types import (
    AgentCard,
    CancelTaskRequest,
    CancelTaskResponse,
    GetTaskPushNotificationConfigRequest,
    GetTaskPushNotificationConfigResponse,
    GetTaskRequest,
    GetTaskResponse,
    JSONRPCRequest,
    SendMessageRequest,
    SendMessageResponse,
    SendStreamingMessageRequest,
    SendStreamingMessageResponse,
    SetTaskPushNotificationConfigRequest,
    SetTaskPushNotificationConfigResponse,
)
from ...common.types import A2AClientHTTPError, A2AClientJSONError
import json
from typing import Any, AsyncIterable
import httpx
from httpx_sse import connect_sse


class A2AClient:
    def __init__(self, agent_card: AgentCard = None, url: str = None):
        if agent_card:
            self.url = agent_card.url
        elif url:
            self.url = url
        else:
            raise ValueError("Must provide either agent_card or url")

    async def send_task(self, payload: dict[str, Any]) -> SendMessageResponse:
        request = SendMessageRequest(**payload)
        return SendMessageResponse.model_validate(await self._send_request(request))

    async def send_task_streaming(
        self, payload: dict[str, Any]
    ) -> AsyncIterable[SendStreamingMessageResponse]:
        request = SendStreamingMessageRequest(**payload)
        with httpx.Client(timeout=None) as client:
            with connect_sse(
                client,
                "POST",
                self.url,
                json=request.model_dump(by_alias=True, exclude_none=True),
            ) as event_source:
                try:
                    for sse in event_source.iter_sse():
                        yield SendStreamingMessageResponse.model_validate(
                            json.loads(sse.data)
                        )
                except json.JSONDecodeError as e:
                    raise A2AClientJSONError(str(e)) from e
                except httpx.RequestError as e:
                    raise A2AClientHTTPError(400, str(e)) from e

    async def _send_request(self, request: JSONRPCRequest) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.url,
                    json=request.model_dump(by_alias=True, exclude_none=True),
                    timeout=30,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise A2AClientHTTPError(e.response.status_code, str(e)) from e
            except json.JSONDecodeError as e:
                raise A2AClientJSONError(str(e)) from e

    async def get_task(self, payload: dict[str, Any]) -> GetTaskResponse:
        request = GetTaskRequest(params=payload)
        return GetTaskResponse.model_validate(await self._send_request(request))

    async def cancel_task(self, payload: dict[str, Any]) -> CancelTaskResponse:
        request = CancelTaskRequest(params=payload)
        return CancelTaskResponse.model_validate(await self._send_request(request))

    async def set_task_callback(
        self, payload: dict[str, Any]
    ) -> SetTaskPushNotificationConfigResponse:
        request = SetTaskPushNotificationConfigRequest(params=payload)
        return SetTaskPushNotificationConfigResponse.model_validate(
            await self._send_request(request)
        )

    async def get_task_callback(
        self, payload: dict[str, Any]
    ) -> GetTaskPushNotificationConfigResponse:
        request = GetTaskPushNotificationConfigRequest(params=payload)
        return GetTaskPushNotificationConfigResponse.model_validate(
            await self._send_request(request)
        )
