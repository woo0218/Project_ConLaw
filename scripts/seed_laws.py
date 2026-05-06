import asyncio
import logging
import os
import sqlite3
import sys


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.database import create_tables, get_db
from app.services.law_api import LawApiService


logger = logging.getLogger(__name__)


async def seed_articles(articles: list[dict]) -> tuple[int, int]:
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
                logger.warning("법령 조항 저장 실패: %s, %s", law_id, exc)

    return inserted, skipped


async def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    if len(sys.argv) < 2:
        print("사용법: python scripts/seed_laws.py 자동차관리법")
        raise SystemExit(1)

    query = " ".join(sys.argv[1:]).strip()
    if not query:
        print("검색어를 입력하십시오.")
        raise SystemExit(1)

    await create_tables()

    service = LawApiService()
    laws, articles = service.fetch_articles_for_query(query)
    inserted, skipped = await seed_articles(articles)

    print(f"query: {query}")
    print(f"laws fetched: {len(laws)}")
    print(f"articles inserted: {inserted}")
    print(f"articles skipped: {skipped}")


if __name__ == "__main__":
    asyncio.run(main())
