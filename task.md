# Tasks: Multi-Tenant Semantic RAG for Keep

Tasks are grouped into milestones. After each milestone is completed, we pause for your review before proceeding.

---

## Milestone 1: Dependencies, Infrastructure & Config Setup
- [x] Update `requirements.txt` with `pgvector`, `langchain`, `langchain-google-genai`, `beautifulsoup4`
- [x] Update `docker-compose.yml` db service to `pgvector/pgvector:pg16`
- [x] Update `app/config.py` to add `default_user_id` and ensure `gemini_api_key` configuration
- [x] **Milestone 1 Review**: Pause and confirm dependencies and environment setup

---

## Milestone 2: Database Layer & Vector Indexing
- [x] Update `app/db/models.py`:
  - Add `user_id` (indexed, default `"kaushal"`)
  - Add `url`, `content_type` (`note`, `youtube`, `instagram`, `link`)
  - Add `auto_tags` (Postgres `ARRAY(String)`)
  - Add `enriched_text` and `enrichment_status` (`done`, `skipped`, `failed`)
  - Add `embedding` (`Vector(768)`)
  - Add HNSW vector index (`vector_cosine_ops`)
  - Add GIN Trigram index (`gin_trgm_ops`) on content + tags
- [x] Update `app/main.py` lifespan to ensure `vector` and `pg_trgm` PostgreSQL extensions are loaded
- [x] **Milestone 2 Review**: Pause and confirm DB schema & vector index setup

---

## Milestone 3: Enrichment & LangChain RAG Core Services
- [x] Implement `app/services/enrichment.py`:
  - `detect_content_type(text)` for YouTube, Instagram, Generic URLs, and Notes
  - `enrich_url(...)` with 5s timeout (YouTube oEmbed, BeautifulSoup for `<title>` & `<meta>` description)
- [x] Implement `app/services/rag.py`:
  - LangChain Gemini 2.0 Flash tag generator (generating 3–6 concrete search tags)
  - LangChain `text-embedding-004` embedder
  - LangChain conversational QA synthesis chain with WhatsApp buddy persona (1–2 sentences, humanized texting style)
  - Vector similarity search (`>= 0.75`) with `pg_trgm` keyword fallback
- [x] **Milestone 3 Review**: Pause and confirm enrichment & LangChain pipeline logic

---

## Milestone 4: Webhook & Ingestion Integration
- [x] Update `app/routers/webhook.py`:
  - Support multi-tenancy: extract and normalize phone number from `payload["from"]`
  - Support `/keep` and `/ai` via both `payload["intent"]` and `raw_text` prefix
  - Expose callable `handle_keep(...)` and `handle_ai(...)`
  - Connect saving pipeline with WhatsApp confirmation
  - Connect retrieval pipeline with WhatsApp conversational answer via Odyssey egress
- [x] Update `app/routers/ingest.py`:
  - Support `x-user-id` header (fallback to `default_user_id`)
  - Integrate enrichment and embedding for extension, bookmark, and ESP32 ingestions
- [x] **Milestone 4 Review**: Pause and confirm webhook & ingestion endpoints

---

## Milestone 5: Verification & End-to-End Testing
- [x] Write a standalone integration verification script:
  - Test saving conversational text: `"sarvesh recommended twc nandan cafe mocha is good its in parel"`
  - Test asking: `"which cafe did sarvesh recommend?"` and `"share good mocha places"`
  - Verify conversational human-like response: `"Sarvesh recommended TWC Nandan Cafe in Parel and said their mocha is really good!"`
  - Test link enrichment with a YouTube URL
  - Test multi-tenant isolation between different phone numbers
- [x] **Final Review**: Comprehensive walkthrough and sign-off
