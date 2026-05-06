import os
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import OUTPUT_DIR, TEMPLATES_DIR, LOG_PATH
from app.database import create_tables
from app.routers.api import router


if getattr(sys, "frozen", False):
    resource_base = sys._MEIPASS
else:
    resource_base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

static_dir = os.path.join(resource_base, "static")

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(static_dir, exist_ok=True)

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger().addHandler(logging.StreamHandler())

app = FastAPI(title="감리보고서 자동생성 도구", version="3.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/")
async def root():
    index_path = os.path.join(static_dir, "index.html")
    if not os.path.exists(index_path):
        return {"status": "running", "ui": "not found"}
    return FileResponse(index_path)


app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.on_event("startup")
async def startup() -> None:
    await create_tables()
