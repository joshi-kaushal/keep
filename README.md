# keep

Notes / Links / Voice transcription service. Receives data from Odyssey (WhatsApp), browser extension, bookmark export, and ESP32. Stores everything in PostgreSQL.

## Stack

- Python 3.12 + FastAPI
- PostgreSQL 16 (via SQLAlchemy + psycopg2)
- pgAdmin 4 for DB inspection

## Run

```bash
cp .env.example .env
# edit .env with your real tokens
docker compose up --build
```

- API: http://localhost:3005
- pgAdmin: http://localhost:5050 (admin@local / admin)
- Postgres: localhost:5432 (user: `keep`, pass: `keep`, db: `keep`)

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | none | health check |
| POST | `/webhook` | `x-gateway-secret` | Odyssey webhook (/keep /help /list /voice) |
| POST | `/ingest/extension` | `x-extension-token` | browser extension |
| POST | `/ingest/bookmark` | `x-extension-token` | bookmark export |
| POST | `/ingest/esp32` | `x-esp32-token` | ESP32 device |

## Layout

```
keep/
├── app/
│   ├── main.py          # FastAPI entrypoint
│   ├── config.py        # settings (env-driven)
│   ├── schemas.py       # Pydantic models
│   ├── db/
│   │   ├── models.py    # SQLAlchemy ORM (items table)
│   │   └── session.py   # engine + session
│   └── routers/
│       ├── webhook.py   # /webhook (Odyssey)
│       └── ingest.py    # /ingest/* (extension/esp32)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## See also

- `../llm/new-service-plan.md` — full design spec
