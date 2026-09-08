import os
import time

# Override DB URL for local host execution
os.environ["DATABASE_URL"] = "postgresql+psycopg2://keep:keep@localhost:5432/keep"
os.environ["NOTES_WEBHOOK_SECRET"] = "testsecret"

# We will load the actual .env so GEMINI_API_KEY is picked up
from dotenv import load_dotenv
load_dotenv()

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import engine
from sqlalchemy import text

def run_tests():
    print("Initializing TestClient (runs lifespan: tables + pgvector)...")
    
    # We use TestClient as a context manager to run lifespan events
    with TestClient(app) as client:
        print("\n✅ Server started.")
        
        # 1. Save a natural text note
        print("\n--- 1. Testing Text Save (User A) ---")
        save_payload = {
            "intent": "/keep",
            "raw_text": "/keep sarvesh recommended twc nandan cafe mocha is good its in parel",
            "from": "+919876543210"
        }
        resp1 = client.post("/webhook", json=save_payload, headers={"x-gateway-secret": "testsecret"})
        print(f"Status: {resp1.status_code}")
        print(f"Response: {resp1.json()}")
        
        # 2. Save a YouTube link
        print("\n--- 2. Testing YouTube Enrichment Save (User A) ---")
        yt_payload = {
            "intent": "/keep",
            "raw_text": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "from": "+919876543210"
        }
        resp2 = client.post("/webhook", json=yt_payload, headers={"x-gateway-secret": "testsecret"})
        print(f"Status: {resp2.status_code}")
        print(f"Response: {resp2.json()}")
        
        # 3. Query RAG (User A)
        print("\n--- 3. Testing RAG Conversational Recall (User A) ---")
        ai_payload = {
            "intent": "/ai",
            "raw_text": "/ai which cafe did sarvesh recommend?",
            "from": "+919876543210"
        }
        # The webhook endpoint attempts to reply to Odyssey asynchronously, 
        # but returns 200 immediately. We can check the DB to see tags!
        resp3 = client.post("/webhook", json=ai_payload, headers={"x-gateway-secret": "testsecret"})
        print(f"Status: {resp3.status_code}")
        print(f"Response: {resp3.json()}")
        
        # 4. Multi-Tenant Isolation
        print("\n--- 4. Testing Multi-Tenant Isolation (User B) ---")
        ai_payload_b = {
            "intent": "/ai",
            "raw_text": "/ai which cafe did sarvesh recommend?",
            "from": "+11234567890"
        }
        resp4 = client.post("/webhook", json=ai_payload_b, headers={"x-gateway-secret": "testsecret"})
        print(f"Status: {resp4.status_code}")
        print(f"Response: {resp4.json()}")
        
        # 5. Let's inspect the database directly to show the generated tags and enrichment!
        print("\n--- 5. Inspecting Database Records ---")
        with engine.connect() as conn:
            records = conn.execute(text("SELECT content_type, content, url, auto_tags, enriched_text FROM items ORDER BY created_at DESC LIMIT 2")).mappings().all()
            for r in records:
                print(f"\nType: {r['content_type']}")
                print(f"Content: {r['content']}")
                print(f"URL: {r['url']}")
                print(f"Tags: {r['auto_tags']}")
                print(f"Enriched: {r['enriched_text']}")

if __name__ == "__main__":
    run_tests()
