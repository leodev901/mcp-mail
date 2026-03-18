# REQUEST_STATE_GUIDE.md

## 문제 정의
- `current_user` 를 `ContextVar` 에만 두면 HTTP 요청과 MCP tool 실행이 다른 컨텍스트일 때 값이 섞이거나 비어 보일 수 있다.
- 그래서 tool 코드도 현재 HTTP 요청의 `request.state` 를 기준으로 사용자 정보를 읽도록 맞춘다.

## 접근 방법
- HTTP ASGI 미들웨어가 `scope["state"]["trace_id"]`, `scope["state"]["current_user"]` 를 채운다.
- MCP 미들웨어와 tool 은 `get_http_request()` 로 현재 요청을 받아 같은 `state` 를 읽는다.
- 테스트도 `mcp_context.py` 대신 `request.state` 를 가진 더미 요청을 만들어 검증한다.

## 코드 경로
- `app/core/http_ASGI_middware.py`
- `app/core/mcp_midleware.py`
- `app/tools/calendar_tools.py`

## 예시
```python
from fastmcp.server.dependencies import get_http_request

request = get_http_request()
current_user = getattr(request.state, "current_user", None)
trace_id = getattr(request.state, "trace_id", "-")
```

설명:
- `get_http_request()` 는 현재 MCP 실행과 연결된 HTTP 요청 객체를 가져온다.
- `getattr(..., None)` 를 쓰면 테스트나 비HTTP 실행 환경에서도 바로 예외가 나지 않는다.

## 검증 기준
1. HTTP 로그와 MCP 로그의 `trace_id` 가 같은 요청에서 일치해야 한다.
2. `list_my_calendar_events` 같은 tool 도 `request.state.current_user` 를 기준으로 동작해야 한다.
3. 테스트가 `mcp_context.py` 의 `set_*`, `get_*` 없이도 통과해야 한다.

## 한 줄 요약
- `trace_id`, `current_user` 의 진짜 기준 저장소를 `request.state` 로 통일하면 HTTP, MCP, tool 코드가 같은 요청 데이터를 보게 된다.
