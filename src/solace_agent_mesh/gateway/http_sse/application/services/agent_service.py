from typing import List
from uuid import UUID, uuid4

from ...domain.entities.agent import Agent, AgentCard
from ...domain.repositories.agent_repository import IAgentRepository


class AgentService:
    def __init__(self, agent_repository: IAgentRepository):
        self.agent_repository = agent_repository

    def create_agent(
        self,
        display_name: str,
        prompt: str,
        agent_card_data: dict,
    ) -> Agent:
        agent_card = AgentCard(
            id=uuid4(),
            description=agent_card_data.get("description"),
            default_input_modes=agent_card_data.get("default_input_modes", ["text"]),
            default_output_modes=agent_card_data.get("default_output_modes", ["text"]),
        )
        agent = Agent(
            id=uuid4(),
            display_name=display_name,
            prompt=prompt,
            agent_card=agent_card,
        )
        return self.agent_repository.create(agent)

    def get_agent(self, agent_id: UUID) -> Agent | None:
        return self.agent_repository.get_by_id(agent_id)

    def get_all_agents(self) -> List[Agent]:
        return self.agent_repository.get_all()

    def update_agent(
        self,
        agent_id: UUID,
        display_name: str | None = None,
        prompt: str | None = None,
        agent_card_data: dict | None = None,
    ) -> Agent | None:
        agent = self.agent_repository.get_by_id(agent_id)
        if agent:
            if display_name is not None:
                agent.display_name = display_name
            if prompt is not None:
                agent.prompt = prompt
            if agent_card_data:
                if "description" in agent_card_data:
                    agent.agent_card.description = agent_card_data.get("description")
                if "default_input_modes" in agent_card_data:
                    agent.agent_card.default_input_modes = agent_card_data.get(
                        "default_input_modes"
                    )
                if "default_output_modes" in agent_card_data:
                    agent.agent_card.default_output_modes = agent_card_data.get(
                        "default_output_modes"
                    )
            return self.agent_repository.update(agent)
        return None

    def delete_agent(self, agent_id: UUID) -> bool:
        return self.agent_repository.delete(agent_id)
