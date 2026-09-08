import json
import logging
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import text
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768  # gemini-embedding-001 with output_dimensionality=768 (HNSW max = 2000)
EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"

# Initialize LangChain chat model only (embeddings use httpx directly)
try:
    chat_model = ChatGoogleGenerativeAI(
        model="gemini-3.6-flash",
        temperature=0.2,
        google_api_key=settings.gemini_api_key
    )
except Exception as e:
    logger.error(f"Failed to initialize Gemini chat model: {e}")
    chat_model = None


def _embed(text_input: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """
    Calls Google embedding API directly with output_dimensionality=768.
    This bypasses LangChain which doesn't expose the output_dimensionality param.
    """
    try:
        resp = httpx.post(
            EMBED_URL,
            params={"key": settings.gemini_api_key},
            json={
                "content": {"parts": [{"text": text_input}]},
                "taskType": task_type,
                "outputDimensionality": EMBEDDING_DIM,
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]["values"]
    except Exception as e:
        logger.error(f"Embedding API call failed: {e}")
        return [0.0] * EMBEDDING_DIM


def _normalize_content(response_content) -> str:
    """Normalize LangChain response.content which may be a str or list of parts."""
    if isinstance(response_content, list):
        return " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in response_content
        ).strip()
    return str(response_content).strip()


def generate_auto_tags(raw_text: str, enriched_text: str | None = None) -> list[str]:
    """
    Uses Gemini 3.6 Flash to generate 3-6 concrete search tags for the snippet.
    Returns a list of tags.
    """
    if not chat_model:
        return []

    prompt = f"""Given this saved note/link, generate 3-6 short, concrete tags that describe what it is and why
someone would search for it later. Favor concrete nouns and use-cases over abstract categories.
Return ONLY a JSON array of strings, nothing else.

Examples of good tag style: "palak paneer dish", "cafe in bandra", "restaurant in parel",
"yoga after busy day", "glute exercise", "running gym", "sarvesh recommendation"

Content: {raw_text}
Additional context: {enriched_text or "none"}"""

    try:
        response = chat_model.invoke(prompt)
        content = _normalize_content(response.content)
        if content.startswith("```json"):
            content = content.replace("```json", "", 1)
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        tags = json.loads(content)
        if isinstance(tags, list):
            return [str(t) for t in tags]
    except Exception as e:
        logger.warning(f"Failed to generate tags: {e}")

    return []


def embed_snippet(raw_text: str, tags: list[str], enriched_text: str | None = None) -> list[float]:
    """
    Generates a 768-dim embedding for the content using the Google embedding API directly.
    """
    parts = [raw_text]
    if tags:
        parts.append(", ".join(tags))
    if enriched_text:
        parts.append(enriched_text)

    full_text = "\n".join(parts)
    return _embed(full_text, task_type="RETRIEVAL_DOCUMENT")


def query_snippets(user_id: str, query: str, db: Session) -> str:
    """
    Embeds query, performs pgvector cosine search (>= 0.75) with pg_trgm fallback.
    Synthesizes a conversational WhatsApp buddy response.
    """
    if not chat_model:
        return "I'm sorry, my AI features are currently unavailable."

    query_emb = _embed(query, task_type="RETRIEVAL_QUERY")
    if all(v == 0.0 for v in query_emb):
        return "I'm having trouble understanding that right now."

    # 1. Vector similarity search (cosine, threshold 0.75)
    sql = text("""
        SELECT id, content, url, auto_tags, content_type,
            1 - (embedding <=> CAST(:query_emb AS vector)) AS similarity
        FROM items
        WHERE user_id = :user_id
        AND embedding IS NOT NULL
        AND 1 - (embedding <=> CAST(:query_emb AS vector)) >= 0.75
        ORDER BY embedding <=> CAST(:query_emb AS vector)
        LIMIT 3
    """)
    results = db.execute(sql, {"user_id": user_id, "query_emb": query_emb}).mappings().all()

    # 2. pg_trgm keyword fallback
    if not results:
        trgm_sql = text("""
            SELECT id, content, url, auto_tags, content_type
            FROM items
            WHERE user_id = :user_id
              AND (content || ' ' || array_to_string(auto_tags, ' ')) % :query
            ORDER BY similarity((content || ' ' || array_to_string(auto_tags, ' ')), :query) DESC
            LIMIT 3
        """)
        results = db.execute(trgm_sql, {"user_id": user_id, "query": query}).mappings().all()

    if not results:
        return "I couldn't find anything matching that in your notes."

    # 3. Conversational synthesis
    context_blocks = []
    for r in results:
        block = f"Note: {r['content']}"
        if r["url"]:
            block += f"\nLink: {r['url']}"
        if r["auto_tags"]:
            block += f"\nTags: {', '.join(r['auto_tags'])}"
        context_blocks.append(block)

    retrieved_context = "\n\n".join(context_blocks)

    prompt = f"""You are an empathetic, concise personal assistant chatting on WhatsApp.
Based on the user's saved notes below, answer their question conversationally in 1-2 friendly sentences
like a close friend texting back. Do not sound like an AI assistant or dump search results.
If a link exists in the notes, weave it in naturally. Do not use em dashes.

User's Question: {query}

Saved Notes Context:
{retrieved_context}"""

    try:
        response = chat_model.invoke(prompt)
        return _normalize_content(response.content)
    except Exception as e:
        logger.error(f"Failed to synthesize response: {e}")
        return "I found some notes, but had trouble formatting the response."
