# HTTP_STATE_GUIDE.md

## 문제 정의
- `ContextVar`만으로 HTTP 요청과 MCP 실행 컨텍스트를 연결하면 이전 요청 값이 섞일 수 있다.
- 그래서 현재 요청과 함께 이동하는 저장소에 `trace_id`, `current_user`를 명시적으로 보관하는 방식이 필요하다.

## 접근 방법
- ASGI 미들웨어에서는 `scope["state"]`를 요청 공용 저장소로 사용한다.
- 이 예제에서는 아래 2개만 저장한다.
  - `trace_id`
  - `current_user`
- `/mcp` 경로는 리다이렉트 전용으로 보고 로그를 남기지 않는다.
- 실제 처리 경로인 `/mcp/`만 request/response 로그를 남긴다.

## 코드 경로
- `app/core/http_ASGI_middware.py`
- `app/core/mcp_midleware.py`

## 핵심 예시
```python
state = scope.setdefault("state", {})
state["trace_id"] = trace_id
state["current_user"] = userinfo
```

설명:
- `scope.setdefault("state", {})`는 현재 요청의 state dict가 없으면 새로 만들고, 있으면 기존 것을 재사용한다.
- downstream에서 새 `Request` 객체를 만들더라도 같은 `scope`를 보면 같은 state를 읽을 수 있다.

## 검증 포인트
1. `tools/call` 요청의 HTTP 로그와 MCP 로그의 `trace_id`가 같아야 한다.
2. MCP 로그에서 `current_user.email`, `company_cd`가 HTTP에서 조회한 값과 같아야 한다.
3. `/mcp` 307 리다이렉트 로그는 남지 않고 `/mcp/` 로그만 남아야 한다.

## 한 줄 요약
- `scope["state"]`는 요청 단위 공용 저장소로 쓰기 좋고, 리다이렉트용 `/mcp` 로그를 제외하면 운영 로그도 더 읽기 쉬워진다.
