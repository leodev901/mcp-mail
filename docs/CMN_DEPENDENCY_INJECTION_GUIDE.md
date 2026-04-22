# CMN_DEPENDENCY_INJECTION_GUIDE.md

## 문제 정의
- FastAPI에서 `Depends(AuthService)`처럼 일반 클래스를 직접 의존성으로 넣으면, 생성자 `__init__()` 인자도 요청 파라미터처럼 분석합니다.
- 이번 경우 `AuthService.__init__(session: AsyncSession)`의 `AsyncSession`을 Pydantic 필드로 만들 수 없어서 서버 시작 시점에 `FastAPIError`가 발생했습니다.

## 접근 방법
- `AuthService`는 비즈니스 로직 클래스 그대로 유지합니다.
- 대신 FastAPI가 이해할 수 있는 함수 의존성 `get_auth_service_by_company()`를 만들어, 요청 body의 `company_cd`로 schema 세션을 연 뒤 `AuthService(session)`을 생성하도록 변경했습니다.

## 코드
### 관련 경로
- `cmn/api/endpoint/m365_oauth.py`
- `cmn/services/auth_service.py`

### 핵심 패턴
```python
async def get_auth_service_by_company(
    request: Request,
    payload: AuthRequest,
) -> AsyncGenerator[AuthService, None]:
    company_cd = payload.company_cd.strip()
    db_manager: Database = request.app.state.db

    async for session in db_manager.get_session_schema(company_cd):
        yield AuthService(session)
```

```python
@router.post("/")
async def auth(
    payload: AuthRequest,
    auth_service: AuthService = Depends(get_auth_service_by_company),
):
    return await auth_service.get_auth_token(payload.company_cd, payload.app_name)
```

문법 설명:
- `Depends(...)`는 의존성 주입(Dependency Injection, 필요한 객체를 프레임워크가 대신 준비해 주는 방식) 문법입니다.
- `yield` 의존성은 요청 동안 자원을 유지하고 종료 시점에 정리할 수 있게 해 줍니다.

## 검증
### 실행 명령어
전제조건:
- `.venv` 환경의 패키지가 설치되어 있어야 합니다.

```powershell
.\.venv\Scripts\python -c "import cmn.main; print('IMPORT_OK')"
```

기대 결과:
- `IMPORT_OK`가 출력되어야 합니다.
- 더 이상 `Invalid args for response field` 예외가 발생하지 않아야 합니다.

실패 예시:
- 증상: `company_cd is required`
- 해결 방법: `/api/auth/` POST body에 `company_cd`를 포함합니다.

## 왜 이렇게 했는지
- 서비스 클래스는 FastAPI 프레임워크 의존성과 분리해 두는 편이 테스트와 유지보수에 유리합니다.
- DB 세션 선택은 HTTP 요청 문맥이 필요하므로, 서비스를 만들기 전에 함수 의존성에서 처리하는 구조가 가장 명확합니다.

## 대안
- 대안: 엔드포인트에서 `db: AsyncSession = Depends(...)`를 직접 받고 `AuthService(db)`를 수동 생성할 수도 있습니다.

## 트레이드오프
- 의존성 함수가 하나 더 생겨 코드 줄 수는 조금 늘어나지만, 요청 해석과 서비스 로직 책임이 분리되어 디버깅이 쉬워집니다.

## 한 줄 요약
- `Depends(AuthService)`를 함수 의존성으로 바꾸면 `AsyncSession` 주입 오류 없이 FastAPI가 정상 기동됩니다.
