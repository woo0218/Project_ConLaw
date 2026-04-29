# Project_ConLaw
건설 법령 공공 문서 작성 도우미

### 주요 기능
1. **문서 폼 업로드**: 사용자가 사용할 문서 템플릿 제공
2. **상황 입력**: 사용자의 법적 상황 기술
3. **법령 자동 매칭**: LLM + 법령 API를 통한 관련 법령 검색 및 요약
4. **법령 선택**: 사용자가 적용할 법령 선택
5. **문서 생성**: 사례 기반 자동 문서 작성
6. **최종 검토**: 사용자 승인 프로세스
7. **문서 출력**: HWP 형식으로 최종 문서 제공

---

## 🏗️ 기술 스택

### Backend
- **언어**: Python 3.11+ ⭐ (Claude + Codex 최적화)
- **웹 프레임워크**: FastAPI (비동기 지원, 자동 API 문서)
- **LLM**: Claude API (Anthropic) - Sonnet 3.5
- **데이터베이스**: Supabase (PostgreSQL + Auth + Realtime)
- **API 클라이언트**:
  - Supabase Python SDK
  - Anthropic Python SDK (공식)
- **문서 처리**:
  - python-docx (DOCX 생성)
  - pdfplumber (PDF 추출)
  - LangChain (LLM 체인)

### Frontend
- **프레임워크**: React 18+ + TypeScript
- **상태관리**: TanStack Query (서버 상태) + Zustand (전역 상태)
- **UI 라이브러리**: Shadcn/ui (Tailwind 기반)
- **스타일**: Tailwind CSS
- **폼 관리**: React Hook Form
- **Supabase 클라이언트**: @supabase/supabase-js

### 테스트 & 개발
- **단위 테스트**: pytest + pytest-asyncio
- **통합 테스트**: pytest-mock, responses (HTTP 모킹)
- **E2E 테스트**: Playwright (선택사항)
- **테스트 커버리지**: pytest-cov (목표: 90%+)

### DevOps & 배포
- **Backend**: Railway (Python FastAPI 자동 감지)
- **Frontend**: Vercel (React 자동 감지)
- **Database**: Supabase (관리형 PostgreSQL)
- **CI/CD**: GitHub Actions
- **컨테이너**: Docker (로컬 개발용, 배포는 Railway)

---

## 📁 프로젝트 구조

```
legal-doc-generator/
├── README.md
├── .gitignore
├── pyproject.toml              # Poetry 설정
├── docker-compose.yml
├── Dockerfile
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI 앱 엔트리포인트
│   │   ├── config.py           # 설정 관리 (Supabase 키 등)
│   │   │
│   │   ├── core/               # 핵심 비즈니스 로직
│   │   │   ├── __init__.py
│   │   │   ├── law_matching.py      # 법령 매칭 엔진
│   │   │   ├── law_summarizer.py    # 법령 요약 (Claude API)
│   │   │   ├── document_generator.py # 문서 생성 로직
│   │   │   └── validation.py        # 입력값 검증
│   │   │
│   │   ├── services/          # 외부 서비스 통합
│   │   │   ├── __init__.py
│   │   │   ├── supabase_service.py  # Supabase 클라이언트
│   │   │   ├── llm_service.py       # Claude API 호출
│   │   │   ├── law_search_service.py # 법령 검색 (Full-Text Search)
│   │   │   └── document_service.py  # DOCX/HWP 변환
│   │   │
│   │   ├── schemas/           # Pydantic 스키마
│   │   │   ├── __init__.py
│   │   │   ├── document.py
│   │   │   ├── law.py
│   │   │   └── user.py
│   │   │
│   │   ├── api/               # API 라우터
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── documents.py
│   │   │   │   ├── laws.py
│   │   │   │   └── health.py
│   │   │   └── deps.py        # 의존성 주입
│   │   │
│   │   └── utils/             # 유틸리티
│   │       ├── __init__.py
│   │       └── file_handler.py
│   │
│   └── tests/
│       ├── conftest.py        # pytest 공용 설정
│       ├── unit/
│       │   ├── test_law_matching.py
│       │   ├── test_law_summarizer.py
│       │   ├── test_document_generator.py
│       │   └── test_validation.py
│       ├── integration/
│       │   ├── test_law_api_service.py
│       │   ├── test_llm_service.py
│       │   └── test_document_workflow.py
│       └── e2e/
│           └── test_full_workflow.py
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   ├── FormUploader.tsx
│   │   │   ├── SituationInput.tsx
│   │   │   ├── LawSelector.tsx
│   │   │   ├── DocumentPreview.tsx
│   │   │   └── ApprovalStep.tsx
│   │   │
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── DocumentCreate.tsx
│   │   │   └── History.tsx
│   │   │
│   │   ├── hooks/
│   │   │   ├── useDocumentFlow.ts
│   │   │   ├── useLawAPI.ts
│   │   │   └── useFileUpload.ts
│   │   │
│   │   ├── services/
│   │   │   └── api.ts
│   │   │
│   │   └── App.tsx
│   │
│   └── tests/
│       ├── unit/
│       └── e2e/
│
└── docs/
    ├── ARCHITECTURE.md
    ├── API.md
    ├── SETUP.md
    └── TESTING.md
```

---
