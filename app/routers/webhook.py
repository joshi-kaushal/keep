import logging
import re
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.db.models import Item
from app.services.enrichment import detect_content_type, enrich_url
from app.services.rag import generate_auto_tags, embed_snippet, query_snippets

logger = logging.getLogger(__name__)
router = APIRouter()


async def reply_to_odyssey(to: str, text: str) -> None:
    """Best-effort reply back through Odyssey's egress."""
    if not settings.odyssey_api_key:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{settings.odyssey_url}/send",
                headers={"x-api-key": settings.odyssey_api_key},
                json={"to": to, "text": text},
            )
    except Exception as e:
        logger.error("Failed to reply via Odyssey: %s", e)


@router.post("/webhook")
async def odyssey_webhook(
    payload: dict,
    x_gateway_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Endpoint hit by Odyssey for /keep, /help, /list, /ai and voice notes."""
    if x_gateway_secret != settings.notes_webhook_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")

    intent = (payload.get("intent") or "").lower().strip()
    raw = (payload.get("raw_text") or "").strip()
    
    from_number = payload.get("from")
    # Normalize phone number to E.164 (digits and +)
    user_id = re.sub(r"[^\d+]", "", from_number) if from_number else settings.default_user_id
    if not user_id:
        user_id = settings.default_user_id

    # Detect prefix
    lower_raw = raw.lower()
    if lower_raw.startswith("/keep ") or lower_raw == "/keep":
        return await handle_keep(raw, from_number, user_id, db)
    if lower_raw.startswith("/ai ") or lower_raw == "/ai":
        return await handle_ai(raw, from_number, user_id, db)
        
    if intent in ("/keep", "keep", "continuation"):
        return await handle_keep(raw, from_number, user_id, db)
    if intent in ("/ai", "ai", "query"):
        return await handle_ai(raw, from_number, user_id, db)

    if intent == "/help":
        return await handle_help(from_number)
    if intent == "/list":
        return await handle_list(raw, from_number, user_id, db)

    if payload.get("media"):
        if from_number:
            await reply_to_odyssey(from_number, "Voice transcription not yet implemented.")
        return {"status": "received", "kind": "transcript"}

    raise HTTPException(status_code=400, detail="Unknown intent")


async def handle_help(from_number: str | None) -> dict:
    HELP_TEXT = """
*Keep Bot commands* 📝

Available commands:
• `/keep <text-or-url>` — save a note or link
• `/ai <question>` — ask a question about your notes
• `/list` — show recent notes
""".strip()
    if from_number:
        await reply_to_odyssey(from_number, HELP_TEXT)
    return {"status": "ok"}


async def handle_list(raw: str, from_number: str | None, user_id: str, db: Session) -> dict:
    """Parse `/list` or `/list 20` and return a bullet list of content."""
    parts = raw.split()
    n = 10
    if len(parts) >= 2 and parts[1].isdigit():
        n = min(int(parts[1]), 50)

    rows = (
        db.query(Item)
        .filter(Item.user_id == user_id)
        .order_by(Item.created_at.desc())
        .limit(n)
        .all()
    )

    lines = [f"- {r.content}" for r in rows]
    text = "\n".join(lines) if lines else "No items found."
    if from_number:
        await reply_to_odyssey(from_number, text)
    return {"status": "ok", "count": len(rows)}


async def handle_ai(raw: str, from_number: str | None, user_id: str, db: Session) -> dict:
    query = raw
    if query.lower().startswith("/ai"):
        query = query[3:].strip()
        
    if not query:
        if from_number:
            await reply_to_odyssey(from_number, "What would you like to know?")
        return {"status": "error", "reason": "empty"}
        
    # Call RAG retrieval
    response_text = query_snippets(user_id, query, db)
    
    if from_number:
        await reply_to_odyssey(from_number, response_text)
        
    return {"status": "answered"}


async def handle_keep(raw: str, from_number: str | None, user_id: str, db: Session) -> dict:
    body = raw
    if body.lower().startswith("/keep"):
        body = body[5:].lstrip()

    if not body:
        if from_number:
            await reply_to_odyssey(from_number, "Usage: /keep <content>")
        return {"status": "error", "reason": "empty"}

    content_type, extracted_url = detect_content_type(body)
    
    kind = "link" if content_type in ("link", "youtube", "instagram", "twitter") else "note"
    context = "link" if kind == "link" else "text"
    
    enriched_text, enrichment_status = await enrich_url(content_type, extracted_url)
    
    tags = generate_auto_tags(body, enriched_text)
    embedding = embed_snippet(body, tags, enriched_text)
    
    item = Item(
        user_id=user_id,
        kind=kind,
        context=context,
        content=body,
        source="whatsapp",
        meta={},
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

    if from_number:
        msg = f"Saved 👍"
        await reply_to_odyssey(from_number, msg)
        
    return {"status": "saved", "id": item.id, "kind": item.kind}
