import json
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from app.config import settings

logger = logging.getLogger(__name__)

# Initialize LangChain models
try:
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=settings.gemini_api_key
    )
    chat_model = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.2,
        google_api_key=settings.gemini_api_key
    )
except Exception as e:
    logger.error(f"Failed to initialize Gemini models: {e}")
    embeddings = None
    chat_model = None

def generate_auto_tags(raw_text: str, enriched_text: str | None = None) -> list[str]:
    """
    Uses Gemini 2.0 Flash to generate 3-6 concrete search tags for the snippet.
    Returns a list of tags.
    """
    if not chat_model:
        return []
        
    prompt = f"""
    Given this saved note/link, generate 3-6 short, concrete tags that describe what it is and why
    someone would search for it later. Favor concrete nouns and use-cases over abstract categories.
    Return ONLY a JSON array of strings, nothing else.

    Examples of good tag style: "palak paneer dish", "cafe in bandra", "restaurant in parel",
    "yoga after busy day", "glute exercise", "running gym", "sarvesh recommendation"

    Content: {raw_text}
    Additional context: {enriched_text or "none"}
    """
    
    try:
        response = chat_model.invoke(prompt)
        content = response.content.strip()
        if content.startswith("```json"):
            content = content.replace("```json", "", 1)
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        tags = json.loads(content)
        if isinstance(tags, list):
            return tags
    except Exception as e:
        logger.warning(f"Failed to generate tags: {e}")
    
    return []

def embed_snippet(raw_text: str, tags: list[str], enriched_text: str | None = None) -> list[float]:
    """
    Generates a 768-dim embedding for the content.
    """
    if not embeddings:
        return [0.0] * 768
        
    context_parts = [raw_text]
    if tags:
        context_parts.append(", ".join(tags))
    if enriched_text:
        context_parts.append(enriched_text)
        
    full_text = "\n".join(context_parts)
    
    try:
        return embeddings.embed_query(full_text)
    except Exception as e:
        logger.error(f"Failed to embed snippet: {e}")
        return [0.0] * 768

def query_snippets(user_id: str, query: str, db: Session) -> str:
    """
    Embeds query, performs pgvector search with fallback to pg_trgm.
    Synthesizes a conversational response.
    """
    if not embeddings or not chat_model:
        return "I'm sorry, my AI features are currently unavailable."
        
    try:
        query_emb = embeddings.embed_query(query)
    except Exception as e:
        logger.error(f"Failed to embed query: {e}")
        return "I'm having trouble understanding that right now."

    # 1. Try vector similarity search
    sql = text("""
        SELECT id, content, url, auto_tags, content_type,
               1 - (embedding <=> :query_emb::vector) AS similarity
        FROM items
        WHERE user_id = :user_id
          AND 1 - (embedding <=> :query_emb::vector) >= 0.75
        ORDER BY embedding <=> :query_emb::vector
        LIMIT 3
    """)
    
    results = db.execute(sql, {"user_id": user_id, "query_emb": query_emb}).mappings().all()
    
    # 2. Fallback to pg_trgm if no strong vector matches
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

    # 3. Conversational Synthesis
    context_blocks = []
    for r in results:
        block = f"Note: {r['content']}"
        if r['url']:
            block += f"\nLink: {r['url']}"
        if r['auto_tags']:
            block += f"\nTags: {', '.join(r['auto_tags'])}"
        context_blocks.append(block)
        
    retrieved_context = "\n\n".join(context_blocks)
    
    prompt = f"""
    You are an empathetic, concise personal assistant chatting on WhatsApp. 
    Based on the user's saved notes below, answer their question conversationally in 1-2 friendly sentences 
    like a friend texting back. Do not sound like an AI assistant or dump search results. 
    If a link exists in the notes, weave it in naturally.
    Do not use em dashes.
    
    User's Question: {query}

    Saved Notes Context:
    {retrieved_context}
    """
    
    try:
        response = chat_model.invoke(prompt)
        return response.content.strip()
    except Exception as e:
        logger.error(f"Failed to synthesize response: {e}")
        return "I found some notes, but had trouble formatting the response."
