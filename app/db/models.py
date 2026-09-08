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
    ARRAY,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase
from pgvector.sqlalchemy import Vector

class Base(DeclarativeBase):
    pass

class Item(Base):
    __tablename__ = "items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, default="bottlerekt")
    kind = Column(String, nullable=False)        # 'note' | 'link' | 'transcript'
    context = Column(String, nullable=False)     # 'text' | 'audio' | 'link'
    content = Column(Text, nullable=False)       # the useful text (English translation for voice)
    original = Column(Text, nullable=True)       # raw Marathi transcript (voice only)
    source = Column(String, nullable=False)      # 'whatsapp' | 'extension' | 'esp32' | 'bookmark'
    meta = Column("metadata", JSONB, nullable=False, default=dict)
    
    # RAG & Enrichment fields
    url = Column(Text, nullable=True)
    content_type = Column(String, nullable=False, default="note")
    auto_tags = Column(ARRAY(String), default=list)
    enriched_text = Column(Text, nullable=True)
    enrichment_status = Column(String, nullable=False, default="skipped")
    embedding = Column(Vector(768), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("context IN ('text', 'audio', 'link')", name="chk_context"),
        CheckConstraint("kind IN ('note', 'link', 'transcript')", name="chk_kind"),
        CheckConstraint("source IN ('whatsapp', 'extension', 'esp32', 'bookmark')", name="chk_source"),
        CheckConstraint("content_type IN ('note', 'youtube', 'instagram', 'twitter', 'link')", name="chk_content_type"),
        CheckConstraint("enrichment_status IN ('done', 'skipped', 'failed')", name="chk_enrich_status"),
        Index("idx_items_user_id", "user_id"),
        Index("idx_items_created_at", "created_at"),
        Index("idx_items_kind", "kind"),
        Index("idx_items_source", "source"),
        Index(
            "idx_items_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"}
        ),
        Index(
            "idx_items_trgm",
            text("(content || ' ' || array_to_string(auto_tags, ' ')) gin_trgm_ops"),
            postgresql_using="gin"
        ),
    )
