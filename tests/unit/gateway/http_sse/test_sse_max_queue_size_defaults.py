"""Pin the production default of ``sse_max_queue_size`` (1000).

The default lives in two places that MUST agree:

1. ``WebUIBackendApp.SPECIFIC_APP_SCHEMA_PARAMS`` — the schema default applied
   when YAML omits the key.
2. ``WebUIBackendComponent.__init__`` — the runtime fallback in the
   ``self.get_config("sse_max_queue_size", 1000)`` call.

These were bumped from 200 → 1000 as part of the DATAGO-133967 fix to give
per-stream SSE queues enough headroom under high-fan-out tasks. An accidental
revert of EITHER value would silently reintroduce the queue-overflow bug — so
this test pins both.
"""

from __future__ import annotations

import inspect

from solace_agent_mesh.gateway.http_sse.app import WebUIBackendApp
from solace_agent_mesh.gateway.http_sse.component import WebUIBackendComponent


def test_app_schema_default_is_1000():
    schema = {
        param["name"]: param
        for param in WebUIBackendApp.SPECIFIC_APP_SCHEMA_PARAMS
    }
    assert schema["sse_max_queue_size"]["default"] == 1000, (
        "WebUIBackendApp schema default for sse_max_queue_size must be 1000 "
        "to prevent SSE queue overflow under high-fan-out tasks (DATAGO-133967)."
    )


def test_component_runtime_fallback_is_1000():
    """Pin the literal default in component.__init__'s get_config call.

    We use inspect.getsource rather than constructing the component because
    WebUIBackendComponent.__init__ pulls in FastAPI/uvicorn/SAC App/etc. The
    literal-string check is sufficient: the only way this passes is if the
    second positional arg of the get_config call is exactly ``1000``.
    """
    src = inspect.getsource(WebUIBackendComponent.__init__)
    assert 'self.get_config("sse_max_queue_size", 1000)' in src, (
        "Runtime fallback for sse_max_queue_size in WebUIBackendComponent."
        "__init__ must remain 1000 — see DATAGO-133967."
    )
