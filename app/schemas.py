from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class ItemOut(BaseModel):
    id: str
    kind: str
    context: str
    content: str
    original: Optional[str] = None
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict, alias="meta")
    created_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class IngestRequest(BaseModel):
    kind: str           # 'note' | 'link' | 'transcript'
    context: str        # 'text' | 'audio' | 'link'
    content: str
    original: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    id: str
    kind: str
