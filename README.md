# Project_ConLaw

건설공사 감리 상황을 입력하면 관련 법령 후보를 검색하고, 선택한 법령 조문을 근거로 감리보고서 `.docx`를 생성하는 로컬 웹 앱입니다.

## 기능

- 법제처 Open API 기반 법령 데이터 적재
- SQLite FTS5 기반 법령 조문 검색
- 검색된 법령 후보의 조문 본문 확인
- 선택한 법령을 기준으로 감리보고서 문안 생성
- `.docx` 템플릿 업로드 및 보고서 다운로드
- `{{placeholder}}` 기반 템플릿 지원
- 공식 감리보고서 표 양식 지원
  - 자동 작성: `기타사항`, `종합의견`
  - 자동 작성 제외: 허가번호, 허가일자, 대지위치, 지번, 건축주, 서명자, 날짜, 확인자/서명란, 체크박스
- Windows 실행 파일 빌드를 위한 GitHub Actions 워크플로 제공

## 실행 방법

### 1. 환경변수 설정

프로젝트 루트에 `.env` 파일을 만들고 아래 값을 입력합니다.

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-nano
LAW_API_OC=your_law_go_kr_oc
AUTO_SEED_CONSTRUCTION_LAWS=1
AUTO_SEED_MIN_LAW_ROWS=200
```

문안 품질을 높이고 싶으면 `OPENAI_MODEL`을 `gpt-4.1-mini`로 변경할 수 있습니다.

```env
OPENAI_MODEL=gpt-4.1-mini
```

### 2. 설치

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. 법령 데이터 적재

앱 시작 시 건설 관련 주요 법령은 백그라운드에서 자동 적재됩니다. 자동 적재 상태는 화면 상단의 진행 표시에서 확인할 수 있으며, 적재 중에도 앱은 계속 사용할 수 있습니다.

자동 적재는 설정된 건설 관련 법령 목록을 하나씩 확인합니다. 이미 `laws_cache`에 조문이 저장된 법령은 건너뛰고, 누락된 법령만 법제처 API에서 가져옵니다.

자동 적재를 끄려면 `.env`에 아래 값을 설정합니다.

```env
AUTO_SEED_CONSTRUCTION_LAWS=0
```

수동 적재 명령도 계속 사용할 수 있습니다.

```bash
python scripts/seed_laws.py "건설기술 진흥법"
```

필요한 법령을 추가로 적재할 수 있습니다.

```bash
python scripts/seed_laws.py "건축법"
python scripts/seed_laws.py "건축법 시행령"
```

### 4. 앱 실행

```bash
python run_app.py
```

개발 서버로 실행하려면:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

브라우저에서 접속:

```text
http://127.0.0.1:8000
```

### 5. 사용 순서

1. `.docx` 템플릿 업로드
2. 현장 상황 입력
3. 법령 후보 검색
4. 법령 후보 선택 및 본문 확인
5. 보고서 생성
6. `.docx` 다운로드

## Windows 실행 파일

GitHub Actions의 `Build Windows EXE` 워크플로로 Windows용 실행 파일을 빌드합니다.

1. GitHub에 push
2. `Actions` 탭에서 `Build Windows EXE` 실행
3. `MyApp-windows` artifact 다운로드
4. 압축 해제
5. `MyApp.exe` 옆에 `.env` 배치
6. `MyApp.exe` 실행

PyInstaller `onedir` 방식이므로 `MyApp.exe`만 배포하지 말고 생성된 폴더 전체를 배포해야 합니다.
