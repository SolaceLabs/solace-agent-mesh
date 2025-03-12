"""This is the definition of responses for the actions of the system."""

from typing import Optional


class RagMatch:

    def __init__(self, text: str, link: str = None, heading: str = None):
        self._text: str = text
        self._link: str = link
        self._heading: str = heading

    @property
    def text(self) -> str:
        return self._text

    @property
    def link(self) -> str:
        return self._link

    @property
    def heading(self) -> str:
        return self._headings

    def to_dict(self) -> dict:
        return {
            "text": self._text,
            "link": self._link,
            "heading": self._heading,
        }


class InlineFile:

    def __init__(self, content: str, name: str, **kwargs):
        if type(content) != str:
            raise ValueError("InlineFile content must be a string")
        self._content: str = content
        self._name: str = name
        self._kwargs: dict = kwargs

    @property
    def content(self) -> str:
        return self._content

    @property
    def name(self) -> str:
        return self._name
    
    @property
    def kwargs(self) -> dict:
        return self._kwargs

    def to_dict(self) -> dict:
        return {
            "data": self._content,
            "name": self._name,
            "file_size": len(self._content.encode()),
            "mime_type": "text/plain",
            **self._kwargs,
        }


class WithContextQuery:

    def __init__(
        self, query: str, context_type: str, context: str = None, since: str = None
    ):
        self._query: str = query
        self._context_type: str = context_type
        self._context: str = context
        self._since: str = since

    @property
    def query(self) -> str:
        return self._query

    @property
    def context(self) -> str:
        return self._context

    @property
    def context_type(self) -> str:
        return self._context_type

    @property
    def since(self) -> dict:
        return self._since

    def to_dict(self) -> dict:
        return {
            "query": self._query,
            "context_type": self._context_type,
            "context": self._context,
            "since": self._since,
        }


class RagResponse:

    def __init__(
        self, data_source: str, matches: list[RagMatch], query: str, prompt: str = None
    ):
        self._data_source: str = data_source
        self._matches: list[RagMatch] = matches
        self._query: str = query
        self._prompt: str = prompt

    @property
    def data_source(self) -> str:
        return self._data_source

    @property
    def matches(self) -> list[RagMatch]:
        return self._matches

    @property
    def query(self) -> str:
        return self._query

    @property
    def prompt(self) -> str:
        return self._prompt

    def to_dict(self) -> dict:
        return {
            "data_source": self._data_source,
            "matches": [match.to_dict() for match in self._matches],
            "query": self._query,
            "prompt": self._prompt,
        }


class AgentStateChange:

    def __init__(self, agent_name: str, new_state: str):
        self._agent_name: str = agent_name
        self._new_state: str = new_state

    @property
    def agent_name(self) -> str:
        return self._agent_name

    @property
    def new_state(self) -> str:
        return self._new_state

    def to_dict(self) -> dict:
        return {"agent_name": self._agent_name, "new_state": self._new_state}


class ErrorInfo:

    def __init__(self, error_message: str):
        self._error_message: str = error_message

    @property
    def error_message(self) -> str:
        return self._error_message

    def __str__(self) -> str:
        return self._error_message

    def to_dict(self) -> dict:
        return {"error_message": self._error_message}


class ActionResponse:

    def __init__(
        self,
        message: any = None,
        files: list[str] = None,
        inline_files: list[InlineFile] = None,
        clear_history: bool = False,
        history_depth_to_keep: int = None,
        error_info: ErrorInfo = None,
        agent_state_change: AgentStateChange = None,
        invoke_model_again: bool = False,
        context_query: WithContextQuery = None,
        is_async: bool = False,
        async_response_id: str = None,
    ):
        # Message to return - this could be a string or a slack blocks message
        self._message: str = message
        # Files to return - this is a list of temporary files to return
        self._files: list[str] = files
        # Inline files to return - this is a list of inline files to return
        self._inline_files: list[InlineFile] = inline_files
        # Clear history - this is a flag to clear the chat history
        self._clear_history: bool = clear_history
        # Clear history but keep depth - this is a flag to clear the chat history but keep
        # the last N messages
        self._history_depth_to_keep: int = history_depth_to_keep
        # Error info - this is a dictionary of error information (error_message)
        self._error_info: ErrorInfo = error_info
        # Agent state change - this is a dictionary of agent state change
        # information (agent_name, new_state)
        self._agent_state_change: AgentStateChange = agent_state_change
        # Invoke model again - this is a flag to indicate if the model should be
        # invoked again with the same input
        self._invoke_model_again: bool = invoke_model_again
        # Context query - this contains the query and context type to be used in the next action
        self._context_query: WithContextQuery = context_query
        # action_list_id - identifier of the action_list that this action response is associated with
        self._action_list_id: str = None
        # action_idx - index of the action in the action_list that this action response is associated with
        self._action_idx: int = None
        # action_name - name of the action that this action response is associated with
        self._action_name: str = None
        # action_params - parameters of the action that this action response is associated with
        self._action_params: dict = None
        # is_async - indicates if this is an async response that will be delivered later
        self._is_async: bool = is_async
        # async_response_id - unique identifier for correlating async responses
        self._async_response_id: str = async_response_id
        # originator - the component that originated the action request
        self._originator: Optional[str] = None

    @property
    def message(self) -> any:
        return self._message

    @message.setter
    def message(self, message: any):
        self._message = message

    @property
    def files(self) -> list[str]:
        return self._files

    @property
    def inline_files(self) -> list[InlineFile]:
        return self._inline_files

    @property
    def clear_history(self) -> bool:
        return self._clear_history

    @property
    def history_depth_to_keep(self) -> int:
        return self._history_depth_to_keep

    @property
    def error_info(self) -> dict:
        return self._error_info

    @property
    def agent_state_change(self) -> AgentStateChange:
        return self._agent_state_change

    @property
    def invoke_model_again(self) -> bool:
        return self._invoke_model_again

    @property
    def context_query(self) -> WithContextQuery:
        return self._context_query

    @property
    def action_list_id(self) -> str:
        return self._action_list_id

    @property
    def action_idx(self) -> int:
        return self._action_idx

    @property
    def action_name(self) -> str:
        return self._action_name

    @property
    def action_params(self) -> dict:
        return self._action_params

    @property
    def originator(self) -> dict:
        return self._originator

    @action_list_id.setter
    def action_list_id(self, action_list_id: str):
        self._action_list_id = action_list_id

    @action_idx.setter
    def action_idx(self, action_idx: int):
        self._action_idx = action_idx

    @action_name.setter
    def action_name(self, action_name: str):
        self._action_name = action_name

    @action_params.setter
    def action_params(self, action_params: dict):
        self._action_params = action_params

    @originator.setter
    def originator(self, originator: str):
        self._originator = originator

    @property
    def is_async(self) -> bool:
        return self._is_async

    @property 
    def async_response_id(self) -> str:
        return self._async_response_id

    def to_dict(self) -> dict:
        response = {}
        if self._message:
            response["message"] = self._message
        if self._is_async:
            response["is_async"] = True
            response["async_response_id"] = self._async_response_id
        if self._files:
            # Files are already dictionary
            response["files"] = self._files
        if self._inline_files:
            # Add to the files list
            response["files"] = response.get("files", []) + [
                inline_file.to_dict() for inline_file in self._inline_files
            ]
        if self._clear_history:
            response["clear_history"] = self._clear_history
        if self._history_depth_to_keep:
            response["history_depth_to_keep"] = self._history_depth_to_keep
        if self._error_info:
            response["error_info"] = self._error_info.to_dict()
        if self._agent_state_change:
            response["agent_state_change"] = self._agent_state_change.to_dict()
        if self._invoke_model_again:
            response["invoke_model_again"] = self._invoke_model_again
        if self._context_query:
            response["context_query"] = self._context_query.to_dict()
        response["action_list_id"] = self._action_list_id
        response["action_idx"] = self._action_idx
        response["action_name"] = self._action_name
        response["action_params"] = self._action_params
        response["originator"] = self._originator
        return response
