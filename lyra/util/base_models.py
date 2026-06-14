from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    text: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str


class StreamRequest(BaseModel):
    text: str
    session_id: Optional[str] = None
