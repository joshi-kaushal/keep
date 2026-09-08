import re
import httpx
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

def detect_content_type(text: str) -> tuple[str, str | None]:
    """
    Detects if the text contains a URL and classifies it as youtube, instagram, or link.
    Returns (content_type, extracted_url).
    """
    url_match = re.search(r"https?://[^\s]+", text)
    if not url_match:
        return "note", None
        
    url = url_match.group(0)
    lower_url = url.lower()
    
    if "youtube.com" in lower_url or "youtu.be" in lower_url:
        return "youtube", url
    if "instagram.com" in lower_url:
        return "instagram", url
    if "twitter.com" in lower_url or "x.com/" in lower_url:
        return "twitter", url
        
    return "link", url

async def enrich_url(content_type: str, url: str) -> tuple[str | None, str]:
    """
    Fetches context for a URL with a 5s timeout.
    Returns (enriched_text, status) where status is 'done', 'skipped', or 'failed'.
    """
    if content_type in ("instagram", "twitter") or not url:
        return None, "skipped"
        
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            if content_type == "youtube":
                resp = await client.get(f"https://www.youtube.com/oembed?url={url}&format=json")
                resp.raise_for_status()
                data = resp.json()
                title = data.get("title", "")
                author = data.get("author_name", "")
                enriched = f"Title: {title} | Channel: {author}" if title else None
                return enriched, "done"
                
            elif content_type == "link":
                # We use a user-agent to avoid simple bot blocks
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                resp = await client.get(url, follow_redirects=True, headers=headers)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                
                title = soup.title.string.strip() if soup.title and soup.title.string else ""
                
                desc_tag = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
                desc = desc_tag.get("content", "").strip() if desc_tag else ""
                
                parts = []
                if title:
                    parts.append(f"Title: {title}")
                if desc:
                    parts.append(f"Description: {desc}")
                    
                enriched = " | ".join(parts) if parts else None
                return enriched, "done"
                
    except Exception as e:
        logger.warning(f"Failed to enrich URL {url}: {e}")
        return None, "failed"
        
    return None, "failed"
