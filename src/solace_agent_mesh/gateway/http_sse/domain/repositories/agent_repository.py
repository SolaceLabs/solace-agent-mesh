from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from ..entities.agent import Agent


class IAgentRepository(ABC):
    @abstractmethod
    def create(self, agent: Agent) -> Agent:
        pass

    @abstractmethod
    def get_by_id(self, agent_id: UUID) -> Agent | None:
        pass

    @abstractmethod
    def get_all(self) -> List[Agent]:
        pass

    @abstractmethod
    def update(self, agent: Agent) -> Agent:
        pass

    @abstractmethod
    def delete(self, agent_id: UUID) -> bool:
        pass
