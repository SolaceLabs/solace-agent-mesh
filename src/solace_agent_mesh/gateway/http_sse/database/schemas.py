from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class ChatMessageBase(BaseModel):
    message: str
    sender_type: str
    sender_name: str


class ChatMessageCreate(ChatMessageBase):
    pass


class ChatMessage(ChatMessageBase):
    id: str
    session_id: str
    created_at: datetime

    class Config:
        orm_mode = True


class SessionBase(BaseModel):
    name: Optional[str] = None
    agent_id: Optional[str] = None


class SessionCreate(SessionBase):
    user_id: str


class Session(SessionBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessage] = []

    class Config:
        orm_mode = True


