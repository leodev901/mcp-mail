# HTTP_LOGGING_GUIDE.md

## 문제 정의
- `HttpLoggingMiddleware`는 `/mcp` 요청 중 일부 메서드만 HTTP 로그 대상으로 본다.
- 현재 기준:
  - `tools/call`
  - `tools/list`
- 사용자 토큰 해석은 `tools/call`에서만 수행한다.

## 접근 방법
- 요청 body는 `POST`일 때만 읽는다.
- JSON body에서 `method`를 한 번만 추출한 뒤 아래 판단값으로 재사용한다.
  - `should_log_http`
  - `should_set_user_context`

## 코드 흐름
- 코드 경로: `app/core/http_middleware.py`
1. `trace_id` 생성 또는 재사용
2. request body 파싱
3. `method_name` 계산
4. `tools/call`이면 사용자 토큰 해석
5. `tools/call`, `tools/list`이면 HTTP request 로그 기록
6. 응답 후 status/duration/headers 로그 기록

## 실수 포인트
- `BaseHTTPMiddleware`에서는 `request.body()` 캐시를 재사용하므로 `request._receive`를 직접 건드리지 않는다.
- `/mcp` 응답은 `_StreamingResponse`가 될 수 있으므로 `response.body`에 직접 접근하지 않는다.
- `tools/list`도 HTTP 로그 대상이므로 `body=None` 기대 테스트로 두면 안 된다.

## 검증 절차
- `tools/call` 요청:
  - request body가 로그에 남아야 한다.
  - 사용자 토큰이 있으면 사용자 context를 설정한다.
- `tools/list` 요청:
  - request body가 로그에 남아야 한다.
  - 사용자 토큰 해석은 하지 않는다.
- `ping` 요청:
  - request body는 HTTP 로그 대상이 아니다.
