from pydantic import BaseModel
from typing import List
from uuid import UUID
from datetime import datetime

from ....domain.entities.agent import Agent


class AgentCardResponse(BaseModel):
    id: UUID
    description: str
    default_input_modes: List[str]
    default_output_modes: List[str]

class AgentResponse(BaseModel):
    id: UUID
    display_name: str
    prompt: str
    created_at: datetime
    updated_at: datetime
    agent_card: AgentCardResponse

    @classmethod
    def from_entity(cls, agent: Agent) -> "AgentResponse":
        return cls(
            id=agent.id,
            display_name=agent.display_name,
            prompt=agent.prompt,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            agent_card=AgentCardResponse(
                id=agent.agent_card.id,
                description=agent.agent_card.description,
                default_input_modes=agent.agent_card.default_input_modes,
                default_output_modes=agent.agent_card.default_output_modes,
            ),
        )
