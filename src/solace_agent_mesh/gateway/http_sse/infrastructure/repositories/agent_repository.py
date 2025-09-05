from typing import List
from uuid import UUID

from ...domain.entities.agent import Agent, AgentCard
from ...domain.repositories.agent_repository import IAgentRepository
from ..persistence.database_service import DatabaseService
from ..persistence.models import AgentModel, AgentCardModel


class AgentRepository(IAgentRepository):
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service

    def create(self, agent: Agent) -> Agent:
        with self.db_service.session_scope() as session:
            agent_card_model = AgentCardModel(
                id=agent.agent_card.id,
                description=agent.agent_card.description,
                default_input_modes=agent.agent_card.default_input_modes,
                default_output_modes=agent.agent_card.default_output_modes,
            )
            agent_model = AgentModel(
                id=agent.id,
                display_name=agent.display_name,
                prompt=agent.prompt,
                agent_card=agent_card_model,
            )
            session.add(agent_model)
            session.flush()
            session.refresh(agent_model)
            return self._to_entity(agent_model)

    def get_by_id(self, agent_id: UUID) -> Agent | None:
        with self.db_service.read_only_session() as session:
            agent_model = session.query(AgentModel).filter(AgentModel.id == agent_id).first()
            if agent_model:
                return self._to_entity(agent_model)
            return None

    def get_all(self) -> List[Agent]:
        with self.db_service.read_only_session() as session:
            agent_models = session.query(AgentModel).all()
            return [self._to_entity(model) for model in agent_models]

    def update(self, agent: Agent) -> Agent:
        with self.db_service.session_scope() as session:
            agent_model = session.query(AgentModel).filter(AgentModel.id == agent.id).first()
            if agent_model:
                agent_model.display_name = agent.display_name
                agent_model.prompt = agent.prompt
                if agent_model.agent_card:
                    agent_model.agent_card.description = agent.agent_card.description
                    agent_model.agent_card.default_input_modes = agent.agent_card.default_input_modes
                    agent_model.agent_card.default_output_modes = agent.agent_card.default_output_modes
                session.flush()
                session.refresh(agent_model)
                return self._to_entity(agent_model)
            return None

    def delete(self, agent_id: UUID) -> bool:
        with self.db_service.session_scope() as session:
            agent_model = session.query(AgentModel).filter(AgentModel.id == agent_id).first()
            if agent_model:
                session.delete(agent_model)
                return True
            return False

    def _to_entity(self, model: AgentModel) -> Agent:
        return Agent(
            id=model.id,
            display_name=model.display_name,
            prompt=model.prompt,
            created_at=model.created_at,
            updated_at=model.updated_at,
            agent_card=AgentCard(
                id=model.agent_card.id,
                description=model.agent_card.description,
                default_input_modes=model.agent_card.default_input_modes,
                default_output_modes=model.agent_card.default_output_modes,
            ),
        )
