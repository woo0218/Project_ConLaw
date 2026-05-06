import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import aiosqlite

from app.config import DB_PATH


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def create_tables() -> None:
    async with get_db() as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS laws_cache (
                row_id     INTEGER PRIMARY KEY,
                id         TEXT UNIQUE NOT NULL,
                title      TEXT NOT NULL,
                article_no TEXT NOT NULL,
                article    TEXT NOT NULL,
                category   TEXT NOT NULL DEFAULT '',
                updated_at DATETIME DEFAULT (datetime('now','localtime'))
            )
            """
        )
        await db.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS laws_fts
                USING fts5(title, article, tokenize='unicode61')
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS templates (
                id           TEXT PRIMARY KEY,
                filename     TEXT NOT NULL,
                placeholders TEXT NOT NULL,
                created_at   DATETIME DEFAULT (datetime('now','localtime'))
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id          TEXT PRIMARY KEY,
                template_id TEXT REFERENCES templates(id),
                law_id      TEXT REFERENCES laws_cache(id),
                user_input  TEXT NOT NULL,
                output_path TEXT NOT NULL,
                created_at  DATETIME DEFAULT (datetime('now','localtime'))
            )
            """
        )
        await db.commit()
