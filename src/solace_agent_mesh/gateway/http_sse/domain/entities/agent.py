from dataclasses import dataclass, field
from datetime import datetime
import uuid

@dataclass
class AgentCard:
    id: uuid.UUID
    description: str
    default_input_modes: list[str]
    default_output_modes: list[str]

@dataclass
class Agent:
    id: uuid.UUID
    display_name: str
    prompt: str
    agent_card: AgentCard
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
