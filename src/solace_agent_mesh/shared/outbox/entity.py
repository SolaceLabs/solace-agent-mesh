from pydantic import BaseModel


class OutboxEventEntity(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    event_type: str
    status: str
    payload: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    next_retry_at: int = 0
    created_time: int
    updated_time: int

    model_config = {"from_attributes": True}
