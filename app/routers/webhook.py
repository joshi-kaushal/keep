import logging
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.db.models import Item

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
    """Endpoint hit by Odyssey for /keep, /help, /list, and voice notes."""
    if x_gateway_secret != settings.notes_webhook_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")

    intent = (payload.get("intent") or "").lower()
    raw = (payload.get("raw_text") or "").strip()
    from_number = payload.get("from")

    if intent == "/help":
        return await handle_help(from_number)
    if intent == "/list":
        return await handle_list(raw, from_number, db)
    if intent == "/keep":
        kind = "link" if raw.lower().startswith(("http://", "https://")) else "note"
        ctx = "link" if kind == "link" else "text"
        return await handle_save(kind, ctx, raw, from_number, payload, db)
    if intent == "continuation":
        kind = "link" if raw.lower().startswith(("http://", "https://")) else "note"
        ctx = "link" if kind == "link" else "text"
        return await handle_save(kind, ctx, raw, from_number, payload, db)

    if payload.get("media"):
        if from_number:
            await reply_to_odyssey(from_number, "Voice transcription not yet implemented.")
        return {"status": "received", "kind": "transcript"}

    raise HTTPException(status_code=400, detail="Unknown intent")


async def handle_help(from_number: str | None) -> dict:
    HELP_TEXT = """
*Keep Bot commands* 📝

Available commands:
• `/keep` <text-or-url> — save a note or link
• `/list` — show recent notes
• `/list <n>` — show last n notes
""".strip()
    if from_number:
        await reply_to_odyssey(from_number, HELP_TEXT)
    return {"status": "ok"}


async def handle_list(raw: str, from_number: str | None, db: Session) -> dict:
    """Parse `/list` or `/list 20` and return a bullet list of content."""
    parts = raw.split()
    n = 10
    if len(parts) >= 2 and parts[1].isdigit():
        n = min(int(parts[1]), 50)

    rows = (
        db.query(Item)
        .order_by(Item.created_at.desc())
        .limit(n)
        .all()
    )

    lines = [f"- {r.content}" for r in rows]
    text = "\n".join(lines) if lines else "No items found."
    if from_number:
        await reply_to_odyssey(from_number, text)
    return {"status": "ok", "count": len(rows)}


async def handle_save(
    kind: str,
    context: str,
    raw: str,
    from_number: str | None,
    payload: dict,
    db: Session,
) -> dict:
    body = raw
    if body.lower().startswith("/keep"):
        body = body[len("/keep"):].lstrip()

    if not body:
        if from_number:
            await reply_to_odyssey(from_number, f"Usage: {kind} <content>")
        return {"status": "error", "reason": "empty"}

    item = Item(
        kind=kind,
        context=context,
        content=body,
        source="whatsapp",
        meta={},
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    if from_number:
        msg = f"{kind.capitalize()} saved." if kind != "transcript" else "Saved."
        await reply_to_odyssey(from_number, msg)
    return {"status": "saved", "id": item.id, "kind": item.kind}
