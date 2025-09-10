from abc import ABC, abstractmethod

from ...shared.types import PaginationInfo, SessionId, UserId
from ..entities.session import Message, Session


class ISessionRepository(ABC):
    @abstractmethod
    def find_by_user(
        self, user_id: UserId, pagination: PaginationInfo | None = None
    ) -> list[Session]:
        pass

    @abstractmethod
    def find_user_session(
        self, session_id: SessionId, user_id: UserId
    ) -> Session | None:
        pass

    @abstractmethod
    def save(self, session: Session) -> Session:
        pass

    @abstractmethod
    def delete(self, session_id: SessionId, user_id: UserId) -> bool:
        pass

    @abstractmethod
    def find_user_session_with_messages(
        self, session_id: SessionId, user_id: UserId, pagination: PaginationInfo | None = None
    ) -> tuple[Session, list[Message]] | None:
        pass


class IMessageRepository(ABC):
    @abstractmethod
    def find_by_session(
        self, session_id: SessionId, pagination: PaginationInfo | None = None
    ) -> list[Message]:
        pass

    @abstractmethod
    def save(self, message: Message) -> Message:
        pass

    @abstractmethod
    def delete_by_session(self, session_id: SessionId) -> bool:
        pass
