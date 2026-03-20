# Delegated Trasfor Step 1

## 문제 정의

현재 프로젝트는 `Application Permission` 기반 Microsoft Graph 호출 구조에서
`Delegated Permission` 기반 구조로 전환 중이다.

이번 Step 1의 목표는 아래 3가지를 고정하는 것이다.

1. Azure App Registration 설정
2. `.env`와 `config.py` 구조 정리
3. 회사별 OAuth 설정을 안전하게 읽는 기반 준비

이번 학습에서는 범위를 아래처럼 제한한다.

- 로그인한 **본인 기준**의 메일 / 일정 / 드라이브만 다룬다.
- 다른 사용자 메일함이나 일정 조회는 제외한다.
- 회사별 설정은 `.env`의 `MS365_CONFIGS` JSON 문자열로 관리한다.

관련 코드 경로:

- `app/core/config.py`
- `.env`

---

## 접근 방법

위임 권한 구조에서 가장 먼저 바뀌는 것은 “설정의 기준”이다.

- 기존: 앱 토큰 발급용 `tenant_id`, `client_id`, `client_secret` 위주
- 변경: OAuth 시작/콜백을 위한 `redirect_uri`, `scopes`까지 포함

즉, 회사별 설정에서 아래 다섯 값이 반드시 있어야 한다.

- `tenant_id`
- `client_id`
- `client_secret`
- `redirect_uri`
- `scopes`

왜 이렇게 하는가?

- `redirect_uri`는 Microsoft 로그인 후 우리 서버로 돌아오는 주소이기 때문이다.
- `scopes`는 사용자가 동의할 권한 범위를 정의하기 때문이다.
- 이후 `m365_oauth.py`에서 이 설정을 그대로 사용하게 된다.

대안:

- 회사별 키를 없애고 단일 앱 설정만 사용할 수 있다.

트레이드오프:

- 단순하지만 멀티 테넌트 확장성이 떨어진다.

---

## Azure 설정

위임 권한으로 테스트하려면 Azure / Entra App Registration에서 아래를 맞춰야 한다.

### 1. 플랫폼

- `Authentication` > `Add a platform` > `Web`

### 2. Redirect URI

코드와 Azure 등록값은 **문자 하나까지 완전히 같아야 한다**.

예시:

```text
http://localhost:8003/auth/m365/callback
```

아래는 서로 다른 값으로 취급된다.

- `localhost` 와 `127.0.0.1`
- `8002` 와 `8003`
- `/callback` 와 `/callback/`

### 3. Client Secret

`.env`의 `client_secret`에는 Azure 화면의 `Secret ID`가 아니라
반드시 `Value`를 넣어야 한다.

실패 예시:

- `AADSTS7000215: Invalid client secret provided`

해결 방법:

- `Certificates & secrets`에서 새 client secret 생성 후
  생성 직후 보이는 `Value`를 `.env`에 넣는다.

---

## .env 구조

전제조건:

- `MS365_CONFIGS`는 유효한 JSON 문자열이어야 한다.
- `company_cd`와 JSON 키 이름이 일치해야 한다.

예시:

```env
MS365_CONFIGS={"leodev901":{"tenant_id":"ef6b6834-cff9-47ae-86ff-f7c9a1d0e225","client_id":"7d54979e-1c79-4e7c-a8c5-9b72589561da","client_secret":"your-secret-value","redirect_uri":"http://localhost:8003/auth/m365/callback","scopes":"openid profile offline_access User.Read Mail.Read Mail.Send"}}
```

기대 결과:

- `company_cd="leodev901"`로 설정 조회 가능
- `redirect_uri`와 `scopes`를 OAuth 코드에서 바로 사용 가능

실패 예시:

- `redirect_uri` 오타
- `client_secret`에 `Secret ID` 입력
- JSON 필드명 오타

해결 방법:

- 코드와 `.env`, Azure 설정 이름을 완전히 통일한다.

---

## config.py 정리

관련 코드 경로:

- `app/core/config.py`

현재 `config.py`의 역할은 아래와 같다.

1. `.env`의 `MS365_CONFIGS`를 `json.loads()`로 파싱한다.
2. `company_cd` 기준으로 회사 설정을 찾는다.
3. 필수 키 누락 시 즉시 예외를 발생시킨다.
4. `get_m365_scopes(company_cd)`로 공백 기준 scope 리스트를 만든다.

### 핵심 문법 설명

- `json.loads(...)`
  문자열 JSON을 파이썬 딕셔너리로 바꾸는 문법이다.
- `config.get("redirect_uri")`
  키가 없을 수 있을 때 안전하게 읽는 문법이다.
- `split(" ")`
  공백 기준으로 scope 문자열을 나누는 문법이다.

---

## 실습 코드

`config.py`가 준비되면 아래 같은 호출이 가능해야 한다.

```python
config = settings.get_m365_config("leodev901")
scopes = settings.get_m365_scopes("leodev901")
```

기대 결과:

- `config["redirect_uri"]` 가 문자열로 반환된다.
- `scopes` 가 리스트로 반환된다.

예시:

```python
[
    "openid",
    "profile",
    "offline_access",
    "User.Read",
    "Mail.Read",
    "Mail.Send",
]
```

---

## 검증

Step 1이 끝났다면 아래를 만족해야 한다.

1. Azure App Registration에 `Web` Redirect URI가 등록되어 있다.
2. `.env`의 `redirect_uri`와 Azure 등록값이 완전히 같다.
3. `.env`의 `client_secret`가 `Value` 기준으로 들어가 있다.
4. `config.py`가 회사별 필수 설정을 읽을 수 있다.
5. `get_m365_scopes(company_cd)`가 정상 동작한다.

---

## 한 줄 요약

Step 1에서는 Azure App Registration, `.env`, `config.py`를 정리해
회사별 위임 권한 OAuth 설정을 안전하게 읽을 수 있는 기반을 만들었다.
