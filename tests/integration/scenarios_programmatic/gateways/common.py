from typing import Any, Dict, List, Optional

def create_llm_response(
    content: Optional[str],
    id_suffix: str,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    finish_reason: str = "stop",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> Dict[str, Any]:
    """
    Creates a standard LLM response structure.

    Args:
        content: The main content of the assistant's message.
        id_suffix: A unique suffix for the response ID.
        tool_calls: An optional list of tool calls.
        finish_reason: The reason the LLM finished, e.g., "stop" or "tool_calls".
        prompt_tokens: The number of prompt tokens.
        completion_tokens: The number of completion tokens.
    """
    message: Dict[str, Any] = {"role": "assistant"}
    if content:
        message["content"] = content
    if tool_calls:
        message["tool_calls"] = tool_calls

    response = {
        "id": f"chatcmpl-test-gateway-{id_suffix}",
        "object": "chat.completion",
        "model": "openai/test-model-sam",
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }
    return response
