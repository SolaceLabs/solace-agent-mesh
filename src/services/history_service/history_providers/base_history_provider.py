from abc import ABC, abstractmethod

class BaseHistoryProvider(ABC):

    def __init__(self, config=None):
        self.config = config or {}
    
    @abstractmethod
    def get_all_sessions(self) -> list[str]:
        """
        Retrieve all session identifiers.
        """
        raise NotImplementedError("Method not implemented")

    @abstractmethod
    def get_session(self, session_id: str)->dict:
        """
        Retrieve the session .

        :param session_id: The session identifier.
        :return: The session metadata.
        """
        raise NotImplementedError("Method not implemented")
    
    @abstractmethod
    def delete_session(self, session_id: str):
        """
        Delete the session.

        :param session_id: The session identifier.
        """
        raise NotImplementedError("Method not implemented")
    
    @abstractmethod
    def store_session(self, session_id: str, data: dict):
        """
        Store the session metadata.

        :param session_id: The session identifier.
        :param data: The session data to be stored.
        """
        raise NotImplementedError("Method not implemented")
    

    def update_session(self, session_id: str, data: dict):
        """
        Update data in the store using the partial data provided.

        :param key: The key to update the data under.
        :param data: The data to update.
        """
        history = self.get_session(session_id).copy()
        history.update(data)
        self.store_session(session_id, history)