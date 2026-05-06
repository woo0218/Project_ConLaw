# Project_ConLaw

건설공사 감리 상황을 입력하면 관련 법령 후보를 검색하고, 선택한 법령 조문을 근거로 감리보고서 `.docx` 문안을 생성하는 로컬 웹 앱입니다. FastAPI 서버가 로컬에서 실행되고, 사용자는 브라우저 화면에서 템플릿 업로드, 법령 검색, 보고서 생성을 수행합니다.

## 주요 기능

- 법제처 Open API 법령 데이터를 SQLite DB에 적재
- FTS5 기반 법령 조문 검색
- 검색된 법령 후보의 조문 본문 확인
- 사용자가 선택한 법령을 기준으로 보고서 생성
- placeholder 기반 `.docx` 템플릿 지원
- 공식 감리보고서 표 양식 지원
- OpenAI API를 이용한 공문서 문체 문안 생성
- Windows 배포용 PyInstaller 빌드 워크플로 제공

## 구조

```text
browser UI
  -> FastAPI
  -> SQLite(data/app.db)
  -> OpenAI 문안 생성
  -> python-docx 문서 작성
  -> outputs/*.docx
```

주요 디렉터리:

```text
app/                  FastAPI 앱, 서비스, 라우터
static/               브라우저 UI
scripts/              법령 데이터 적재 스크립트
data/                 SQLite DB, 로그, 업로드 템플릿 저장 위치
data/templates/        업로드된 docx 템플릿
outputs/              생성된 감리보고서 docx
.github/workflows/    Windows exe 빌드 워크플로
```

## 환경 변수

프로젝트 루트에 `.env` 파일을 만들고 아래 값을 설정합니다. 실제 키 값은 GitHub에 올리면 안 됩니다.

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-nano
LAW_API_OC=your_law_go_kr_oc
```

`OPENAI_MODEL`은 비용을 줄여 테스트하려면 `gpt-4.1-nano`, 문안 품질을 높이려면 `gpt-4.1-mini`를 권장합니다.

```env
OPENAI_MODEL=gpt-4.1-mini
```

## 설치

Python 3.12 환경에서 테스트했습니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell에서는:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 법령 데이터 적재

앱 시작 시 DB 스키마는 자동 생성되지만, 법령 데이터는 자동으로 채워지지 않습니다. 법령 검색을 사용하려면 먼저 법제처 Open API 데이터를 적재해야 합니다.

예시:

```bash
python scripts/seed_laws.py "건설기술 진흥법"
```

필요한 법령은 여러 번 나누어 적재할 수 있습니다.

```bash
python scripts/seed_laws.py "건축법"
python scripts/seed_laws.py "건축법 시행령"
python scripts/seed_laws.py "건설기술 진흥법"
```

적재 스크립트는 법제처 현행법령 API에서 목록과 본문을 가져와 조문 단위로 저장합니다.

- `laws_cache`: 법령 조문 원문
- `laws_fts`: 검색용 FTS5 인덱스
- `templates`: 업로드된 템플릿 정보
- `reports`: 생성된 보고서 기록

## 실행

일반 실행:

```bash
python run_app.py
```

개발 실행:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

브라우저:

```text
http://127.0.0.1:8000
```

상태 확인:

```text
http://127.0.0.1:8000/health
```

API 문서:

```text
http://127.0.0.1:8000/docs
```

## 사용 흐름

1. `.env` 설정
2. 법령 데이터 적재
3. 앱 실행
4. `.docx` 템플릿 업로드
5. 현장 상황 입력
6. 법령 후보 검색
7. 후보 카드 클릭 후 조문 본문 확인
8. 사용할 법령 선택
9. 보고서 생성
10. 생성된 `.docx` 다운로드

## 템플릿 규칙

두 가지 템플릿 방식을 지원합니다.

### 1. Placeholder 템플릿

`.docx` 안에 아래 형식의 placeholder를 넣습니다.

```text
{{법령근거}}
{{조항번호}}
{{종합의견}}
{{기타사항}}
```

필수 placeholder:

```text
{{법령근거}}
{{조항번호}}
```

### 2. 공식 감리보고서 표 양식

`{{...}}` placeholder가 없는 공식 감리보고서 표 양식도 지원합니다. 이 경우 앱은 서식의 행정정보나 서명란을 임의로 채우지 않습니다.

자동 작성 대상:

```text
기타사항
종합의견
```

자동 작성하지 않는 항목:

```text
허가번호
허가일자
대지위치
지번
건축주
서명자
날짜
확인자/서명란
적합/부적합/해당없음 체크박스
```

## HWP 사용 시 주의사항

현재 앱은 `.hwp` 직접 업로드를 지원하지 않습니다. HWP 양식은 한글에서 Word 문서(`.docx`)로 저장한 뒤 업로드해야 합니다.

생성 결과도 `.docx`입니다. HWP 제출이 필요하면 생성된 `.docx`를 한글에서 열고 `.hwp`로 다시 저장하세요.

## Windows EXE 빌드

macOS에서 Windows `.exe`를 직접 안정적으로 빌드하기 어렵기 때문에 GitHub Actions의 Windows runner를 사용합니다.

빌드 절차:

1. GitHub에 push
2. GitHub 저장소의 `Actions` 탭 열기
3. `Build Windows EXE` 워크플로 실행
4. 완료 후 `MyApp-windows` artifact 다운로드
5. 압축 해제
6. `MyApp.exe` 옆에 `.env` 배치
7. `MyApp.exe` 실행

PyInstaller `onedir` 방식이므로 `MyApp.exe` 하나만 배포하면 안 됩니다. 생성된 `MyApp` 폴더 전체를 배포해야 합니다.

배포 예시:

```text
MyApp/
  MyApp.exe
  .env
  _internal/
  static/
  data/
  outputs/
```

코딩을 모르는 사용자는 `.env` 파일만 메모장으로 열어 API 키를 넣고 `MyApp.exe`를 더블클릭하면 됩니다.

## Git 업로드 전 주의사항

아래 파일과 폴더는 GitHub에 올리면 안 됩니다.

```text
.env
.venv/
data/app.db
data/app.log
data/templates/
outputs/
__pycache__/
*.pyc
```

현재 `.gitignore`에 위 항목들이 포함되어 있습니다. 업로드 전 반드시 확인하세요.

```bash
git status --short
```

`.env`가 보이면 커밋하면 안 됩니다.

## 문제 해결

검색 결과가 비어 있음:

- 법령 데이터가 아직 적재되지 않았을 수 있습니다.
- `python scripts/seed_laws.py "건설기술 진흥법"`처럼 필요한 법령을 먼저 적재하세요.
- 너무 긴 문장보다 `감리`, `철근`, `설계도서`, `품질관리` 같은 핵심 키워드가 검색에 유리합니다.

`OPENAI_API_KEY is not set` 오류:

- `.env` 파일이 프로젝트 루트 또는 exe 옆에 있는지 확인하세요.
- `OPENAI_API_KEY=...` 형식에서 따옴표와 불필요한 공백을 제거하세요.

`LAW_API_OC is not set` 오류:

- `.env`에 법제처 Open API OC 값을 넣어야 합니다.

법제처 API가 HTML 오류 페이지를 반환함:

- 법제처 Open API 신청 화면에서 목록/본문 XML 권한이 승인되어 있는지 확인하세요.
- 현재 seed는 현행법령 목록/본문 API를 사용합니다.

보고서 문안 품질이 낮음:

- `.env`의 모델을 `gpt-4.1-nano`에서 `gpt-4.1-mini`로 바꿔 테스트하세요.

```env
OPENAI_MODEL=gpt-4.1-mini
```

포트 8000 사용 중:

- 다른 서버가 실행 중일 수 있습니다. 기존 터미널에서 `Ctrl + C`로 종료한 뒤 다시 실행하세요.

`favicon.ico 404`:

- 브라우저가 자동으로 아이콘을 요청해서 생기는 로그입니다. 앱 동작에는 영향이 없습니다.
