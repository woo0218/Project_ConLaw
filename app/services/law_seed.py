import asyncio
import logging
import sqlite3

from app.config import (
    AUTO_SEED_CONSTRUCTION_LAWS,
    AUTO_SEED_MIN_LAW_ROWS,
    CONSTRUCTION_LAW_QUERIES,
)
from app.database import get_db
from app.services.law_api import LawApiService


logger = logging.getLogger(__name__)

_status_lock = asyncio.Lock()
_seed_status: dict = {
    "enabled": AUTO_SEED_CONSTRUCTION_LAWS,
    "running": False,
    "done": False,
    "total_queries": len(CONSTRUCTION_LAW_QUERIES),
    "completed_queries": 0,
    "current_query": "",
    "inserted": 0,
    "skipped": 0,
    "pending_queries": [],
    "skipped_queries": [],
    "errors": [],
    "message": "법령 데이터 준비 상태를 확인 중입니다.",
}


async def get_seed_status() -> dict:
    async with _status_lock:
        status = dict(_seed_status)
        status["errors"] = list(_seed_status["errors"])
        status["pending_queries"] = list(_seed_status["pending_queries"])
        status["skipped_queries"] = list(_seed_status["skipped_queries"])
        return status


async def _update_status(**kwargs) -> None:
    async with _status_lock:
        _seed_status.update(kwargs)


async def _append_error(message: str) -> None:
    async with _status_lock:
        errors = list(_seed_status["errors"])
        errors.append(message)
        _seed_status["errors"] = errors[-10:]


async def _increment_status(inserted: int = 0, skipped: int = 0, completed_queries: int = 0) -> None:
    async with _status_lock:
        _seed_status["inserted"] += inserted
        _seed_status["skipped"] += skipped
        _seed_status["completed_queries"] += completed_queries


async def count_law_rows() -> int:
    try:
        async with get_db() as db:
            async with db.execute("SELECT COUNT(*) FROM laws_cache") as cursor:
                row = await cursor.fetchone()
        return int(row[0]) if row else 0
    except Exception as exc:
        logger.warning("법령 데이터 개수 확인 실패: %s", exc)
        return 0


async def count_rows_for_query(query: str) -> int:
    try:
        async with get_db() as db:
            async with db.execute(
                "SELECT COUNT(*) FROM laws_cache WHERE title LIKE ?",
                (f"%{query}%",),
            ) as cursor:
                row = await cursor.fetchone()
        return int(row[0]) if row else 0
    except Exception as exc:
        logger.warning("법령별 데이터 개수 확인 실패: %s, %s", query, exc)
        return 0


async def get_seed_plan() -> dict:
    pending_queries: list[str] = []
    skipped_queries: list[str] = []
    existing_rows = 0

    for query in CONSTRUCTION_LAW_QUERIES:
        row_count = await count_rows_for_query(query)
        if row_count > 0:
            skipped_queries.append(query)
            existing_rows += row_count
        else:
            pending_queries.append(query)

    return {
        "pending_queries": pending_queries,
        "skipped_queries": skipped_queries,
        "existing_rows": existing_rows,
        "total_queries": len(CONSTRUCTION_LAW_QUERIES),
        "completed_queries": len(skipped_queries),
    }


async def seed_articles_for_query(query: str) -> tuple[int, int]:
    service = LawApiService()
    _laws, articles = await asyncio.to_thread(service.fetch_articles_for_query, query)
    inserted = 0
    skipped = 0

    async with get_db() as db:
        for article in articles:
            law_id = article.get("law_id", "")
            title = article.get("title", "")
            article_no = article.get("article_no", "")
            article_text = article.get("article", "")
            category = article.get("category", "")

            if not law_id or not title or not article_no or not article_text:
                skipped += 1
                continue

            try:
                await db.execute(
                    "INSERT INTO laws_cache (id, title, article_no, article, category) VALUES (?,?,?,?,?)",
                    (law_id, title, article_no, article_text, category),
                )
                cur = await db.execute("SELECT last_insert_rowid()")
                row = await cur.fetchone()
                fts_rowid = row[0]
                await db.execute(
                    "INSERT INTO laws_fts (rowid, title, article) VALUES (?,?,?)",
                    (fts_rowid, title, article_text),
                )
                await db.commit()
                inserted += 1
            except sqlite3.IntegrityError:
                await db.rollback()
                skipped += 1
            except Exception as exc:
                await db.rollback()
                skipped += 1
                logger.warning("자동 법령 조항 저장 실패: %s, %s", law_id, exc)

    return inserted, skipped


async def ensure_construction_laws_seeded() -> None:
    try:
        async with _status_lock:
            if _seed_status["running"]:
                return
            if not AUTO_SEED_CONSTRUCTION_LAWS:
                _seed_status.update(
                    {
                        "enabled": False,
                        "running": False,
                        "done": True,
                        "message": "자동 법령 적재가 비활성화되어 있습니다.",
                    }
                )
                return
            _seed_status.update(
                {
                    "enabled": True,
                    "running": True,
                    "done": False,
                    "total_queries": len(CONSTRUCTION_LAW_QUERIES),
                    "completed_queries": 0,
                    "current_query": "",
                    "inserted": 0,
                    "skipped": 0,
                    "pending_queries": [],
                    "skipped_queries": [],
                    "errors": [],
                    "message": "건설 관련 법령 데이터 준비 대상을 확인 중입니다.",
                }
            )

        plan = await get_seed_plan()
        if not plan["pending_queries"]:
            await _update_status(
                running=False,
                done=True,
                current_query="",
                total_queries=plan["total_queries"],
                completed_queries=plan["total_queries"],
                skipped=plan["existing_rows"] or len(plan["skipped_queries"]),
                pending_queries=[],
                skipped_queries=plan["skipped_queries"],
                message="건설 관련 법령 데이터가 이미 준비되어 있습니다.",
            )
            return

        await _update_status(
            running=True,
            done=False,
            total_queries=plan["total_queries"],
            completed_queries=plan["completed_queries"],
            pending_queries=plan["pending_queries"],
            skipped_queries=plan["skipped_queries"],
            skipped=len(plan["skipped_queries"]),
            message="건설 관련 법령 데이터를 준비 중입니다.",
        )

        for index, query in enumerate(plan["pending_queries"]):
            await _update_status(
                current_query=query,
                pending_queries=plan["pending_queries"][index:],
                message="법령 데이터를 준비 중입니다.",
            )
            try:
                inserted, skipped = await seed_articles_for_query(query)
                await _increment_status(inserted=inserted, skipped=skipped, completed_queries=1)
            except Exception as exc:
                logger.warning("자동 법령 적재 실패: %s, %s", query, exc)
                await _append_error(f"{query}: {exc}")
                await _increment_status(completed_queries=1)
            await _update_status(pending_queries=plan["pending_queries"][index + 1 :])

        await _update_status(
            running=False,
            done=True,
            current_query="",
            pending_queries=[],
            message="건설 관련 법령 데이터 준비가 완료되었습니다.",
        )
    except Exception as exc:
        logger.warning("자동 법령 적재 작업 실패: %s", exc)
        await _append_error(str(exc))
        await _update_status(
            running=False,
            done=True,
            current_query="",
            message="법령 데이터 준비 중 오류가 발생했습니다.",
        )
