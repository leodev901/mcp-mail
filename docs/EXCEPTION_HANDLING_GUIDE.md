# Python API 예외(Exception) 처리 전략 가이드

> **대상 독자**: Python 에러 핸들링 패턴을 실무 기준으로 정리하고 싶은 개발자  
> **예시 배경**: 외부 결제 API, DB 클라이언트, REST API 클라이언트 래퍼를 구현하는 일반적인 Python 서버 구조를 사용합니다.

---

## 📌 목차

1. [문제 정의](#1-문제-정의)
2. [에러 포맷 구조화 방안 3가지](#2-에러-포맷-구조화-방안-3가지)
3. [커스텀 예외 클래스 설계: 1개 vs 계층 구조](#3-커스텀-예외-클래스-설계-1개-vs-계층-구조)
4. [공통 부모 클래스(상속)를 쓰는 이유](#4-공통-부모-클래스상속를-쓰는-이유)
5. [API 핸들러에서의 처리 방식](#5-api-핸들러에서의-처리-방식)
6. [에러 처리 모듈화: 헬퍼 vs 데코레이터](#6-에러-처리-모듈화-헬퍼-vs-데코레이터)
7. [반환 타입이 혼재할 때의 대응](#7-반환-타입이-혼재할-때의-대응)
8. [전략 선택 기준 요약](#8-전략-선택-기준-요약)
9. [HTTP 상태 코드별 커스텀 예외 변환 패턴](#9-http-상태-코드별-커스텀-예외-변환-패턴)
10. [message vs error 필드 분리 패턴](#10-message-vs-error-필드-분리-패턴)
11. [실패 예시 & 해결 방법](#11-실패-예시--해결-방법)
12. [학습 포인트 체크리스트](#12-학습-포인트-체크리스트)

---

## 1. 문제 정의

외부 API나 DB를 호출하는 **클라이언트 레이어**에서 에러가 발생했을 때,  
그 에러를 어떤 형태로 상위 레이어(라우터/핸들러)에 전달할지가 핵심 문제입니다.

**시나리오**: 결제 API 클라이언트에서 차단된 사용자를 처리하는 경우

```python
# ❌ 나쁜 예: 에러인데 정상 dict로 반환해버림
class PaymentClient:
    async def charge(self, user_id: str, amount: int) -> dict:
        if self._is_blocked(user_id):
            return {"message": "결제가 차단된 사용자입니다."}   # 문제 발생!
        # ... 실제 결제 처리
        return {"transaction_id": "txn_abc123", "status": "success"}
```

**이 코드의 문제점**:

```python
# 호출하는 쪽(핸들러)에서는 에러 여부를 알 수 없다
result = await payment_client.charge(user_id, amount)

# result가 정상 응답인지 에러인지 구분 불가
transaction_id = result.get("transaction_id")
# ↑ 차단된 사용자의 경우 "transaction_id" 키가 없으므로 None → 에러 무시됨
```

> **핵심 원칙**: "에러는 에러답게 표현해야 한다.  
> 정상 반환값과 에러 반환값이 같은 타입이면 caller가 구분할 수 없다."

---

## 2. 에러 포맷 구조화 방안 3가지

### 방안 A. 커스텀 예외 클래스 (`raise`) ⭐ 권장

```python
# app/clients/payment_client.py

class PaymentAccessDeniedError(Exception):
    """
    결제가 차단된 사용자에 대해 발생시키는 커스텀 예외.

    [문법 포인트]
    Exception을 상속받아야 Python의 예외 처리 시스템(try/except)에서 잡힌다.
    super().__init__(message)는 부모 클래스(Exception)에 메시지를 전달하여
    str(e), repr(e) 로 출력 가능하게 만드는 관례(convention)이다.
    """
    def __init__(self, code: str, message: str):
        super().__init__(message)  # Exception 기반 초기화 (필수)
        self.code = code           # 에러 분류 코드 (예: "BLOCKED_USER")
        self.message = message     # 사람이 읽을 수 있는 메시지


class PaymentClient:
    async def charge(self, user_id: str, amount: int) -> dict:
        if self._is_blocked(user_id):
            # ✅ 에러를 명확하게 예외로 표현
            raise PaymentAccessDeniedError(
                code="BLOCKED_USER",
                message=f"결제가 차단된 사용자입니다. user_id={user_id}"
            )
        # ... 정상 결제 처리
        return {"transaction_id": "txn_abc123", "status": "success"}
```

| 장점 | 단점 |
|---|---|
| Python 관용 방식, 코드 의도 명확 | caller에서 `try/except` 코드 필요 |
| 에러 분류(`code`)로 세분화 처리 가능 | |
| 스택트레이스 보존 → 디버깅 용이 | |
| 미들웨어/로거가 자동으로 에러 감지 | |

---

### 방안 B. Result 타입 패턴 (`TypedDict`)

모든 반환값을 성공/실패 구조로 통일하는 패턴입니다.  
Go 언어의 `(result, error)` 튜플 반환 방식과 유사합니다.

```python
from typing import TypedDict

class ApiResult(TypedDict):
    ok: bool              # True=성공, False=실패
    data: dict | None     # 성공 시 실제 데이터
    error_code: str | None
    error_message: str | None


class PaymentClient:
    async def charge(self, user_id: str, amount: int) -> ApiResult:
        if self._is_blocked(user_id):
            return ApiResult(
                ok=False, data=None,
                error_code="BLOCKED_USER",
                error_message=f"차단된 사용자: {user_id}"
            )
        return ApiResult(
            ok=True,
            data={"transaction_id": "txn_abc123"},
            error_code=None, error_message=None
        )


# 핸들러에서 사용
result = await payment_client.charge(user_id, amount)
if not result["ok"]:                    # ok 필드로 즉시 판단
    return {"error": result["error_message"]}
return result["data"]                   # 성공 데이터 접근
```

| 장점 | 단점 |
|---|---|
| 모든 상황이 명시적 구조로 통일 | **기존 핸들러 전체 수정 필요** |
| `ok` 필드 하나로 성공/실패 즉시 판단 | 로거/미들웨어가 에러 감지 못함 |
| 타입 힌트로 IDE 자동완성 지원 | `result["data"]` 접근마다 `None` 체크 필요 |

---

### 방안 C. 서비스 레이어 분리 (아키텍처 개선)

라우터(핸들러)와 외부 API 클라이언트 사이에 비즈니스 로직을 담당하는 서비스 레이어를 추가합니다.

```
기존 구조:
  router/ ──────────────────────────────► clients/payment_client.py

개선 구조:
  router/ ──► services/payment_service.py ──► clients/payment_client.py
              비즈니스 룰 & 에러 처리 담당
```

```python
# app/services/payment_service.py (신규)
from app.clients.payment_client import PaymentClient, PaymentAccessDeniedError

class PaymentService:
    def __init__(self):
        self.client = PaymentClient()

    async def process_payment(self, user_id: str, amount: int) -> dict:
        """비즈니스 차단 처리, 데이터 변환을 한 곳에서 담당"""
        try:
            result = await self.client.charge(user_id, amount)
            return {
                "status": "success",
                "transaction_id": result["transaction_id"]
            }
        except PaymentAccessDeniedError as e:
            # 클라이언트 에러를 API 응답 형식으로 변환
            return {"status": "denied", "code": e.code, "message": e.message}


# app/routers/payment_router.py - 라우터는 입력/출력만 담당
@router.post("/charge")
async def charge_endpoint(user_id: str, amount: int):
    result = await payment_service.process_payment(user_id, amount)
    return result  # try/except 없이 깔끔
```

| 장점 | 단점 |
|---|---|
| 라우터는 "입력→서비스 호출→반환"만 담당 (단일 책임 원칙) | 파일/레이어 증가 (소규모엔 과함) |
| 비즈니스 로직이 서비스에 집중 → 테스트하기 좋음 | 초기 설계 비용 발생 |

---

## 3. 커스텀 예외 클래스 설계: 1개 vs 계층 구조

### 1개 클래스로 충분한 경우 (에러 케이스 2~3개 이하)

```python
class ApiClientError(Exception):
    """
    외부 API 클라이언트에서 발생하는 모든 에러를 하나의 클래스로 표현.
    code 필드로 종류를 구분한다.
    """
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# 사용: code 값으로 종류를 구분
raise ApiClientError(code="BLOCKED_USER", message="차단된 사용자입니다.")
raise ApiClientError(code="RATE_LIMIT",   message="요청 횟수를 초과했습니다.")
raise ApiClientError(code="TIMEOUT",      message="응답 시간이 초과되었습니다.")
```

```python
# 핸들러에서 code 문자열로 분기
try:
    result = await api_client.request(...)
except ApiClientError as e:
    if e.code == "BLOCKED_USER":
        return {"message": e.message}   # 친화적 메시지 반환
    raise HTTPException(status_code=500, detail=e.message)
```

### 계층 구조 (에러 케이스 4개 이상, 처리 방식이 각기 다름)

```python
class ApiClientError(Exception):
    """모든 API 클라이언트 에러의 공통 부모 클래스"""
    def __init__(self, message: str, code: str = "API_ERROR"):
        super().__init__(message)
        self.code = code
        self.message = message

# 하위 클래스: 처리 방식이 다른 케이스마다 분리
class ApiAccessDeniedError(ApiClientError):
    """접근 차단 (블랙리스트, 권한 없음)"""
    def __init__(self, user_id: str):
        super().__init__(
            message=f"접근이 차단된 사용자입니다. user_id={user_id}",
            code="ACCESS_DENIED"
        )

class ApiRateLimitError(ApiClientError):
    """요청 횟수 초과"""
    def __init__(self, retry_after: int):
        super().__init__(
            message=f"{retry_after}초 후 다시 시도해주세요.",
            code="RATE_LIMIT"
        )

class ApiTimeoutError(ApiClientError):
    """응답 시간 초과"""
    def __init__(self):
        super().__init__(message="외부 API 응답 시간이 초과되었습니다.", code="TIMEOUT")
```

```python
# 핸들러에서 타입으로 명확하게 분기 (문자열 비교 불필요)
try:
    result = await api_client.request(...)
except ApiAccessDeniedError as e:
    # 비즈니스 차단 → 사용자에게 친화적 메시지 반환
    return JSONResponse(status_code=403, content={"message": e.message})
except ApiRateLimitError as e:
    # 요청 횟수 초과 → 429 응답
    return JSONResponse(status_code=429, content={"message": e.message})
except ApiClientError as e:
    # 나머지 모든 API 에러 → 500 서버 에러
    raise HTTPException(status_code=500, detail=e.message)
```

---

## 4. 공통 부모 클래스(상속)를 쓰는 이유

핵심 이점은 **`except` 한 줄로 "이 모듈에서 나온 에러 전체"를 묶어서 처리**할 수 있다는 것입니다.

```python
# ❌ 공통 부모 없이 Exception을 각자 상속하면
class ApiAccessDeniedError(Exception): ...
class ApiRateLimitError(Exception): ...
class ApiTimeoutError(Exception): ...

# 핸들러에서 "나머지 다 잡기"가 안 됨 → 하나씩 명시해야 함
try:
    result = await api_client.request(...)
except ApiAccessDeniedError as e:
    return JSONResponse(status_code=403, content={"message": e.message})
except ApiRateLimitError as e:       # 에러 종류 늘어날수록 계속 추가
    raise HTTPException(status_code=429)
except ApiTimeoutError as e:         # 에러 종류 늘어날수록 계속 추가
    raise HTTPException(status_code=504)
```

```python
# ✅ 공통 부모 ApiClientError가 있으면
try:
    result = await api_client.request(...)
except ApiAccessDeniedError as e:
    return JSONResponse(status_code=403, content={"message": e.message})
except ApiClientError as e:
    # ← 나머지 모든 API 에러를 한 줄로 커버
    # ApiRateLimitError, ApiTimeoutError 등 미래에 추가되는 에러도 자동 포함됨
    raise HTTPException(status_code=500, detail=e.message)
```

**[문법 포인트] Python 예외 계층 탐색 순서**

```python
# Python은 위에서 아래로 except를 순서대로 비교한다.
# 더 구체적인 타입(하위 클래스)을 먼저, 더 일반적인 타입을 나중에 써야 한다.

try:
    ...
except ApiAccessDeniedError as e:  # 1순위: 더 구체적 (하위 클래스)
    ...
except ApiClientError as e:        # 2순위: 더 일반적 (상위 클래스)
    ...

# ❌ 순서가 반대면 ApiAccessDeniedError가 ApiClientError에 먼저 잡혀버림
# except ApiClientError:           ← ApiAccessDeniedError도 여기서 잡힘
# except ApiAccessDeniedError:     ← 영원히 실행 안 됨 (Dead Code)
```

---

## 5. API 핸들러에서의 처리 방식

비즈니스 차단(블랙리스트, 권한 없음)은 "시스템 장애"가 아닌 **"예측된 비즈니스 규칙"**입니다.  
따라서 사용자에게 "왜 안 되는지"를 명확히 돌려줘야 하므로 `return`으로 변환합니다.

```python
# app/routers/user_router.py (FastAPI 예시)
from fastapi import APIRouter
from app.clients.user_client import UserApiClient, ApiAccessDeniedError

router = APIRouter()

# 반드시 에러 클래스도 함께 import해야 한다 (누락 시 NameError 발생)
client = UserApiClient()

@router.get("/users/{user_id}/orders")
async def get_user_orders(user_id: str) -> list[dict]:
    try:
        result = await client.fetch_orders(user_id)
        # 정상 경로: 필요한 필드만 추려서 반환
        return [
            {"order_id": o["id"], "amount": o["total"], "status": o["status"]}
            for o in result.get("items", [])
        ]
    except ApiAccessDeniedError as e:
        # 비즈니스 차단 경로: 클라이언트가 이해할 수 있는 메시지로 변환
        # ⚠️ 반환 타입이 list[dict]이므로 에러도 list 안에 담아야 함
        return [{
            "status": "error",
            "code": e.code,
            "message": e.message
        }]
    # ApiClientError 외 예외는 잡지 않는다 → FastAPI의 예외 핸들러가 처리
```

**[실수 주의] 반환 타입 불일치**

```python
# ❌ 잘못된 예: 함수 반환 타입이 list[dict]인데 dict 반환
@router.get("/users/{user_id}/orders")
async def get_user_orders(user_id: str) -> list[dict]:
    ...
    except ApiAccessDeniedError as e:
        return {"status": "error", "message": e.message}  # ← dict! 타입 불일치

# ✅ 올바른 예: list[dict] 유지
        return [{"status": "error", "message": e.message}]  # ← list 안에 담기
```

---

## 6. 에러 처리 모듈화: 헬퍼 vs 데코레이터

API 핸들러 수가 많아질수록 `try/except` 블록을 반복 작성해야 하는 문제가 생깁니다.

### 헬퍼 함수 방식 (엔드포인트 5개 이하)

```python
# app/clients/user_client.py 하단에 추가

def make_error_list(e: ApiAccessDeniedError) -> list[dict]:
    """list[dict] 반환 타입의 핸들러에서 사용"""
    return [{"status": "error", "code": e.code, "message": e.message}]

def make_error_dict(e: ApiAccessDeniedError) -> dict:
    """dict 반환 타입의 핸들러에서 사용"""
    return {"status": "error", "code": e.code, "message": e.message}
```

```python
# 핸들러에서 사용
from app.clients.user_client import client, ApiAccessDeniedError, make_error_list

@router.get("/users/{user_id}/orders")
async def get_user_orders(user_id: str) -> list[dict]:
    try:
        result = await client.fetch_orders(user_id)
        return [serialize(o) for o in result.get("items", [])]
    except ApiAccessDeniedError as e:
        return make_error_list(e)   # 헬퍼 한 줄로 대체
```

---

### 데코레이터 방식 (엔드포인트 10개 이상) ⭐ 규모가 크면 권장

`try/except` 자체를 각 핸들러에서 완전히 제거합니다.

```python
# app/common/error_handler.py (신규 파일)
import functools
from app.clients.user_client import ApiAccessDeniedError


def handle_api_errors(as_list: bool = False):
    """
    ApiAccessDeniedError를 자동으로 잡아서 에러 응답으로 변환하는 데코레이터 팩토리.

    [문법 포인트] 데코레이터 팩토리란?
    - 데코레이터에 파라미터(as_list)를 받기 위해 함수를 한 겹 더 감싸는 패턴.
    - @handle_api_errors(as_list=True) 라고 쓰면:
        1. handle_api_errors(as_list=True) 가 먼저 호출 → decorator 함수 반환
        2. 반환된 decorator 가 실제 핸들러 함수(func)를 감쌈
        3. 이후 핸들러가 호출되면 wrapper가 실행됨

    Args:
        as_list (bool): True → 에러를 list[dict]로 반환 / False → dict로 반환
    """
    def decorator(func):
        @functools.wraps(func)
        # [문법 포인트] @functools.wraps(func):
        #   데코레이터로 감싸면 원본 함수의 __name__, __doc__ 등이 사라진다.
        #   wraps를 쓰면 원본 함수의 메타정보를 wrapper에 복사해 유지시킨다.
        #   FastAPI는 __name__으로 라우트를 등록하므로 wraps가 필수이다.
        async def wrapper(*args, **kwargs):
            # [문법 포인트] *args, **kwargs:
            #   어떤 함수든 감쌀 수 있도록, 인자를 타입/개수 지정 없이 전부 받아 넘긴다.
            #   *args → positional 인자를 tuple로, **kwargs → keyword 인자를 dict로 받음.
            try:
                return await func(*args, **kwargs)  # 원본 핸들러 실행
            except ApiAccessDeniedError as e:
                err = {"status": "error", "code": e.code, "message": e.message}
                return [err] if as_list else err    # 타입에 맞게 반환
        return wrapper
    return decorator
```

```python
# app/routers/user_router.py - try/except가 완전히 사라짐
from app.common.error_handler import handle_api_errors

@router.get("/users/{user_id}/orders")
@handle_api_errors(as_list=True)           # list[dict] 반환 핸들러
async def get_user_orders(user_id: str) -> list[dict]:
    result = await client.fetch_orders(user_id)
    return [serialize(o) for o in result.get("items", [])]
    # ↑ try/except 없어도 ApiAccessDeniedError는 데코레이터가 자동 처리


@router.get("/users/{user_id}")
@handle_api_errors(as_list=False)          # dict 반환 핸들러
async def get_user(user_id: str) -> dict:
    return await client.fetch_user(user_id)


@router.post("/users/{user_id}/orders")
@handle_api_errors()                       # as_list=False가 기본값이므로 생략 가능
async def create_order(user_id: str, body: dict) -> dict:
    return await client.create_order(user_id, body)
```

**`@functools.wraps` 없이 데코레이터 만들면 생기는 문제**:

```python
# wraps 없이 만들면
def decorator(func):
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper

@decorator
async def get_user_orders(user_id: str) -> list[dict]:
    """사용자의 주문 목록을 반환합니다."""
    ...

print(get_user_orders.__name__)   # 출력: "wrapper"           ← 이름이 사라짐!
print(get_user_orders.__doc__)    # 출력: None                ← 문서도 사라짐!
# FastAPI 라우팅이나 Swagger 문서에 잘못된 이름이 등록될 수 있음

# ✅ @functools.wraps(func) 사용 시
print(get_user_orders.__name__)   # 출력: "get_user_orders"  ✅
print(get_user_orders.__doc__)    # 출력: "사용자의 주문 목록..." ✅
```

---

## 7. 반환 타입이 혼재할 때의 대응

실제 API 서버에서는 엔드포인트마다 반환 타입이 다릅니다.

```python
# list[dict] 반환 → 목록 조회
@router.get("/users")               # → list[dict]
@router.get("/users/{id}/orders")   # → list[dict]

# dict 반환 → 단건 조회/생성/수정/삭제
@router.get("/users/{id}")          # → dict
@router.post("/users")              # → dict
@router.patch("/users/{id}")        # → dict
@router.delete("/users/{id}")       # → dict
```

**`as_list` 플래그 사용 가이드**:

```python
# 목록 조회 (GET /resources) → as_list=True
@handle_api_errors(as_list=True)
async def list_*(): ...

# 단건 조회/생성/수정/삭제 → as_list=False (기본값이므로 생략 가능)
@handle_api_errors()
async def get_*(): ...
async def create_*(): ...
async def update_*(): ...
async def delete_*(): ...
```

---

## 8. 전략 선택 기준 요약

```
에러를 어떻게 표현할 것인가?
 │
 ├─ 시스템 장애, 예측 불가능한 에러 (DB 연결 실패, 타임아웃 등)
 │    → raise Exception
 │    → FastAPI/로거가 자동으로 500 에러 처리
 │
 └─ 예측된 비즈니스 규칙 (블랙리스트, 권한 없음, 잔액 부족 등)
      → raise 커스텀예외 (ApiAccessDeniedError)
      → 핸들러에서 except → return {"status":"error",...}
      → 클라이언트가 이해할 수 있는 자연어 메시지로 변환
```

```
에러 처리를 어떻게 모듈화할 것인가?
 │
 ├─ 엔드포인트 수 적음 (5개 이하)
 │    → 헬퍼 함수 (make_error_list / make_error_dict)
 │
 ├─ 엔드포인트 수 많음 (10개 이상)
 │    → 파라미터 데코레이터 @handle_api_errors(as_list=Bool)
 │
 └─ 비즈니스 로직이 복잡해질 때
      → 서비스 레이어 분리 (router → service → client)
```

```
커스텀 예외 클래스는 몇 개?
 │
 ├─ 에러 케이스 2~3개, 처리 방식이 같음
 │    → 1개 클래스 + code 필드로 구분 (YAGNI 원칙)
 │
 └─ 에러 케이스 4개 이상, 처리 방식이 각기 다름
      → 공통 부모 클래스 + 하위 클래스 계층 구조
        (except 타입으로 명확하게 분기 가능)
```

> **YAGNI 원칙** (You Aren't Gonna Need It):  
> "지금 당장 필요하지 않은 설계는 만들지 말라." 코드가 단순할 때는 단순하게 유지한다.

---

## 9. HTTP 상태 코드별 커스텀 예외 변환 패턴

외부 API(`httpx` 등)를 호출할 때 `4xx/5xx` 응답이 오면, 상태 코드만으로는 "왜 실패했는지" 의미를 알기 어렵습니다.  
`httpx.HTTPStatusError`를 잡아서 **의미 있는 커스텀 예외로 변환하는 패턴**을 사용하면, 호출 레이어에서 에러 분기가 명확해집니다.

```python
# app/clients/api_client.py
import httpx

try:
    resp = await client.request(method, url, headers=headers, json=body)
    resp.raise_for_status()  # 4xx/5xx 응답 시 httpx.HTTPStatusError 발생
    return resp.json()

except httpx.HTTPStatusError as e:
    # [문법 포인트] httpx.HTTPStatusError는 httpx 라이브러리 자체 예외이므로
    # import 없이 `httpx.HTTPStatusError`로 직접 참조한다.
    # 별도 from httpx import HTTPStatusError 없이 사용 가능.
    status_code = e.response.status_code
    error_detail = f"{type(e).__name__}: {e}"

    # 상태 코드 → 커스텀 예외 변환
    if status_code == 400:
        raise ApiBadRequestError(error_detail)       # LLM에게 반환 가능
    elif status_code == 401:
        raise ApiUnauthorizedError(error_detail)     # 시스템 에러 (인프라 문제)
    elif status_code == 403:
        raise ApiForbiddenError(error_detail)        # 시스템 에러 (권한 문제)
    elif status_code == 404:
        raise ApiNotFoundError(error_detail)         # LLM에게 반환 가능
    raise e  # 위에서 처리 못한 나머지 HTTP 에러는 원본 그대로 throw

except Exception as e:
    # httpx.HTTPStatusError가 아닌 네트워크 오류, 타임아웃 등
    raise e
```

**왜 이렇게 하나?**  
`httpx.HTTPStatusError`는 단순히 "HTTP 응답이 4xx/5xx"라는 사실만 알려주지만,  
커스텀 예외로 바꾸면 호출 측에서 `except ApiNotFoundError`처럼 **의미 단위로 분기**할 수 있게 됩니다.

**설정 누락(ConfigError) 특이 케이스**:

```python
# 외부 API가 아닌, 서버 내부 설정이 누락된 경우도 같은 패턴으로 커스텀 예외화
class ApiConfigError(ApiClientError):
    """API 클라이언트 설정값(키, 시크릿 등)이 누락됐을 때 발생.
    이 에러는 개발자 또는 운영자가 .env를 수정해야 해결 가능하며,
    LLM 에이전트가 파라미터를 바꿔도 해결이 안 된다.
    따라서 데코레이터에서 잡히더라도 '관리자에게 문의하세요' 수준의 메시지로 전달된다.
    """
    def __init__(self, service_name: str):
        super().__init__(
            code="CONFIG_NOT_FOUND",
            message=f"{service_name} 설정이 없습니다. 관리자에게 문의하세요."
        )

# get_access_token() 내부에서:
if not client_id or not client_secret:
    raise ApiConfigError("PaymentGateway")  # ValueError 대신 커스텀 에러
```

> **설계 포인트**: `ApiConfigError`는 LLM이 받아봤자 파라미터를 바꿔서 해결할 수 없는 에러입니다.  
> 하지만 공통 부모(`ApiClientError`)로 관리하면 **데코레이터 한 곳에서 일관된 응답 구조**를 만들 수 있습니다.  
> "관리자에게 문의하세요" 라는 `message`가 LLM을 통해 사용자에게 전달되는 것 자체는 유효한 UX입니다.

---

## 10. message vs error 필드 분리 패턴

커스텀 예외에 `message` 필드 하나만 있을 때의 문제:

```python
# ❌ message 하나만 있으면:
class ApiBadRequestError(ApiClientError):
    def __init__(self, raw_error: str):
        super().__init__(code="BAD_REQUEST", message=f"잘못된 요청입니다. {raw_error}")
        # ↑ raw_error (기술적 상세 정보)가 message에 그대로 섞여버림
        # LLM에게도, 로그에도 너무 많은 정보가 노출됨
```

**해결: `message`와 `error`를 분리**

```python
class ApiClientError(Exception):
    def __init__(self, code: str, message: str, error: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message   # ← LLM/사용자에게 보여줄 "친화적 설명"
        self.error = error       # ← 개발자를 위한 "기술적 원인" (선택, 기본값 "")


class ApiBadRequestError(ApiClientError):
    def __init__(self, raw_error: str):            # raw_error: httpx가 준 원본 에러 메시지
        super().__init__(
            code="BAD_REQUEST",
            message="잘못된 요청입니다. 파라미터를 확인해주세요.",  # ← 사람/LLM 용
            error=raw_error                                      # ← 로그/디버그 용
        )

class ApiNotFoundError(ApiClientError):
    def __init__(self, raw_error: str):
        super().__init__(
            code="NOT_FOUND",
            message="요청한 리소스를 찾을 수 없습니다. 이메일 또는 ID를 확인해주세요.",
            error=raw_error
        )
```

**데코레이터에서 응답에 두 필드 모두 포함**:

```python
# app/common/error_handler.py
except ApiClientError as e:
    logger.warning(f"[LLM 반환 에러] {func.__name__} - {e.code}:{e.message}")
    rtn_dict = {
        "status": "error",
        "code": e.code,
        "message": e.message,    # LLM이 읽고 사용자에게 전달하는 메시지
        "error": e.error         # 로그 분석 및 디버깅용 원본 에러 (비어있을 수 있음)
    }
    return [rtn_dict] if as_list else rtn_dict
```

**실제 LLM 에이전트가 받는 결과 예시**:

```json
[
  {
    "status": "error",
    "code": "NOT_FOUND",
    "message": "요청한 리소스를 찾을 수 없습니다. 이메일 또는 ID를 확인해주세요.",
    "error": "HTTPStatusError: Client error '404 Not Found' ..."
  }
]
```

| 필드 | 대상 | 내용 성격 |
|---|---|---|
| `message` | LLM 에이전트, 사용자 | 짧고 명확한 한국어 설명 |
| `error` | 개발자, 로그 분석 | httpx 원본 에러 메시지, 스택 힌트 등 |

---

## 11. 실패 예시 & 해결 방법

### 실패 1: import 누락으로 NameError 발생

```python
# ❌ 실패 코드
from app.clients.user_client import UserApiClient

except ApiAccessDeniedError as e:          # NameError 발생!
    return make_error_list(e)

# ✅ 해결: 에러 클래스도 함께 import
from app.clients.user_client import UserApiClient, ApiAccessDeniedError
```

### 실패 2: 반환 타입 불일치

```python
# ❌ 실패 코드 (함수 반환 타입: list[dict])
async def get_user_orders(user_id: str) -> list[dict]:
    except ApiAccessDeniedError as e:
        return {"status": "error"}  # dict 반환 → 타입 불일치

# ✅ 해결: list 안에 담기
        return [{"status": "error"}]
```

### 실패 3: except 순서 실수 (Dead Code 발생)

```python
# ❌ 상위 클래스가 먼저 오면 하위 클래스가 절대 잡히지 않음
try:
    ...
except ApiClientError as e:           # 상위 클래스가 먼저 → 전부 여기서 잡힘
    raise HTTPException(status_code=500)
except ApiAccessDeniedError as e:     # 영원히 실행 안 됨 (Dead Code)
    return [{"message": e.message}]

# ✅ 해결: 구체적인 것(하위 클래스) 먼저
except ApiAccessDeniedError as e:     # 구체적 케이스 먼저
    return [{"message": e.message}]
except ApiClientError as e:           # 나머지 통합 처리
    raise HTTPException(status_code=500)
```

### 실패 4: 빈 `except:` 사용 (안티패턴)

```python
# ❌ 빈 except: 는 KeyboardInterrupt, SystemExit까지 잡아버림
try:
    result = await client.fetch_orders(user_id)
except:
    trace_id = "unknown"   # 어떤 에러인지 알 수 없음, 디버깅 불가

# ✅ 해결: 반드시 Exception 또는 구체적 타입 명시
except Exception as e:
    logger.error(f"예상치 못한 오류: {type(e).__name__}: {e}")
    trace_id = "unknown"
```

### 실패 5: `httpx.HTTPStatusError` 대신 `HTTPStatusError`만 쓰면 `NameError`

```python
# ❌ 실패 코드
except HTTPStatusError as e:        # NameError: name 'HTTPStatusError' is not defined
    status_code = e.response.status_code

# ✅ 해결: httpx 패키지를 앞에 붙여서 직접 참조
except httpx.HTTPStatusError as e:  # httpx가 이미 import 되어 있으므로 별도 import 불필요
    status_code = e.response.status_code

# 또는 from httpx import HTTPStatusError 로 명시적으로 import 후 사용
```

---

## 12. 학습 포인트 체크리스트

- [ ] `Exception`을 상속한 커스텀 예외 클래스를 만들 수 있다
- [ ] `super().__init__(message)`가 왜 필요한지 설명할 수 있다
- [ ] 공통 부모 클래스(예외 계층)를 사용하는 이유를 설명할 수 있다
- [ ] `except` 순서(구체적 → 일반적)가 왜 중요한지 설명할 수 있다
- [ ] 데코레이터와 데코레이터 팩토리의 차이를 설명할 수 있다
- [ ] `@functools.wraps(func)`가 왜 필요한지 설명할 수 있다
- [ ] `*args, **kwargs`로 임의 인자를 전달하는 방식을 이해한다
- [ ] 비즈니스 에러 vs 시스템 에러를 구분하고 처리 방식을 다르게 적용할 수 있다
- [ ] YAGNI 원칙을 설계에 적용할 수 있다
- [ ] 빈 `except:` 대신 `except Exception as e:`를 쓰는 이유를 설명할 수 있다
- [ ] `httpx.HTTPStatusError`를 상태 코드별 커스텀 예외로 변환하는 패턴을 구현할 수 있다
- [ ] `message`(사용자 대상)와 `error`(개발자 대상) 필드를 분리하는 이유를 설명할 수 있다
- [ ] 설정 누락(ConfigError) 에러를 `ValueError` 대신 커스텀 예외로 처리하는 이유를 설명할 수 있다

---

*이 가이드는 FastAPI 기반 Python API 서버의 외부 클라이언트 레이어 에러 처리 설계를 기준으로 작성되었습니다.*
