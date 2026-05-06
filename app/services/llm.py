import json
import logging
from typing import Any

from fastapi import HTTPException
from openai import APIError, APITimeoutError, OpenAI, RateLimitError

from app.config import (
    LLM_MAX_TOKENS_GENERATE,
    LLM_MAX_TOKENS_RECOMMEND,
    LLM_RETRY_COUNT,
    LLM_TEMPERATURE,
    LLM_TIMEOUT_SEC,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    REQUIRED_PLACEHOLDERS,
)


client = OpenAI(api_key=OPENAI_API_KEY, timeout=LLM_TIMEOUT_SEC)

logger = logging.getLogger(__name__)


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        if text.endswith("```"):
            text = text[: -3]
    return text.strip()


class LLMService:
    def __init__(self) -> None:
        self._required_placeholders = set(REQUIRED_PLACEHOLDERS)

    def _call_llm(self, prompt: str, max_tokens: int) -> str:
        last_error: Exception | None = None
        for attempt in range(LLM_RETRY_COUNT + 1):
            try:
                response = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "당신은 한국어 공공 문서와 건설공사 감리 문서를 정확하게 작성하는 전문가입니다.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=LLM_TEMPERATURE,
                    max_tokens=max_tokens,
                )
                if not response.choices:
                    raise HTTPException(503, "AI 서비스에 일시적인 오류가 발생했습니다.")

                text = response.choices[0].message.content
                if not text:
                    raise HTTPException(503, "AI 서비스에 일시적인 오류가 발생했습니다.")

                return _strip_markdown_fences(text)
            except HTTPException:
                raise
            except APITimeoutError:
                raise HTTPException(504, "AI 응답 시간이 초과되었습니다. 다시 시도하십시오.")
            except RateLimitError:
                raise HTTPException(503, "AI 사용량 한도를 초과했습니다. 잠시 후 다시 시도하십시오.")
            except APIError as exc:
                last_error = exc
                logger.warning("OpenAI API 호출 실패 (시도 %s/%s): %s", attempt + 1, LLM_RETRY_COUNT + 1, exc)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning("OpenAI 호출 실패 (시도 %s/%s): %s", attempt + 1, LLM_RETRY_COUNT + 1, exc)
        logger.error("OpenAI 호출 반복 실패: %s", last_error)
        raise HTTPException(503, "AI 서비스에 일시적인 오류가 발생했습니다.")

    def _safe_json_loads(self, text: str) -> Any:
        cleaned = _strip_markdown_fences(text)
        return json.loads(cleaned)

    def recommend(self, laws: list[dict], context: str) -> list[dict]:
        laws_payload = [
            {
                "id": law.get("id"),
                "title": law.get("title"),
                "article_no": law.get("article_no"),
                "category": law.get("category"),
                "article": law.get("article") or law.get("preview"),
            }
            for law in laws
        ]

        prompt = (
            "당신은 건설공사 감리 분야의 최고 전문가입니다.\n"
            "아래 제공된 법령 조항 목록과 사용자의 상황 설명을 바탕으로,\n"
            "보고서에 인용하기에 가장 적절한 법령 조항들을 JSON 배열 형식으로 추천해 주세요.\n"
            "- 각 항목은 원본 입력의 id, title, article_no, category, article 필드를 유지해야 합니다.\n"
            "- 필요하다고 판단되는 조항만 포함하고, 최대 10개 이내로 제한합니다.\n"
            "- 반드시 순수 JSON만 출력하고, 설명 문장은 포함하지 마십시오.\n"
            "\n"
            f"[사용자 상황]\n{context}\n\n"
            "[법령 목록]\n"
            f"{json.dumps(laws_payload, ensure_ascii=False, indent=2)}\n"
        )

        text = self._call_llm(prompt, max_tokens=LLM_MAX_TOKENS_RECOMMEND)

        for attempt in range(2):
            try:
                data = self._safe_json_loads(text)
                if isinstance(data, dict):
                    return [data]
                if isinstance(data, list):
                    return [x for x in data if isinstance(x, dict)]
                raise ValueError("JSON이 dict 또는 list 형식이 아닙니다.")
            except Exception as exc:  # noqa: BLE001
                logger.warning("추천 JSON 파싱 실패 (시도 %s/2): %s", attempt + 1, exc)
                if attempt == 0:
                    text = self._call_llm(prompt, max_tokens=LLM_MAX_TOKENS_RECOMMEND)
                else:
                    raise HTTPException(500, "LLM 응답 오류. 다시 시도하십시오.")

        raise HTTPException(500, "LLM 응답 오류. 다시 시도하십시오.")

    def generate_report_sections(
        self,
        law: dict,
        user_input: str,
        placeholders: list[str],
    ) -> dict:
        form_keys = ["{{감리의견}}", "{{시정요구사항}}", "{{종합의견}}", "{{기타사항}}"]
        is_form_template = all(key in placeholders for key in form_keys) and "{{현장상황}}" in placeholders
        narrative_keys = [
            p
            for p in placeholders
            if p not in self._required_placeholders
        ]
        if is_form_template:
            narrative_keys = ["{{종합의견}}", "{{기타사항}}"]
        if not narrative_keys:
            return {}

        law_summary = {
            "id": law.get("id"),
            "title": law.get("title"),
            "article_no": law.get("article_no"),
            "category": law.get("category"),
            "article": law.get("article"),
        }

        if is_form_template:
            prompt = (
                "당신은 한국 공공기관의 건설공사 감리보고서 문안을 작성하는 실무자입니다.\n"
                "아래의 법령 조항과 사용자의 현장 설명을 바탕으로 공식 서식의 '기타사항' 및 '종합의견' 칸에 들어갈 문안만 작성하세요.\n"
                "- 출력은 반드시 JSON 객체 형식이어야 합니다.\n"
                "- 키는 반드시 {{종합의견}}, {{기타사항}}만 사용하십시오.\n"
                "- 각 값은 2~4문장 이내로 작성하십시오.\n"
                "- 사용자가 제공한 사실만 근거로 작성하고, 새로운 사실을 지어내지 마십시오.\n"
                "- 허가번호, 허가일자, 대지위치, 지번, 건축주, 서명자, 날짜, 체크박스 결과를 지어내지 마십시오.\n"
                "- 적합/부적합/해당없음 같은 판정은 사용자가 명시하지 않았다면 단정하지 마십시오.\n"
                "- 법령 원문은 변경하거나 재작성하지 마십시오.\n"
                "- 종합의견은 다음 순서로 구체화하십시오: ① 확인된 현장 지적 사실, ② 관련 기준 검토 필요성, ③ 시정 또는 보완 요구, ④ 조치 후 재확인 필요성.\n"
                "- 종합의견에는 사용자가 입력한 핵심 공종·부위·하자 내용을 가능한 한 그대로 반영하십시오.\n"
                "- 기타사항에는 선택 법령명과 조항번호, 확인해야 할 증빙자료 또는 후속 확인사항을 포함하십시오.\n"
                "- 가능한 표현 예시는 '설계도서와의 일치 여부 확인', '보완 시공계획 제출', '시정 완료 후 감리자 재확인', '사진 및 검측자료 확보'입니다.\n"
                "- 불필요한 설명이나 JSON 이외의 텍스트는 포함하지 마십시오.\n"
                "\n"
                f"[선택 법령 정보]\n{json.dumps(law_summary, ensure_ascii=False, indent=2)}\n\n"
                f"[사용자 입력]\n{user_input}\n\n"
                f"[생성해야 할 키]\n{json.dumps(narrative_keys, ensure_ascii=False)}\n"
            )
        else:
            prompt = (
                "당신은 한국 공공기관에서 사용하는 형식의 공문서·보고서를 작성하는 전문가입니다.\n"
                "아래의 법령 조항과 사용자의 설명을 참고하여, 보고서 본문에 들어갈 서술형 문단들을 생성하세요.\n"
                "- 출력은 반드시 JSON 객체 형식이어야 합니다.\n"
                "- 키는 아래에 제시된 placeholder 문자열 그대로 사용하십시오.\n"
                "- 각 값은 공무원 보고서 어투의 완성된 한국어 문단(또는 문단들의 문자열)이어야 합니다.\n"
                "- 불필요한 설명이나 JSON 이외의 텍스트는 포함하지 마십시오.\n"
                "\n"
                f"[법령 정보]\n{json.dumps(law_summary, ensure_ascii=False, indent=2)}\n\n"
                f"[사용자 입력]\n{user_input}\n\n"
                f"[생성해야 할 placeholder 목록]\n{json.dumps(narrative_keys, ensure_ascii=False)}\n"
            )

        text = self._call_llm(prompt, max_tokens=LLM_MAX_TOKENS_GENERATE)

        for attempt in range(2):
            try:
                data = self._safe_json_loads(text)
                if not isinstance(data, dict):
                    raise ValueError("JSON이 객체 형식이 아닙니다.")
                result: dict[str, str] = {}
                for key in narrative_keys:
                    val = data.get(key)
                    if isinstance(val, (str, int, float)):
                        result[key] = str(val)
                    elif isinstance(val, list):
                        items = [str(x) for x in val if isinstance(x, (str, int, float))]
                        if items:
                            result[key] = "\n".join(items)
                return result
            except Exception as exc:  # noqa: BLE001
                logger.warning("보고서 JSON 파싱 실패 (시도 %s/2): %s", attempt + 1, exc)
                if attempt == 0:
                    text = self._call_llm(prompt, max_tokens=LLM_MAX_TOKENS_GENERATE)
                else:
                    raise HTTPException(500, "LLM 응답 오류. 다시 시도하십시오.")

        raise HTTPException(500, "LLM 응답 오류. 다시 시도하십시오.")
