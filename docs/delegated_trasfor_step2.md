# Delegated Trasfor Step 2

## 문제 정의

위임 권한 구조에서는 로그인 성공 후 받은 토큰을 사용자별로 저장해야 한다.
이번 Step 2의 목표는 아래 3가지다.

1. 사용자별 토큰 저장 구조 만들기
2. OAuth `state` 임시 저장 구조 만들기
3. 메모리 저장소의 테스트 방법과 한계를 이해하기

관련 코드 경로:

- `app/core/token_manager.py`
- `app/test.py`

---

## 접근 방법

이번 단계에서는 DB 대신 **메모리 기반 저장소**를 사용한다.

왜 이렇게 하는가?

- OAuth 흐름을 먼저 검증하기 쉽다.
- 구조를 이해하기 좋다.
- 나중에 DB로 바꿀 때 메서드 이름만 유지하면 다른 코드 수정이 적다.

현재 저장해야 하는 데이터는 두 종류다.

1. 사용자 토큰
2. OAuth `state`

---

## token_manager.py 구조

관련 코드 경로:

- `app/core/token_manager.py`

현재 핵심 모델은 아래 두 개다.

### 1. `TokenRecord`

사용자 1명의 토큰 세트를 표현한다.

- `user_id`
- `company_cd`
- `access_token`
- `refresh_token`
- `access_token_expires_at`

### 2. `OAuthStateRecord`

OAuth 시작 시 만든 `state`와 연결된 임시 정보를 표현한다.

- `user_id`
- `company_cd`
- `created_at`

### 핵심 메서드

- `save_tokens(...)`
- `get_tokens(...)`
- `clear_tokens(...)`
- `is_access_token_valid(...)`
- `save_oauth_state(...)`
- `pop_oauth_state(...)`

---

## 왜 state를 저장하는가?

`state`는 OAuth 로그인 흐름에서 “내가 시작한 요청”과 “Microsoft가 돌려준 응답”이 같은 세트인지 검증하는 1회용 랜덤 문자열이다.

흐름은 아래와 같다.

1. 우리 서버가 `state` 생성
2. Microsoft 로그인 URL에 `state` 포함
3. Microsoft가 callback에서 같은 `state` 반환
4. 우리 서버가 저장된 값과 비교

왜 중요한가?

- 다른 사용자의 콜백이 섞이는 것을 막기 위해
- 위조된 callback 요청을 걸러내기 위해

---

## 왜 expires_in - 120 을 하는가?

토큰 만료 직전에는 서버 시간 오차나 네트워크 지연 때문에
막 만료된 토큰을 사용할 위험이 있다.

그래서 `expires_in - 120`으로 2분 먼저 만료로 간주한다.

이 방식의 장점:

- 만료 직전 경계값 오류를 줄일 수 있다.

---

## 테스트 방법

관련 코드 경로:

- `app/test.py`

테스트 예시는 아래처럼 할 수 있다.

```powershell
@'
from app.core.token_manager import token_manager

token_manager.save_tokens(
    user_id="20075487",
    company_cd="leodev901",
    access_token="access-token-sample",
    refresh_token="refresh-token-sample",
    expires_in=3600,
)

record = token_manager.get_tokens("20075487", "leodev901")
print(record.user_id)
print(record.company_cd)
print(token_manager.is_access_token_valid("20075487", "leodev901"))

token_manager.save_oauth_state("state-123", "20075487", "leodev901")
state_record = token_manager.pop_oauth_state("state-123")
print(state_record.user_id)
print(token_manager.pop_oauth_state("state-123"))
'@ | .\.venv\Scripts\python.exe -
```

기대 결과:

- `20075487`
- `leodev901`
- `True`
- `20075487`
- `None`

---

## 메모리 저장소 테스트의 주의점

여기서 가장 많이 헷갈리는 포인트가 있다.

`token_manager`는 **프로세스 메모리 저장소**이므로,
`uvicorn` 서버 프로세스와 별도로 `python app/test.py`를 실행하면
같은 토큰을 공유하지 않는다.

즉 아래처럼 된다.

```text
uvicorn app.main:app
  -> 서버 프로세스 메모리에 토큰 저장

python app/test.py
  -> 새 프로세스에서 비어 있는 token_manager 확인
```

그래서 `app/test.py`에서 `None`이 나온다고 해서
저장이 실패했다고 단정하면 안 된다.

더 정확한 확인 방법:

1. 같은 서버 프로세스 안에서 로그 출력
2. 다음 단계에서 실제 Tool / Graph 호출로 검증

---

## 실패 예시와 해결 방법

### 1. dataclass 필드명 불일치

실패 예시:

- `company_cd` 대신 `compnay_cd`
- `refresh_token` 대신 `rfresh_token`

해결 방법:

- `TokenRecord` 필드명과 `save_tokens()` 인자명을 완전히 통일한다.

### 2. state 재사용

실패 예시:

- 같은 `state`를 두 번 사용

해결 방법:

- `pop_oauth_state()`처럼 꺼내면서 삭제하는 구조를 유지한다.

---

## 검증

Step 2가 끝났다면 아래를 만족해야 한다.

1. `token_manager.py`에서 사용자별 토큰 저장/조회가 된다.
2. `state`를 저장하고 한 번만 꺼낼 수 있다.
3. `is_access_token_valid()`가 만료 전에는 `True`를 반환한다.
4. 메모리 저장소는 프로세스 간 공유되지 않는다는 점을 이해했다.

---

## 한 줄 요약

Step 2에서는 `token_manager.py`로 사용자별 토큰과 OAuth `state`를 메모리에 저장하는 구조를 만들었고,
테스트 시 메모리 저장소가 서버 프로세스 안에서만 유효하다는 점까지 확인했다.
