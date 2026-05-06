import os
import json
import uuid
import urllib.parse
import logging

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import OUTPUT_DIR, TEMPLATES_DIR
from app.database import get_db
from app.services.validator import validate_template
from app.services.law import LawService
from app.services.llm import LLMService
from app.services.docx import DocxService
from app.services.law_seed import get_seed_status


logger = logging.getLogger(__name__)
router = APIRouter()

law_service = LawService()
llm_service = LLMService()
docx_service = DocxService()


class RecommendRequest(BaseModel):
    law_ids: list[str]
    context: str


class GenerateRequest(BaseModel):
    template_id: str
    law_id: str
    user_input: str


async def _get_law_or_404(law_id: str) -> dict:
    async with get_db() as db:
        async with db.execute(
            """
            SELECT id, title, article_no, article, category
            FROM laws_cache
            WHERE id = ?
            """,
            (law_id,),
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        raise HTTPException(404, "법령을 찾을 수 없습니다.")

    return {
        "id": row["id"],
        "title": row["title"],
        "article_no": row["article_no"],
        "article": row["article"],
        "category": row["category"],
    }


async def _get_laws_by_ids(law_ids: list[str]) -> list[dict]:
    laws: list[dict] = []
    seen: set[str] = set()

    for law_id in law_ids:
        if law_id in seen:
            continue
        seen.add(law_id)
        laws.append(await _get_law_or_404(law_id))

    return laws


async def _get_template_or_404(template_id: str) -> dict:
    async with get_db() as db:
        async with db.execute(
            """
            SELECT id, filename, placeholders
            FROM templates
            WHERE id = ?
            """,
            (template_id,),
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        raise HTTPException(404, "템플릿을 찾을 수 없습니다.")

    try:
        placeholders = json.loads(row["placeholders"])
    except json.JSONDecodeError:
        logger.warning("템플릿 placeholder JSON 파싱 실패: %s", template_id)
        placeholders = []

    if not isinstance(placeholders, list):
        placeholders = []

    return {
        "id": row["id"],
        "filename": row["filename"],
        "placeholders": [str(item) for item in placeholders],
    }


def _fallback_report_sections(law: dict, user_input: str, placeholders: list[str]) -> dict[str, str]:
    title = str(law.get("title") or "").strip()
    article_no = str(law.get("article_no") or "").strip()
    law_basis = " ".join(part for part in (title, article_no) if part)
    context = user_input.strip()
    sections = {
        "{{현장상황}}": context,
        "{{종합의견}}": (
            f"{context} 위 사항은 {law_basis} 등 관련 기준에 따른 검토가 필요한 사항으로, "
            "설계도서와의 일치 여부 및 구조 안전성 확보 여부를 확인하여야 합니다. "
            "시공자는 보완 시공계획과 검측자료를 제출하고, 조치 완료 후 감리자의 재확인을 받아야 합니다."
        ),
        "{{기타사항}}": (
            f"법령 근거: {law_basis}. "
            "후속 확인자료로 보완 시공 전후 사진, 검측기록, 관련 구조 검토자료를 확보할 필요가 있습니다."
        ),
        "{{감리의견}}": (
            f"{law_basis}를 근거로 현장 지적 사항에 대한 시정 필요성을 검토하였습니다."
        ),
        "{{시정요구사항}}": (
            "설계도서 및 관련 기준에 맞도록 보완하고, 시정 완료 후 확인자료를 제출하여야 합니다."
        ),
    }
    return {key: value for key, value in sections.items() if key in placeholders and value}


@router.post("/template/upload")
async def upload_template(file: UploadFile = File(...)) -> dict:
    filename = file.filename or ""
    file_bytes = await file.read()
    placeholders = await run_in_threadpool(validate_template, filename, file_bytes)

    template_id = str(uuid.uuid4())
    stored_filename = f"{template_id}.docx"
    output_path = os.path.join(TEMPLATES_DIR, stored_filename)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(file_bytes)

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO templates (id, filename, placeholders)
            VALUES (?, ?, ?)
            """,
            (template_id, stored_filename, json.dumps(placeholders, ensure_ascii=False)),
        )
        await db.commit()

    return {
        "template_id": template_id,
        "filename": stored_filename,
        "original_filename": filename,
        "placeholders": placeholders,
    }


@router.get("/laws/search")
async def search_laws(q: str = "", limit: int = 10) -> list[dict]:
    clean_query = q.strip()
    if not clean_query:
        return []

    safe_limit = max(1, min(limit, 50))
    return await law_service.search_fallback(clean_query, safe_limit)


@router.get("/laws/seed/status")
async def law_seed_status() -> dict:
    return await get_seed_status()


@router.post("/laws/recommend")
async def recommend_laws(request: RecommendRequest) -> list[dict]:
    if not request.law_ids:
        raise HTTPException(400, "추천할 법령을 선택하십시오.")
    if not request.context.strip():
        raise HTTPException(400, "상황 설명을 입력하십시오.")

    laws = await _get_laws_by_ids(request.law_ids)
    return await run_in_threadpool(llm_service.recommend, laws, request.context)


@router.get("/laws/{law_id}")
async def get_law(law_id: str) -> dict:
    return await _get_law_or_404(law_id)


@router.post("/report/generate")
async def generate_report(request: GenerateRequest) -> dict:
    if not request.user_input.strip():
        raise HTTPException(400, "보고서 작성 내용을 입력하십시오.")

    template = await _get_template_or_404(request.template_id)
    law = await _get_law_or_404(request.law_id)
    template_path = os.path.join(TEMPLATES_DIR, template["filename"])

    if not os.path.exists(template_path):
        raise HTTPException(404, "파일을 찾을 수 없습니다.")

    with open(template_path, "rb") as f:
        template_bytes = f.read()

    try:
        llm_sections = await run_in_threadpool(
            llm_service.generate_report_sections,
            law,
            request.user_input,
            template["placeholders"],
        )
    except HTTPException as exc:
        if exc.status_code not in (503, 504):
            raise
        logger.warning("LLM 보고서 문안 생성 실패, 기본 문안으로 보고서를 생성합니다: %s", exc.detail)
        llm_sections = _fallback_report_sections(law, request.user_input, template["placeholders"])
    report_bytes, unmatched = await run_in_threadpool(
        docx_service.fill_template,
        template_bytes,
        law,
        llm_sections,
    )

    report_id = str(uuid.uuid4())
    output_filename = f"감리보고서_{report_id[:8]}.docx"
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(report_bytes)

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO reports (id, template_id, law_id, user_input, output_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            (report_id, request.template_id, request.law_id, request.user_input, output_path),
        )
        await db.commit()

    return {
        "report_id": report_id,
        "filename": output_filename,
        "download_url": f"/report/{report_id}/download",
        "unmatched_placeholders": unmatched,
    }


@router.get("/report/{report_id}/download")
async def download_report(report_id: str) -> FileResponse:
    async with get_db() as db:
        async with db.execute(
            """
            SELECT output_path
            FROM reports
            WHERE id = ?
            """,
            (report_id,),
        ) as cursor:
            row = await cursor.fetchone()

    if row is None or not os.path.exists(row["output_path"]):
        raise HTTPException(404, "파일을 찾을 수 없습니다.")

    filename = os.path.basename(row["output_path"])
    encoded_filename = urllib.parse.quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
    }
    return FileResponse(
        row["output_path"],
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )
