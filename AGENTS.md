# keep — AGENTS.md

## Project Overview
Notes/links/voice transcription service receiving data from Odyssey (WhatsApp), browser extension, bookmark export, and ESP32. Stores everything in PostgreSQL via SQLAlchemy.

## Stack
- Python 3.12 + FastAPI
- PostgreSQL 16 (SQLAlchemy 2.0 + psycopg2)
- pgAdmin 4 for DB inspection

## Run Commands
```bash
cp .env.example .env    # edit with real tokens
docker compose up --build
```
- API: http://localhost:3005
- pgAdmin: http://localhost:5050 (admin@local / admin)
- Postgres: localhost:5432 (user: `keep`, pass: `keep`, db: `keep`)

## Key Endpoints
| Method | Path | Auth Header | Purpose |
|--------|------|-------------|---------|
| GET | `/health` | none | health check |
| POST | `/webhook` | `x-gateway-secret` | Odyssey webhook (`/keep`, `/help`, `/list`, voice) |
| POST | `/ingest/extension` | `x-extension-token` | browser extension |
| POST | `/ingest/bookmark` | `x-extension-token` | bookmark export |
| POST | `/ingest/esp32` | `x-esp32-token` | ESP32 device |

## Architecture
```
app/
├── main.py          # FastAPI entrypoint, lifespan creates tables
├── config.py        # Settings (env-driven, pydantic-settings)
├── schemas.py       # Pydantic models (ItemOut, IngestRequest, IngestResponse)
├── db/
│   ├── models.py    # SQLAlchemy ORM (Item table with constraints/indexes)
│   └── session.py   # engine + SessionLocal + get_db dependency
└── routers/
    ├── webhook.py   # /webhook — Odyssey integration, replies via Odyssey egress
    └── ingest.py    # /ingest/* — extension/bookmark/ESP32 ingestion
```

## Database Model (Item)
- `kind`: 'note' | 'link' | 'transcript' (check constraint)
- `context`: 'text' | 'audio' | 'link' (check constraint)
- `source`: 'whatsapp' | 'extension' | 'esp32' | 'bookmark' (check constraint)
- `content`: useful text (English translation for voice)
- `original`: raw Marathi transcript (voice only)
- `meta`: JSONB, default `{}`
- Indexes on `created_at`, `kind`, `source`

## Auth Notes
- Webhook: `x-gateway-secret` must match `NOTES_WEBHOOK_SECRET`
- Extension/Bookmark: `x-extension-token` must match `EXTENSION_TOKEN`
- ESP32: `x-esp32-token` must match `ESP32_TOKEN`
- Tokens configured in `.env` (see `.env.example`)

## Odyssey Integration
- Webhook receives `intent` (`/keep`, `/help`, `/list`, `continuation`) and `raw_text`
- `/list [n]` returns last n items (default 10, max 50)
- Replies sent back via Odyssey egress API (`ODYSSEY_URL/send` with `ODYSSEY_API_KEY`)
- Voice transcription not yet implemented (returns placeholder)

## Environment Variables
See `.env.example`. Critical: `DATABASE_URL` must match docker-compose postgres service.

## Docker Network
- `keep` network is **external** — create once: `docker network create keep`
- Services communicate via service names (`db`, `api`, `pgadmin`)

## No Test/Lint/Typecheck Setup
This repo has no pytest, ruff, mypy, or pre-commit configured. Add if needed.

## External Design Spec
Full design: `../llm/new-service-plan.md`