import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from .db import Base, SessionLocal, engine
from .models import ROOT_CAUSE_CATEGORIES, STATUSES
from .routers import auth, incidents, teams
from .seed import seed

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    for attempt in range(30):  # wait for Postgres
        try:
            Base.metadata.create_all(engine)
            break
        except OperationalError:
            time.sleep(2)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="InfraWatch API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router, prefix="/api")
app.include_router(teams.router, prefix="/api")
app.include_router(incidents.router, prefix="/api")


@app.get("/api/meta")
def meta():
    return {"statuses": STATUSES, "root_cause_categories": ROOT_CAUSE_CATEGORIES}


@app.get("/api/health")
def health():
    return {"ok": True}
