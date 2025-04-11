import json
import os
from .base_history_provider import BaseHistoryProvider

class FileHistoryProvider(BaseHistoryProvider):
    """
    A simple file-based history provider for storing session data.
    """
    def __init__(self, config=None):
        super().__init__(config)

        if not self.config.get("path"):
            raise ValueError("Missing required configuration for FileHistoryProvider, Missing 'path' in configs.")
        
        self.path = self.config.get("path")

        if not self._exists(self.path):
            os.makedirs(self.path, exist_ok=True)

    def _get_key(self, session_id):
        """
        Generate a file path for a session.

        :param session_id: The session identifier.
        :return: A formatted file path.
        """
        return os.path.join(self.path, f"sessions_{session_id}_history.json")

    def store_session(self, session_id: str, data: dict):
        """
        Store the session metadata.

        :param session_id: The session identifier.
        :param data: The session data to be stored.
        """
        file_path = self._get_key(session_id)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(data))

    def get_session(self, session_id: str)->dict:
        """
        Retrieve the session.

        :param session_id: The session identifier.
        :return: The session metadata as a dictionary.
        """
        file_path = self._get_key(session_id)
        if not self._exists(file_path):
            return {}
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    def get_all_sessions(self) -> list[str]:
        """
        Retrieve all session identifiers.
        """
        return [f[9:-13] for f in os.listdir(self.path) if f.startswith("sessions_") and f.endswith("_history.json")]
    
    def delete_session(self, session_id: str):
        """
        Delete the session.

        :param session_id: The session identifier.
        """
        file_path = self._get_key(session_id)
        if self._exists(file_path):
            os.remove(file_path)

    def _exists(self, path: str):
        return os.path.exists(path)
