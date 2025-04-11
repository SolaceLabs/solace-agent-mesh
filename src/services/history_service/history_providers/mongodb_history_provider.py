"""
MongoDB-based history provider for storing session data.
"""
from .base_history_provider import BaseHistoryProvider

class MongoDBHistoryProvider(BaseHistoryProvider):
    """
    A MongoDB-based history provider for storing session data.
    """
    def __init__(self, config=None):
        super().__init__(config)

        try:
            from pymongo import MongoClient
        except ImportError:
            raise ImportError("Please install the pymongo package to use the MongoDBHistoryProvider.\n\t$ pip install pymongo")
        
        if not self.config.get("mongodb_uri"):
            raise ValueError("Missing required configuration for MongoDBHistoryProvider, Missing 'mongodb_uri' in 'store_config'.")
        
        
        self.client = MongoClient(self.config.get("mongodb_uri"))
        self.db = self.client[self.config.get("mongodb_db", "history_db")]
        self.collection = self.db[self.config.get("mongodb_collection", "sessions")]
    
    def _get_key(self, session_id):
        """
        Generate a document identifier for a session.

        :param session_id: The session identifier.
        :return: The session ID as the primary key.
        """
        return {"_id": session_id}
    
    def store_session(self, session_id: str, data: dict):
        """
        Store the session metadata.

        :param session_id: The session identifier.
        :param data: The session data to be stored.
        """
        self.collection.update_one(self._get_key(session_id), {"$set": {"data": data}}, upsert=True)
    
    def get_session(self, session_id: str)->dict:
        """
        Retrieve the session.

        :param session_id: The session identifier.
        :return: The session metadata as a dictionary.
        """
        document = self.collection.find_one(self._get_key(session_id))
        return document.get("data") if document else {}
    
    def get_all_sessions(self) -> list[str]:
        """
        Retrieve all session identifiers.
        """
        return [doc["_id"] for doc in self.collection.find({}, {"_id": 1})]
    
    def delete_session(self, session_id: str):
        """
        Delete the session.

        :param session_id: The session identifier.
        """
        self.collection.delete_one(self._get_key(session_id))
