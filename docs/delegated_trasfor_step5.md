# Delegated Trasfor Step 5

관련 코드 경로:
- `app/clients/graph_client.py`
- `app/core/token_manager.py`
- `app/models/user_info.py`

## 문제 정의

Step 5의 목표는 `graph_client.py`를 기존 `Application Permission` 방식에서
`Delegated Permission` 방식으로 전환하는 것입니다.

여기서 `Graph Client`는 "Microsoft Graph API를 실제로 호출하는 공통 클라이언트"를 뜻합니다.

이번 단계에서 바뀌는 핵심은 아래와 같습니다.

1. 더 이상 `client_credentials`로 앱 토큰을 받지 않는다.
2. `token_manager.py`에 저장된 사용자 access token을 사용한다.
3. `/users/{email}` 대신 `/me/...` 기준으로 호출한다.

## 접근 방법

이번 프로젝트는 사용 범위를 `로그인한 본인 기준`으로 결정했습니다.
그래서 Graph 호출도 자연스럽게 `/me` 기반으로 바뀌어야 합니다.

기존 구조:
- 앱 권한 토큰 발급
- 특정 이메일을 URL에 끼워 넣음
- `/users/{email}/messages`

변경 구조:
- OAuth로 저장된 사용자 토큰 사용
- 현재 요청의 `current_user`에서 `user_id`, `company_cd` 확인
- `/me/messages`, `/me/events` 같은 본인 기준 경로 호출

왜 이렇게 했는지:
- 위임 권한에서는 "누구 대신 호출하는가"가 access token 안에 이미 포함됩니다.
- 본인 기준 기능에서는 `/me/...`가 가장 단순하고 안전합니다.

대안:
- 여전히 `user_email`을 받아 `/users/{email}`를 유지하는 방식

트레이드오프:
- 위임 권한의 장점을 충분히 못 살리고, 타인 리소스 접근 가능성까지 다시 설계해야 합니다.

## 코드

### 1. 현재 `graph_client.py`의 핵심 흐름

현재 `graph_request(...)`는 아래 순서로 동작합니다.

1. `get_http_request()`로 현재 HTTP 요청 컨텍스트를 읽음
2. `request.state.current_user`에서 사용자 정보 확인
3. 현재 사용자 기준으로 `user_id`, `company_cd`, `email` 추출
4. 블랙리스트 이메일 검증
5. `token_manager.get_valid_access_token(...)` 호출
6. `Bearer access_token` 헤더 구성
7. `https://graph.microsoft.com/v1.0/me{path}` 호출

### 2. 현재 사용자 컨텍스트 읽기

```python
req = get_http_request()
trace_id = getattr(req.state, "trace_id", "internal")
current_user = getattr(req.state, "current_user", None)
```

문법 설명:
- `getattr(obj, "name", default)`는 속성이 없을 때 기본값을 반환하는 안전한 조회 문법입니다.
- `request.state`는 미들웨어가 담아둔 요청별 문맥 저장 공간입니다.

왜 이렇게 했는지:
- Tool 호출 시 현재 사용자가 누구인지 알아야 어떤 토큰을 꺼낼지 결정할 수 있습니다.
- `trace_id`는 로깅 추적용으로 함께 사용합니다.

### 3. 현재 사용자 기준 토큰 꺼내기

```python
user_id = current_user.user_id
company_cd = current_user.company_cd
user_email = current_user.email

if _is_black_list(user_email):
    raise GraphAccessDeniedError(user_email)

access_token = await token_manager.get_valid_access_token(user_id, company_cd)
```

문법 설명:
- `await`는 비동기 함수의 결과를 기다리는 문법입니다.
- `token_manager.get_valid_access_token(...)`는 토큰 유효성 판단과 refresh를 포함한 진입 메서드입니다.

현재 상태 기준 주의:
- `token_manager.py`에 아직 `NotImplementedError`가 남아 있으므로
  토큰 없음/refresh 실패 시 지금은 아직 500으로 이어질 수 있습니다.

### 4. `/me` 기준 Graph URL 구성

```python
url = f"{GRAPH_BASE}/me{path}"
headers = {
    "Authorization": f"Bearer {access_token}",
    "Accept": "application/json",
}
```

문법 설명:
- `f"{GRAPH_BASE}/me{path}"`는 f-string으로 문자열 안에 변수 값을 삽입하는 문법입니다.
- `Authorization: Bearer ...` 헤더는 OAuth access token 인증 헤더입니다.

왜 `/me`인가:
- 현재 로그인한 사용자 자신의 메일, 일정, 드라이브를 조회하는 데 가장 적합합니다.
- 별도 `user_email` 파라미터로 타인 리소스를 지정할 필요가 없습니다.

### 5. HTTP 상태 코드별 예외 처리

현재 `graph_client.py`에는 아래 예외 구조가 있습니다.

- `GraphClientError`
- `GraphAccessDeniedError`
- `GraphBadRequestError`
- `GraphUnauthorizedError`
- `GraphForbiddenError`
- `GraphResourceNotFoundError`

예를 들면:

```python
except httpx.HTTPStatusError as e:
    status_code = e.response.status_code

    if status_code == 400:
        raise GraphBadRequestError(error_detail)
    elif status_code == 401:
        raise GraphUnauthorizedError(error_detail)
    elif status_code == 403:
        raise GraphForbiddenError(error_detail)
    elif status_code == 404:
        raise GraphResourceNotFoundError(error_detail)
```

왜 이렇게 했는지:
- Tool 계층에서 "무슨 종류의 실패인지" 구분하기 쉬워집니다.
- 이후 LLM이 사용자에게 이해하기 쉬운 메시지로 바꿔 전달하기 좋습니다.

### 6. Graph 요청/응답 로깅

현재 `logging_message(...)`는 아래 정보를 남깁니다.

- `trace_id`
- `status_code`
- `method`
- `elapsed_ms`
- `email`
- `company_cd`
- 요청 JSON
- 응답 JSON 또는 에러 메시지

이 로깅은 위임 권한 구조에서도 그대로 중요합니다.

왜냐하면:
- 같은 사용자 요청이 여러 Tool을 거칠 수 있고
- Graph 응답 실패가 권한 문제인지, 파라미터 문제인지 추적해야 하기 때문입니다.

## 검증

### Step 5에서 확인할 것

1. `graph_client.py`가 더 이상 앱 토큰 발급 함수를 직접 가지지 않는지
2. `token_manager.get_valid_access_token(...)`를 사용하고 있는지
3. Graph URL이 `/me{path}` 기준인지
4. 현재 사용자 문맥이 없으면 방어적으로 실패하는지
5. Graph 400/401/403/404 응답을 의미 있는 예외로 변환하는지

### 테스트 전제조건

1. OAuth callback까지 성공해 사용자 토큰이 저장된 상태
2. 요청 미들웨어가 `request.state.current_user`를 세팅하는 상태
3. Tool 또는 테스트 코드가 `graph_request(...)`를 호출할 수 있는 상태

### 기대 결과

예를 들어 메일 조회 경로라면:

```python
await graph_request("GET", "/messages")
```

내부적으로 아래 흐름이 일어나야 합니다.

1. 현재 사용자 문맥 획득
2. 사용자 access token 획득
3. `https://graph.microsoft.com/v1.0/me/messages` 호출
4. JSON 응답 반환

### 현재 남아 있는 리스크

현재 `graph_client.py` 자체 방향은 맞지만,
실제 완성도는 아직 `token_manager.py`의 미완성 분기에 묶여 있습니다.

즉 지금은 아래 상황에서 아직 최종 UX가 완성되지 않았습니다.

- 저장된 토큰이 없을 때
- refresh 실패했을 때
- `AuthRequiredError -> connect_url` 변환이 아직 정리되지 않았을 때

이 부분은 다음 정리 단계에서 Tool과 연결하면서 다듬게 됩니다.

## Mermaid 흐름도

```mermaid
flowchart TD
    A[Tool이 graph_request 호출] --> B[get_http_request로 current_user 조회]
    B --> C{current_user 존재하는가?}
    C -- 아니오 --> D[예외 발생]
    C -- 예 --> E[token_manager에서 access token 획득]
    E --> F{토큰 획득 성공인가?}
    F -- 아니오 --> G[현재는 token_manager 분기 상태에 의존]
    F -- 예 --> H[/me 경로로 Graph 요청]
    H --> I{HTTP 상태 코드 확인}
    I -- 200/204 --> J[JSON 또는 success 반환]
    I -- 400/401/403/404 --> K[의미 있는 Graph 예외로 변환]
```

설명:
- `graph_client.py`는 현재 사용자 문맥과 `token_manager`를 연결하는 공통 진입점입니다.
- 실제 Graph 요청은 이제 `/me` 기준으로 수행됩니다.
- HTTP 에러는 Tool이 다루기 쉬운 도메인 예외로 다시 감쌉니다.
- 토큰 부재/refresh 실패의 최종 UX는 다음 단계에서 Tool 계층과 함께 마무리됩니다.

## 한 줄 요약

Step 5에서는 `graph_client.py`를 사용자 토큰 기반 `/me/...` 호출 구조로 전환했고,
이제 다음 단계에서는 `mail_tools.py` 같은 실제 Tool을 이 공통 Graph 클라이언트에 연결하면 됩니다.
