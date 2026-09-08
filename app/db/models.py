import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Index,
    CheckConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    kind = Column(String, nullable=False)        # 'note' | 'link' | 'transcript'
    context = Column(String, nullable=False)     # 'text' | 'audio' | 'link'
    content = Column(Text, nullable=False)       # the useful text (English translation for voice)
    original = Column(Text, nullable=True)       # raw Marathi transcript (voice only)
    source = Column(String, nullable=False)      # 'whatsapp' | 'extension' | 'esp32' | 'bookmark'
    meta = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("context IN ('text', 'audio', 'link')", name="chk_context"),
        CheckConstraint("kind IN ('note', 'link', 'transcript')", name="chk_kind"),
        CheckConstraint("source IN ('whatsapp', 'extension', 'esp32', 'bookmark')", name="chk_source"),
        Index("idx_items_created_at", "created_at"),
        Index("idx_items_kind", "kind"),
        Index("idx_items_source", "source"),
    )
