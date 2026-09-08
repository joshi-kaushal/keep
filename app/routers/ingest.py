import logging
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.db.models import Item
from app.schemas import IngestRequest, IngestResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/ingest/extension", response_model=IngestResponse)
def ingest_extension(
    body: IngestRequest,
    x_extension_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if x_extension_token != settings.extension_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    item = Item(
        kind=body.kind,
        context=body.context,
        content=body.content,
        original=body.original,
        source="extension",
        meta=body.metadata,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return IngestResponse(id=item.id, kind=item.kind)


@router.post("/ingest/bookmark", response_model=IngestResponse)
def ingest_bookmark(
    body: IngestRequest,
    x_extension_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    # Bookmarks share the extension token for now; split later if needed.
    if x_extension_token != settings.extension_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    item = Item(
        kind=body.kind,
        context=body.context,
        content=body.content,
        original=body.original,
        source="bookmark",
        meta=body.metadata,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return IngestResponse(id=item.id, kind=item.kind)


@router.post("/ingest/esp32", response_model=IngestResponse)
def ingest_esp32(
    body: IngestRequest,
    x_esp32_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if x_esp32_token != settings.esp32_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    item = Item(
        kind=body.kind,
        context=body.context,
        content=body.content,
        original=body.original,
        source="esp32",
        meta=body.metadata,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return IngestResponse(id=item.id, kind=item.kind)
