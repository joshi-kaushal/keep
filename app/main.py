import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.db.models import Base
from app.db.session import engine
from app.routers import webhook, ingest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema ensured.")
    yield


app = FastAPI(title="keep", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(webhook.router)
app.include_router(ingest.router)
