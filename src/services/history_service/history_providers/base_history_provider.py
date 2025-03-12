from abc import ABC, abstractmethod
from typing import Union

class BaseHistoryProvider(ABC):

    def __init__(self, config=None):
        self.config = config
        self.max_turns = self.config.get("max_turns")
        self.max_characters = self.config.get("max_characters")
        self.enforce_alternate_message_roles = self.config.get("enforce_alternate_message_roles")

    @abstractmethod
    def store_history(self, session_id: str, role: str, content: Union[str, dict]):
        """
        Store a new entry in the history.

        :param session_id: The session identifier.
        :param role: The role of the entry to be stored in the history.
        :param content: The content of the entry to be stored in the history.
        """
        raise NotImplementedError("Method not implemented")

    @abstractmethod
    def get_history(self, session_id: str):
        """
        Retrieve the entire history.

        :param session_id: The session identifier.
        :return: The complete history.
        """
        raise NotImplementedError("Method not implemented")

    @abstractmethod
    def store_file(self, session_id: str, file: dict):
        """
        Store a file in the history.

        :param session_id: The session identifier.
        :param file: The file metadata to be stored in the history.
        """
        raise NotImplementedError("Method not implemented")

    @abstractmethod
    def get_files(self, session_id: str):
        """
        Retrieve the files for a session.

        :param session_id: The session identifier.
        :return: The files for the session.
        """
        raise NotImplementedError("Method not implemented")
    
    @abstractmethod
    def get_session_meta(self, session_id: str):
        """
        Retrieve the session metadata.

        :param session_id: The session identifier.
        :return: The session metadata.
        """
        raise NotImplementedError("Method not implemented")

    @abstractmethod
    def clear_history(self, session_id: str, keep_levels=0, clear_files=True):
        """
        Clear the history and files, optionally keeping a specified number of recent entries.

        :param session_id: The session identifier.
        :param keep_levels: Number of most recent history entries to keep. Default is 0 (clear all).
        :param clear_files: Whether to clear associated files. Default is True.
        """
        raise NotImplementedError("Method not implemented")

    @abstractmethod
    def get_all_sessions(self) -> list[str]:
        """
        Retrieve all session identifiers.
        """
        raise NotImplementedError("Method not implemented")
