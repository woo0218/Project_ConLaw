import os
import sys
import urllib.parse


if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


ENV_PATH = os.path.join(BASE_DIR, ".env")
if os.path.exists(ENV_PATH):
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set. Set it in .env or as an environment variable.")


DB_PATH = os.path.join(BASE_DIR, "data", "app.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
TEMPLATES_DIR = os.path.join(BASE_DIR, "data", "templates")
LOG_PATH = os.path.join(BASE_DIR, "data", "app.log")
APP_HOST = "127.0.0.1"
APP_PORT: int = 8000


LAW_API_BASE = "https://www.law.go.kr/DRF"
LAW_API_OC = os.getenv("LAW_API_OC", "")
if not LAW_API_OC:
    raise RuntimeError("LAW_API_OC is not set. Set it in .env or as an environment variable.")
LAW_API_TYPE = "XML"


OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
LLM_TEMPERATURE: float = 0.0
LLM_MAX_TOKENS_RECOMMEND: int = 400
LLM_MAX_TOKENS_GENERATE: int = 1200
LLM_TIMEOUT_SEC: int = 30
LLM_RETRY_COUNT: int = 1


REQUIRED_PLACEHOLDERS: list[str] = ["{{법령근거}}", "{{조항번호}}"]

AUTO_SEED_CONSTRUCTION_LAWS: bool = os.getenv("AUTO_SEED_CONSTRUCTION_LAWS", "1") == "1"
AUTO_SEED_MIN_LAW_ROWS: int = int(os.getenv("AUTO_SEED_MIN_LAW_ROWS", "200"))
CONSTRUCTION_LAW_QUERIES: list[str] = [
    "건설기술 진흥법",
    "건설기술 진흥법 시행령",
    "건설기술 진흥법 시행규칙",
    "건축법",
    "건축법 시행령",
    "건축법 시행규칙",
    "건설산업기본법",
    "건설산업기본법 시행령",
    "주택법",
    "주택법 시행령",
    "시설물의 안전 및 유지관리에 관한 특별법",
    "시설물의 안전 및 유지관리에 관한 특별법 시행령",
    "산업안전보건법",
    "산업안전보건법 시행령",
    "중대재해 처벌 등에 관한 법률",
    "중대재해 처벌 등에 관한 법률 시행령",
    "국토의 계획 및 이용에 관한 법률",
    "소방시설 설치 및 관리에 관한 법률",
    "전기안전관리법",
    "승강기 안전관리법",
    "건설폐기물의 재활용촉진에 관한 법률",
    "환경영향평가법",
]


def law_search_url(query: str, page: int = 1, display: int = 100) -> str:
    params = {
        "OC": LAW_API_OC,
        "target": "eflaw",
        "type": LAW_API_TYPE,
        "query": query,
        "page": page,
        "display": display,
    }
    return LAW_API_BASE + "/lawSearch.do?" + urllib.parse.urlencode(params)


def law_detail_url(law_id: str) -> str:
    params = {"OC": LAW_API_OC, "target": "eflaw", "type": LAW_API_TYPE, "ID": law_id}
    return LAW_API_BASE + "/lawService.do?" + urllib.parse.urlencode(params)
