# keep

Notes / Links / Voice transcription service. Receives data from **[Odyssey (WhatsApp bot)](https://github.com/joshi-kaushal/odyssey)**, a browser extension, bookmark exports, and an ESP32 device — then enriches, auto-tags, and embeds each item so you can ask questions over your own notes with semantic RAG.

**Multi-tenant**: every item belongs to a `user_id` (WhatsApp senders are identified by their
phone number; direct ingestions use an `x-user-id` header). Retrieval is always scoped to the caller's own data.

> The current version only supports WhatsApp bot. Connections with other services is not fully tested yet.

## Stack

- Python 3.12 + FastAPI
- PostgreSQL 16 + **pgvector** (via SQLAlchemy 2.0 + psycopg2)
- **Gemini** for auto-tagging & conversational answers, embeddings via the Gemini Embedding API
- pgAdmin 4 for DB inspection

## Architecture

```mermaid
flowchart LR
    subgraph Sources
        WA["Odyssey / WhatsApp<br/>(/keep /ai /list /help)"]
        EXT["Browser extension"]
        BM["Bookmark export"]
        ESP["ESP32 device"]
    end

    API["FastAPI app<br/>(port 3005)"]

    subgraph Pipeline["Save pipeline"]
        DETECT["detect_content_type()"]
        ENRICH["enrich_url()<br/>(oEmbed / page scrape, 5s)"]
        TAGS["generate_auto_tags()<br/>(Gemini)"]
        EMBED["embed_snippet()<br/>(gemini-embedding-001, 768d)"]
    end

    subgraph Query["Query pipeline"]
        QEMBED["Embed question"]
        VEC["pgvector cosine search<br/>similarity ≥ 0.75"]
        TRGM["pg_trgm keyword fallback"]
        LLM["Gemini conversational<br/>synthesis"]
    end

    PG[("PostgreSQL + pgvector<br/>items table")]

    WA -->|POST /webhook| API
    EXT -->|POST /ingest/extension| API
    BM -->|POST /ingest/bookmark| API
    ESP -->|POST /ingest/esp32| API

    API --> DETECT --> ENRICH --> TAGS --> EMBED --> PG
    API --> QEMBED --> VEC
    VEC -. no results .-> TRGM
    VEC --> LLM
    TRGM --> LLM
    LLM -->|reply via Odyssey egress /send| WA
```

### Saving an item (`/keep`, extension, bookmark, ESP32)

```mermaid
sequenceDiagram
    participant S as Source (WhatsApp / extension / ESP32)
    participant A as keep API
    participant G as Gemini (tags)
    participant E as Embedding API
    participant D as Postgres + pgvector

    S->>A: content + auth header
    A->>A: verify token → resolve user_id
    A->>A: detect_content_type() → url?
    alt URL found (youtube / generic link)
        A->>A: enrich_url() — YouTube oEmbed or page scrape (5s timeout)
    end
    A->>G: generate_auto_tags(content, enriched)
    G-->>A: 3–6 search tags (JSON)
    A->>E: embed(content + tags + enriched)
    E-->>A: 768-dim vector
    A->>D: INSERT item (kind, content, tags, embedding, user_id)
    A-->>S: "Saved 👍" (WhatsApp only)
```

### Asking a question (`/ai <question>`)

```mermaid
sequenceDiagram
    participant W as WhatsApp user
    participant A as keep API
    participant D as Postgres + pgvector
    participant E as Embedding API
    participant L as Gemini
    participant O as Odyssey egress

    W->>A: /ai which cafe did sarvesh recommend?
    A->>A: normalize sender phone → user_id
    A->>E: embed question (RETRIEVAL_QUERY)
    E-->>A: 768-dim query vector
    A->>D: cosine search, similarity ≥ 0.75, LIMIT 3
    alt no vector hits
        A->>D: pg_trgm keyword search on content + tags
    end
    D-->>A: top 3 matching items
    A->>L: "WhatsApp buddy" synthesis prompt + context
    L-->>A: 1–2 sentence friendly answer
    A->>O: POST /send {to, text}
    O-->>W: "Sarvesh recommended TWC Nandan Cafe in Parel..."
```

## Run

```bash
cp .env.example .env        # then fill in real tokens & GEMINI_API_KEY
docker compose up --build
```

- API: http://localhost:3005
- pgAdmin: http://localhost:5050
- Postgres: localhost:5432 (user: `keep`, pass: `keep`, db: `keep`)
- Requires the external docker network once: `docker network create keep`

## Endpoints

| Method | Path                | Auth Header         | Purpose                                          |
| ------ | ------------------- | ------------------- | ------------------------------------------------ |
| GET    | `/health`           | none                | health check                                     |
| POST   | `/webhook`          | `x-gateway-secret`  | Odyssey: `/keep`, `/ai`, `/list`, `/help`, voice |
| POST   | `/ingest/extension` | `x-extension-token` | browser extension                                |
| POST   | `/ingest/bookmark`  | `x-extension-token` | bookmark export                                  |
| POST   | `/ingest/esp32`     | `x-esp32-token`     | ESP32 device                                     |

All `/ingest/*` endpoints accept an optional `x-user-id` header (defaults to
`DEFAULT_USER_ID`). The `/webhook` derives `user_id` from the sender's phone number.

### WhatsApp commands (via Odyssey)

| Command               | Action                                        |
| --------------------- | --------------------------------------------- |
| `/keep <text or url>` | save a note/link (enriched, tagged, embedded) |
| `/ai <question>`      | ask over your saved notes (semantic RAG)      |
| `/list [n]`           | show last n items (default 10, max 50)        |
| `/help`               | show command help                             |

## Data model (`items` table)

| Column                                | Notes                                                                    |
| ------------------------------------- | ------------------------------------------------------------------------ |
| `id`                                  | UUID string PK                                                           |
| `user_id`                             | tenant owner (indexed)                                                   |
| `kind`                                | `note` \| `link` \| `transcript`                                         |
| `context`                             | `text` \| `audio` \| `link`                                              |
| `content` / `original`                | useful text / raw Marathi transcript (voice)                             |
| `source`                              | `whatsapp` \| `extension` \| `esp32` \| `bookmark`                       |
| `meta`                                | JSONB                                                                    |
| `url`, `content_type`                 | extracted URL; `note` \| `youtube` \| `instagram` \| `twitter` \| `link` |
| `auto_tags`                           | text[] of Gemini search tags                                             |
| `enriched_text` / `enrichment_status` | fetched page context; `done` \| `skipped` \| `failed`                    |
| `embedding`                           | `vector(768)`                                                            |
| `created_at` / `updated_at`           | server defaults                                                          |

Indexes: HNSW cosine on `embedding`, GIN trigram on `content`, plus btree on
`user_id`, `created_at`, `kind`, `source`. The lifespan hook enables the `vector`
and `pg_trgm` extensions on startup.

## Layout

```
keep/
├── app/
│   ├── main.py           # FastAPI entrypoint + lifespan (extensions, create_all)
│   ├── config.py         # settings (env-driven)
│   ├── schemas.py        # Pydantic models
│   ├── db/
│   │   ├── models.py     # Item ORM + HNSW/GIN indexes
│   │   └── session.py    # engine + session + get_db
│   ├── routers/
│   │   ├── webhook.py    # /webhook — Odyssey intents (/keep /ai /list /help)
│   │   └── ingest.py     # /ingest/* — extension/bookmark/esp32
│   └── services/
│       ├── enrichment.py # content-type detection + URL enrichment (oEmbed/scrape)
│       └── rag.py        # auto-tags, embeddings, vector + trigram retrieval, QA synthesis
├── Dockerfile
├── docker-compose.yml    # db (pgvector), pgadmin, api
├── requirements.txt
├── .env.example
└── README.md
```

## Environment variables

See `.env.example`. `DATABASE_URL` must match the docker-compose postgres service.

| Var                               | Purpose                                              |
| --------------------------------- | ---------------------------------------------------- |
| `DATABASE_URL`                    | SQLAlchemy Postgres DSN                              |
| `ODYSSEY_URL` / `ODYSSEY_API_KEY` | egress replies back to WhatsApp                      |
| `NOTES_WEBHOOK_SECRET`            | `/webhook` auth (`x-gateway-secret`)                 |
| `EXTENSION_TOKEN` / `ESP32_TOKEN` | direct ingestion auth                                |
| `GEMINI_API_KEY`                  | tagging, embeddings & QA (required for RAG features) |
| `DEFAULT_USER_ID`                 | fallback tenant when no user is derivable            |
| `PORT`                            | API port (default 3005)                              |

## See also

- `../llm/new-service-plan.md` — full design spec
- `task.md` — milestone plan for the multi-tenant semantic RAG build
