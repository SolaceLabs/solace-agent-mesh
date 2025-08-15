from abc import ABC, abstractmethod


class PersistenceService(ABC):
    @abstractmethod
    def create_session(self, session_id: str, user_id: str, agent_id: str = None):
        pass

    @abstractmethod
    def get_sessions(self, user_id: str = None):
        pass

    @abstractmethod
    def get_chat_history(self, session_id):
        pass

    @abstractmethod
    def store_chat_message(
        self, session_id: str, message: dict, user_id: str = None, agent_id: str = None
    ):
        pass
