import json
import logging
import os
import re
import sys

from app.database import get_db


logger = logging.getLogger(__name__)


class LawService:
    def __init__(self):
        if getattr(sys, "frozen", False):
            resource_base = sys._MEIPASS
        else:
            resource_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

        synonyms_path = os.path.join(resource_base, "data", "synonyms.json")
        try:
            with open(synonyms_path, encoding="utf-8") as f:
                self.synonyms: dict[str, list[str]] = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.synonyms = {}

    def _sanitize_fts(self, term: str) -> str:
        cleaned = re.sub(r'["\'*()[\]{}\:^~\-+]', " ", term).strip()
        return cleaned

    def expand_keywords(self, query: str) -> list[str]:
        tokens = query.split()
        result: list[str] = []
        seen: set[str] = set()

        for token in tokens:
            clean = self._sanitize_fts(token)
            if clean and clean not in seen:
                result.append(clean)
                seen.add(clean)
            for syn in self.synonyms.get(token, []):
                s = self._sanitize_fts(syn)
                if s and s not in seen:
                    result.append(s)
                    seen.add(s)
        return result[:10]

    async def search(self, query: str, limit: int) -> list[dict]:
        keywords = self.expand_keywords(query)
        if not keywords:
            return []

        match_expr = " OR ".join(f'"{kw}"' for kw in keywords)
        sql = """
            SELECT lc.row_id, lc.id, lc.title, lc.article_no, lc.article, lc.category,
                   bm25(laws_fts) AS bm25_rank
            FROM laws_fts
            JOIN laws_cache lc ON lc.row_id = laws_fts.rowid
            WHERE laws_fts MATCH ?
            ORDER BY bm25_rank
            LIMIT ?
        """
        try:
            async with get_db() as db:
                async with db.execute(sql, (match_expr, limit)) as cursor:
                    rows = await cursor.fetchall()
        except Exception as exc:
            logger.warning("FTS5 search failed: %s", exc)
            return []

        kw_lower = [k.lower() for k in keywords]
        results = []
        for row in rows:
            score = float(abs(row["bm25_rank"]))
            if any(k in row["title"].lower() for k in kw_lower):
                score += 0.3
            if any(k in row["category"].lower() for k in kw_lower):
                score += 0.2
            results.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "article_no": row["article_no"],
                    "category": row["category"],
                    "preview": row["article"][:120],
                    "score": score,
                }
            )
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    async def search_fallback(self, query: str, limit: int) -> list[dict]:
        for word in query.split():
            results = await self.search(word, limit)
            if results:
                return results

        async with get_db() as db:
            async with db.execute(
                "SELECT id, title, article_no, article, category FROM laws_cache ORDER BY row_id DESC LIMIT ?",
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "article_no": r["article_no"],
                "category": r["category"],
                "preview": r["article"][:120],
                "score": 0.0,
            }
            for r in rows
        ]
