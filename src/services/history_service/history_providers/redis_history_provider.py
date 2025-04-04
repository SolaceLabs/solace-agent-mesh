"""
A history provider that stores history in Redis.
"""
import json
from .base_history_provider import BaseHistoryProvider

class RedisHistoryProvider(BaseHistoryProvider):
    """
    A history provider that stores history in Redis.
    """
    def __init__(self, config=None):
        super().__init__(config)
        try:
            import redis
        except ImportError:
            raise ImportError("Please install the redis package to use the RedisHistoryProvider.\n\t$ pip install redis")
        
        self.redis_client = redis.Redis(
            host=self.config.get("redis_host", "localhost"),
            port=self.config.get("redis_port", 6379),
            db=self.config.get("redis_db", 0),
            decode_responses=True  # Ensures string output
        )
    
    def _get_key(self, session_id):
        """
        Generate a Redis key with a specific prefix for a session.

        :param session_id: The session identifier.
        :return: A formatted Redis key string.
        """
        return f"sessions:{session_id}:history"

    def store_session(self, session_id: str, data: dict):
        """
        Store the session metadata.

        :param session_id: The session identifier.
        :param data: The session data to be stored.
        """
        self.redis_client.set(self._get_key(session_id), json.dumps(data))

    def get_session(self, session_id: str)->dict:
        """
        Retrieve the session.

        :param session_id: The session identifier.
        :return: The session metadata as a dictionary.
        """
        data = self.redis_client.get(self._get_key(session_id))
        return json.loads(data) if data else {}

    def get_all_sessions(self) -> list[str]:
        """
        Retrieve all session identifiers.
        """
        keys = self.redis_client.keys("sessions:*:history")
        return [key.split(":")[1] for key in keys]
    
    def delete_session(self, session_id: str):
        """
        Delete the session.

        :param session_id: The session identifier.
        """
        self.redis_client.delete(self._get_key(session_id))