# CMN_SWAGGER_OFFLINE_GUIDE.md

## 문제 정의
- `/cmn` 서버는 `cmn/main.py`에서 `/docs`를 열 때 로컬 정적 파일 경로인 `/static/swagger-ui-bundle.js`, `/static/swagger-ui.css`, `/static/favicon.png`를 사용하도록 설정되어 있습니다.
- 그런데 `cmn/static` 폴더 자체가 없으면 `StaticFiles` 마운트 시점에 실패하거나, 폐쇄망에서 Swagger 화면이 비어 보이게 됩니다.

## 접근 방법
- `cmn/static` 폴더에 Swagger 문서 렌더링용 로컬 JS/CSS 자산을 추가했습니다.
- `swagger-ui-bundle.js`는 FastAPI가 호출하는 `SwaggerUIBundle(...)` 전역 함수를 동일한 이름으로 제공하고, 내부에서 `/openapi.json`을 읽어 경량 문서 화면을 구성합니다.
- `swagger-ui.css`는 외부 CDN 없이도 데스크톱/모바일에서 읽기 쉬운 문서 레이아웃을 제공합니다.
- `favicon.png`는 브라우저 요청 404를 막기 위한 로컬 아이콘 파일입니다.

## 코드
### 관련 경로
- `cmn/main.py`
- `cmn/static/swagger-ui-bundle.js`
- `cmn/static/swagger-ui.css`
- `cmn/static/favicon.png`

### 실행 명령어
전제조건:
- Python 가상환경 `.venv`가 준비되어 있어야 합니다.
- `requirements.txt` 기준 패키지가 설치되어 있어야 합니다.

```powershell
.\.venv\Scripts\python -m uvicorn cmn.main:app --host 127.0.0.1 --port 8001
```

기대 결과:
- `http://127.0.0.1:8001/docs` 접속 시 폐쇄망에서도 문서 화면이 열립니다.
- 브라우저 개발자도구 네트워크 탭에서 외부 CDN 요청 없이 `/openapi.json`, `/static/swagger-ui-bundle.js`, `/static/swagger-ui.css`, `/static/favicon.png`만 호출됩니다.

실패 예시:
- 증상: `/docs`가 하얗게 비거나 `StaticFiles directory ... does not exist` 오류가 발생합니다.
- 해결 방법: `cmn/static` 폴더와 위 3개 정적 파일이 실제 배포본에 포함되었는지 확인합니다.

## 검증
### 수동 검증
1. `uvicorn cmn.main:app`으로 서버를 실행합니다.
2. 브라우저에서 `http://127.0.0.1:8001/docs`로 접속합니다.
3. 좌측 사이드바에 태그 목록, 우측 본문에 엔드포인트 카드가 표시되는지 확인합니다.
4. 검색 입력창에 `token`, `callback` 같은 키워드를 넣었을 때 관련 operation만 남는지 확인합니다.

### 자동 검증 예시
```powershell
.\.venv\Scripts\python -c "from fastapi.testclient import TestClient; from cmn.main import app; c=TestClient(app); print(c.get('/docs').status_code); print(c.get('/static/swagger-ui-bundle.js').status_code); print(c.get('/openapi.json').status_code)"
```

기대 결과:
- 세 응답 코드가 모두 `200`이어야 합니다.

## 왜 이렇게 했는지
- 폐쇄망에서는 CDN 방식 Swagger UI가 바로 깨질 수 있으므로, 서버가 직접 정적 자산을 제공하는 구조가 가장 단순하고 안정적입니다.
- 기존 `cmn/main.py`의 경로 계약을 유지하면 라우팅 코드를 크게 바꾸지 않고도 배포 누락 문제를 해결할 수 있습니다.

## 대안
- 대안: `swagger-ui-dist` 배포본을 사내 아티팩트 저장소에 보관하고 정식 파일을 vendoring(벤더링, 외부 라이브러리 파일을 저장소 내부에 고정 보관)하는 방법도 있습니다.

## 트레이드오프
- 이번 구현은 폐쇄망 호환성과 저장소 자급성을 우선한 경량 문서 UI이므로, 정식 Swagger UI의 "Try it out" 같은 고급 상호작용 기능은 포함하지 않았습니다.

## 한 줄 요약
- `cmn/static`에 로컬 Swagger 자산을 추가해서 폐쇄망에서도 `/cmn/docs`가 외부 CDN 없이 열리도록 구성했습니다.
