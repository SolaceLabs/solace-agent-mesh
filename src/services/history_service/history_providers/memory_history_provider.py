"""
Memory history provider
"""

from .base_history_provider import BaseHistoryProvider


class MemoryHistoryProvider(BaseHistoryProvider):
    """
    A history provider that stores history in memory.
    """

    def __init__(self, config=None):
        super().__init__(config)
        self.history = {}

    def store_session(self, session_id, data):
        if session_id not in self.history:
            self.history[session_id] = {}
        
        self.history[session_id].update(data)

    def get_session(self, session_id):
        if session_id not in self.history:
            return {}
        return self.history[session_id]

    def get_all_sessions(self) -> list[str]:
        return list(self.history.keys())

    def delete_session(self, session_id):
        if session_id in self.history:
            del self.history[session_id]