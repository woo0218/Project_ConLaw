import logging
import os
import re
import xml.etree.ElementTree as ET
from typing import Iterable
import urllib.parse

import requests

from app.config import LAW_API_BASE, LAW_API_OC


logger = logging.getLogger(__name__)


class LawApiService:
    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout
        self._last_response_text = ""
        self._logged_zero_article_tags = False

    def search_laws(self, query: str, display: int = 100, page: int = 1) -> list[dict]:
        params = {
            "OC": LAW_API_OC,
            "target": "eflaw",
            "type": "XML",
            "query": query,
            "display": display,
            "page": page,
        }
        root = self._get_xml(f"{LAW_API_BASE}/lawSearch.do", params)
        laws: list[dict] = []
        seen_ids: set[str] = set()

        for elem in root.iter():
            law_id = self._first_child_text(elem, ("법령ID",))
            mst = self._first_child_text(elem, ("MST", "mst", "법령일련번호"))
            id_value = self._first_child_text(elem, ("ID", "id"))
            detail_link = self._first_child_text(elem, ("법령상세링크",))
            title = self._first_child_text(elem, ("법령명한글", "법령명", "현행법령명", "법령약칭명"))
            unique_id = law_id or mst or id_value
            if not unique_id or unique_id in seen_ids:
                continue
            seen_ids.add(unique_id)
            laws.append(
                {
                    "law_id": law_id,
                    "mst": mst,
                    "id": id_value,
                    "detail_link": detail_link,
                    "title": title,
                }
            )

        return laws

    def fetch_law_articles(
        self,
        law_id: str,
        fallback_title: str = "",
        id_param: str = "ID",
        detail_params: dict | None = None,
    ) -> list[dict]:
        params = {
            "OC": LAW_API_OC,
            "target": "eflaw",
            "type": "XML",
        }
        if detail_params:
            params.update(detail_params)
            params["OC"] = LAW_API_OC
            params.setdefault("target", "eflaw")
            params.setdefault("type", "XML")
        else:
            params[id_param] = law_id

        root = self._get_xml(f"{LAW_API_BASE}/lawService.do", params)
        title = self._find_first_text(root, ("법령명한글", "법령명", "현행법령명", "법령약칭명")) or fallback_title
        category = self._find_first_text(root, ("소관부처명", "법종구분", "법령구분명", "제개정구분명"))

        articles: list[dict] = []
        for article_elem in self._article_elements(root):
            article_no = self._first_child_text(article_elem, ("조문번호", "조번호", "가지번호", "조문가지번호"))
            article_text = self._normalize_article_text(article_elem)

            if not article_no or not article_text:
                continue

            normalized_article_no = self.normalize_article_no(article_no)
            if not normalized_article_no:
                continue

            articles.append(
                {
                    "law_id": f"{law_id}_{normalized_article_no}",
                    "title": title or "",
                    "article_no": article_no,
                    "article": article_text,
                    "category": category or "",
                    "source_law_id": law_id,
                }
            )

        return articles

    def fetch_articles_for_query(self, query: str) -> tuple[list[dict], list[dict]]:
        laws = self.search_laws(query)
        articles: list[dict] = []

        for law in laws:
            law_articles = self._fetch_articles_for_law(law)
            articles.extend(law_articles)

        return laws, articles

    def _fetch_articles_for_law(self, law: dict) -> list[dict]:
        law_id = law.get("law_id", "")
        mst = law.get("mst", "")
        id_value = law.get("id", "")
        detail_link = law.get("detail_link", "")
        fallback_title = law.get("title", "")
        candidates = self._detail_candidates(law)
        first_detail_response = ""
        last_root: ET.Element | None = None

        for candidate in candidates:
            try:
                articles = self.fetch_law_articles(
                    candidate["value"],
                    fallback_title,
                    candidate["param"],
                    candidate.get("params"),
                )
                if not first_detail_response:
                    first_detail_response = self._last_response_text
                if articles:
                    return articles
                last_root = self._last_xml_root
            except requests.RequestException as exc:
                logger.warning("법령 상세 조회 실패: %s, %s", self._masked_identifiers(law), exc)
            except ET.ParseError as exc:
                logger.warning("법령 상세 XML 파싱 실패: %s, %s", self._masked_identifiers(law), exc)
            except RuntimeError as exc:
                logger.warning("법령 상세 XML 처리 실패: %s, %s", self._masked_identifiers(law), exc)

        if first_detail_response:
            os.makedirs("data", exist_ok=True)
            debug_path = os.path.join("data", "last_law_detail_response.xml")
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(first_detail_response)

        if last_root is not None and not self._logged_zero_article_tags:
            self._logged_zero_article_tags = True
            logger.warning("법령 상세 XML 태그 목록: %s", self._tag_names(last_root))

        if candidates:
            logger.warning(
                "법령 상세 응답에서 조문을 찾지 못했습니다: identifiers=%s candidates=%s",
                self._masked_identifiers(law),
                self._masked_candidates(candidates),
            )
        elif law_id or mst or id_value or detail_link:
            logger.warning("법령 상세 조회 후보를 만들지 못했습니다: identifiers=%s", self._masked_identifiers(law))

        return []

    def _detail_candidates(self, law: dict) -> list[dict]:
        candidates: list[dict] = []
        law_id = law.get("law_id", "")
        mst = law.get("mst", "")
        detail_link = law.get("detail_link", "")

        if law_id:
            candidates.append({"param": "ID", "value": law_id})
        if mst:
            candidates.append({"param": "MST", "value": mst})

        link_params = self._params_from_detail_link(detail_link)
        if link_params:
            value = link_params.get("ID") or link_params.get("MST") or link_params.get("id") or link_params.get("mst") or "detail_link"
            candidates.append({"param": "detail_link", "value": value, "params": link_params})

        return candidates

    def _params_from_detail_link(self, detail_link: str) -> dict:
        if not detail_link:
            return {}
        parsed = urllib.parse.urlparse(detail_link)
        query = parsed.query or detail_link.partition("?")[2]
        raw_params = urllib.parse.parse_qs(query, keep_blank_values=False)
        params: dict[str, str] = {}
        for key, values in raw_params.items():
            if not values:
                continue
            params[key] = values[0]
        return params

    def _get_xml(self, url: str, params: dict) -> ET.Element:
        headers = {
            "User-Agent": "ConLawReportSeeder/1.0",
        }
        response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        response_text = response.text.strip()
        self._last_response_text = response_text

        try:
            root = ET.fromstring(response_text)
            self._last_xml_root = root
            return root
        except ET.ParseError as exc:
            os.makedirs("data", exist_ok=True)
            debug_path = os.path.join("data", "last_law_api_response.xml")
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(response_text)

            safe_params = dict(params)
            if "OC" in safe_params:
                safe_params["OC"] = "***"

            logger.warning(
                "법제처 API XML 파싱 실패: url=%s params=%s status=%s content_type=%s preview=%s error=%s",
                url,
                safe_params,
                response.status_code,
                content_type,
                response_text[:300],
                exc,
            )
            raise RuntimeError(
                "법제처 API 응답 XML 파싱에 실패했습니다. data/last_law_api_response.xml 파일을 확인하십시오."
            )

    def _article_elements(self, root: ET.Element) -> Iterable[ET.Element]:
        for elem in root.iter():
            tag = self._local_tag(elem.tag)
            if tag in ("조문단위", "조문", "Article"):
                yield elem

    def _normalize_article_text(self, article_elem: ET.Element) -> str:
        values: list[str] = []
        preferred_tags = (
            "조문제목",
            "조문내용",
            "항",
            "항내용",
            "호",
            "호내용",
            "목",
            "목내용",
            "조문참고자료",
        )

        for elem in article_elem.iter():
            tag = self._local_tag(elem.tag)
            if tag not in preferred_tags:
                continue
            text = self._clean_text(elem.text or "")
            if text:
                values.append(text)

        if not values:
            for text in article_elem.itertext():
                cleaned = self._clean_text(text)
                if cleaned:
                    values.append(cleaned)

        return "\n".join(self._dedupe(values))

    def _find_first_text(self, root: ET.Element, names: tuple[str, ...]) -> str:
        for elem in root.iter():
            if self._local_tag(elem.tag) in names:
                text = self._clean_text(elem.text or "")
                if text:
                    return text
        return ""

    def _first_child_text(self, elem: ET.Element, names: tuple[str, ...]) -> str:
        for child in elem:
            if self._local_tag(child.tag) in names:
                text = self._clean_text(child.text or "")
                if text:
                    return text
        return ""

    def _local_tag(self, tag: str) -> str:
        if "}" in tag:
            return tag.rsplit("}", 1)[1]
        return tag

    def _clean_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _dedupe(self, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value in seen:
                continue
            result.append(value)
            seen.add(value)
        return result

    def _tag_names(self, root: ET.Element) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for elem in root.iter():
            tag = self._local_tag(elem.tag)
            if tag in seen:
                continue
            seen.add(tag)
            names.append(tag)
        return names

    def _masked_identifiers(self, law: dict) -> dict:
        return {
            "law_id": law.get("law_id", ""),
            "mst": law.get("mst", ""),
            "id": law.get("id", ""),
            "detail_link": self._mask_oc_in_text(law.get("detail_link", "")),
            "title": law.get("title", ""),
        }

    def _masked_candidates(self, candidates: list[dict]) -> list[dict]:
        masked: list[dict] = []
        for candidate in candidates:
            item = dict(candidate)
            params = item.get("params")
            if isinstance(params, dict):
                safe_params = dict(params)
                if "OC" in safe_params:
                    safe_params["OC"] = "***"
                item["params"] = safe_params
            masked.append(item)
        return masked

    def _mask_oc_in_text(self, text: str) -> str:
        if not text or LAW_API_OC not in text:
            return text
        return text.replace(LAW_API_OC, "***")

    @staticmethod
    def normalize_article_no(article_no: str) -> str:
        cleaned = re.sub(r"\s+", "", article_no)
        cleaned = re.sub(r"[^0-9A-Za-z가-힣_-]", "_", cleaned)
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        return cleaned
