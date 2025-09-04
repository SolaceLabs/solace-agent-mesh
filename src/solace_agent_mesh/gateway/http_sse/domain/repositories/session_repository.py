from abc import ABC, abstractmethod

from ...shared.types import PaginationInfo, SessionId, UserId
from ..entities.session import Message, Session


class ISessionRepository(ABC):
    @abstractmethod
    def get_by_id(self, session_id: SessionId) -> Session | None:
        pass

    @abstractmethod
    def get_by_user_id(
        self, user_id: UserId, pagination: PaginationInfo | None = None
    ) -> list[Session]:
        pass

    @abstractmethod
    def get_user_session(
        self, session_id: SessionId, user_id: UserId
    ) -> Session | None:
        pass

    @abstractmethod
    def create(self, session: Session) -> Session:
        pass

    @abstractmethod
    def update(self, session: Session) -> Session | None:
        pass

    @abstractmethod
    def delete(self, session_id: SessionId, user_id: UserId) -> bool:
        pass

    @abstractmethod
    def exists(self, session_id: SessionId) -> bool:
        pass


class IMessageRepository(ABC):
    @abstractmethod
    def get_by_session_id(
        self, session_id: SessionId, pagination: PaginationInfo | None = None
    ) -> list[Message]:
        pass

    @abstractmethod
    def create(self, message: Message) -> Message:
        pass

    @abstractmethod
    def delete_by_session_id(self, session_id: SessionId) -> bool:
        pass
