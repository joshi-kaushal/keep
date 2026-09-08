import logging
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.db.models import Item
from app.schemas import IngestRequest, IngestResponse
from app.services.enrichment import detect_content_type, enrich_url
from app.services.rag import generate_auto_tags, embed_snippet

logger = logging.getLogger(__name__)
router = APIRouter()


async def process_ingestion(
    body: IngestRequest,
    source: str,
    user_id: str,
    db: Session,
):
    content_type, extracted_url = detect_content_type(body.content)
    enriched_text, enrichment_status = await enrich_url(content_type, extracted_url)
    tags = generate_auto_tags(body.content, enriched_text)
    embedding = embed_snippet(body.content, tags, enriched_text)

    item = Item(
        user_id=user_id,
        kind=body.kind,
        context=body.context,
        content=body.content,
        original=body.original,
        source=source,
        meta=body.metadata,
        url=extracted_url,
        content_type=content_type,
        auto_tags=tags,
        enriched_text=enriched_text,
        enrichment_status=enrichment_status,
        embedding=embedding
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return IngestResponse(id=item.id, kind=item.kind)


@router.post("/ingest/extension", response_model=IngestResponse)
async def ingest_extension(
    body: IngestRequest,
    x_extension_token: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if x_extension_token != settings.extension_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    uid = x_user_id or settings.default_user_id
    return await process_ingestion(body, "extension", uid, db)


@router.post("/ingest/bookmark", response_model=IngestResponse)
async def ingest_bookmark(
    body: IngestRequest,
    x_extension_token: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if x_extension_token != settings.extension_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    uid = x_user_id or settings.default_user_id
    return await process_ingestion(body, "bookmark", uid, db)


@router.post("/ingest/esp32", response_model=IngestResponse)
async def ingest_esp32(
    body: IngestRequest,
    x_esp32_token: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if x_esp32_token != settings.esp32_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    uid = x_user_id or settings.default_user_id
    return await process_ingestion(body, "esp32", uid, db)
