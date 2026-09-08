# Keep Service — Semantic RAG & Multi-Tenancy Plan

## Overview
Keep is a personal note and link capture service. This document outlines the architecture and design for adding a semantic memory / RAG layer with multi-tenancy based on WhatsApp phone numbers, LangChain, Google Gemini, and PostgreSQL (`pgvector` + `pg_trgm`).

---

## 1. Objectives & Use Cases
- **Natural Personal Texting**: Users text random recommendations, thoughts, links, and snippets into WhatsApp (e.g. `sarvesh recommended twc nandan cafe mocha is good its in parel`).
- **Conversational Recall (`/ai`)**: Users later ask natural questions in the chat (e.g. `which cafe did sarvesh recommend?`, `share good mocha places`), and receive a warm, concise, human-like WhatsApp message answering them directly (e.g. `Sarvesh recommended TWC Nandan Cafe in Parel — he said their mocha is really good!`).
- **Multi-Tenancy by Phone Number**: Open multi-tenancy where each user's snippets are partitioned strictly by their normalized E.164 phone number (`user_id`).
- **Multi-Source Support**: WhatsApp bot, browser extension, bookmark imports, and ESP32 hardware capture seamlessly participate in the same vector memory store.

---

## 2. Architecture & Data Flow

```
WhatsApp / Odyssey / Extension / ESP32
                 │
                 ▼
          FastAPI Router
  (/webhook & /ingest/* with user_id)
        │                     │
   (Save / /keep)        (Query / /ai)
        │                     │
        ▼                     ▼
┌──────────────────┐   ┌───────────────────────────────┐
│ Saving Pipeline  │   │      Retrieval Pipeline       │
├──────────────────┤   ├───────────────────────────────┤
│ 1. Type & URL    │   │ 1. Embed query with Gemini    │
│    Detection     │   │ 2. pgvector cosine search     │
│ 2. 5s URL Enrich │   │    (HNSW index, >= 0.75 sim)  │
│ 3. Gemini Tagging│   │ 3. pg_trgm keyword fallback   │
│ 4. Gemini Embed  │   │ 4. Conversational Synthesis   │
│ 5. DB Insert     │   │    (Gemini 2.0 Flash prompt)  │
└────────┬─────────┘   └───────────────┬───────────────┘
         │                             │
         ▼                             ▼
   Postgres (pgvector)       WhatsApp Reply via Egress
```

---

## 3. Database Schema (Upgraded `items` table)

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Upgraded items table definition:
-- id                 VARCHAR PRIMARY KEY
-- user_id            VARCHAR NOT NULL DEFAULT 'kaushal' (indexed)
-- kind               VARCHAR ('note' | 'link' | 'transcript')
-- context            VARCHAR ('text' | 'audio' | 'link')
-- content            TEXT NOT NULL (raw user text / translation)
-- original           TEXT NULL (voice raw)
-- source             VARCHAR ('whatsapp' | 'extension' | 'esp32' | 'bookmark')
-- metadata           JSONB NOT NULL DEFAULT '{}'
-- url                TEXT NULL
-- content_type       VARCHAR NOT NULL DEFAULT 'note' ('note' | 'youtube' | 'instagram' | 'link')
-- auto_tags          TEXT[] DEFAULT '{}'
-- enriched_text      TEXT NULL
-- enrichment_status  VARCHAR NOT NULL DEFAULT 'skipped' ('done' | 'skipped' | 'failed')
-- embedding          VECTOR(768) NULL
-- created_at         TIMESTAMPTZ DEFAULT now()
-- updated_at         TIMESTAMPTZ DEFAULT now()

-- Indexes:
-- HNSW index on embedding (vector_cosine_ops)
-- GIN Trigram index on (content || ' ' || array_to_string(auto_tags, ' '))
-- B-tree index on user_id
-- B-tree index on created_at
```

---

## 4. LangChain & Gemini Pipelines

### 4.1 Ingestion / Saving Pipeline
1. **Type & URL Detection**:
   - `youtube.com`, `youtu.be` -> `youtube`
   - `instagram.com` -> `instagram` (enrichment skipped, relies on user text)
   - Other `http(s)` -> `link`
   - Otherwise -> `note`
2. **5s Best-effort Enrichment**:
   - YouTube: oEmbed API for title and author.
   - Link: fetch HTML, extract `<title>` and `<meta name="description">` / `og:description`.
3. **Tag Generation**:
   - LangChain + `gemini-2.0-flash`.
   - Generates 3–6 concrete tags focused on recall use cases (e.g. `sarvesh recommendation`, `twc nandan cafe`, `mocha coffee`, `cafe in parel`).
4. **Vector Embedding**:
   - LangChain `GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")` (768 dimensions).
   - Input: `f"{content}\n{', '.join(auto_tags)}\n{enriched_text or ''}"`.

### 4.2 Retrieval & Humanized Synthesis Pipeline
1. **Query Embedding**: Embed user question with `text-embedding-004`.
2. **Vector Similarity**:
   - Query `items` WHERE `user_id = :user_id` ORDER BY `embedding <=> query_embedding` LIMIT 3.
   - Cosine similarity threshold: `>= 0.75`.
3. **Keyword / Trigram Fallback**:
   - If no vector match meets threshold, use `pg_trgm` on `content` and `auto_tags` to rescue exact names/keywords.
4. **Conversational Synthesis Persona**:
   - Prompt `gemini-2.0-flash` with retrieved context and user query.
   - Persona: Concierge buddy chatting on WhatsApp. 1–2 sentences, warm, direct, natural human texting tone.
   - If nothing found: "I couldn't find anything matching that in your notes."
