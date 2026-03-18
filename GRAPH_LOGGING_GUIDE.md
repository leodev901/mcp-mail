# Graph API 호출/응답 로깅 가이드 (Study)

이 문서는 Microsoft Graph API 를 호출할 때 발생하는 요청(Request)과 응답(Response) 데이터를 어떻게 구조화하여 기록(Logging/DB)할 수 있는지에 대한 설계와 실습 코드를 담고 있습니다.

> [!IMPORTANT]
> 이 가이드는 학습 및 설계 목적으로 작성되었으며, 실제 프로젝트 코드는 수정하지 않습니다.

---

## 1. 문제 정의
현재 `graph_client.py`는 API 호출 결과를 로깅 없이 즉시 반환하고 있습니다. 디버깅과 감사(Audit), 성능 분석을 위해 다음과 같은 정보의 기록이 필요합니다.
- 어떤 사용자가(Who), 언제(When), 어떤 경로로(Where) 요청했는가?
- 요청 본문(Body)과 결과(Status/Response)는 무엇인가?
- 응답까지 시간이 얼마나 걸렸는가? (Latency)

## 2. 접근 방법 및 데이터 설계
가장 효율적인 방법은 개별 `tool` 파일이 아닌, Graph API 호출을 전담하는 공통 함수(`graph_request`) 내부에서 로깅을 가로채어 기록하는 것입니다.

### 제안 스키마 (JSON 형태)
```json
{
  "context": {
    "trace_id": "req-12345",
    "timestamp": "2026-03-13T14:23:14Z",
    "company_cd": "leodev901",
    "user_email": "admin@leodev901.onmicrosoft.com"
  },
  "request": {
    "method": "GET",
    "url": "https://graph.microsoft.com/v1.0/users/.../calendarView?...",
    "body": null
  },
  "response": {
    "status_code": 200,
    "payload_summary": "{ 'value': [...] }",
    "latency_ms": 150.5
  },
  "error": null
}
```

---

## 3. 실습 코드 예시 (Concept Only)

실제 소스 코드를 건드리지 않고, `graph_client.py`에 적용할 수 있는 가상의 개선 코드입니다.

### [EX] `app/clients/graph_client.py` 상상해보기
```python
import time
from loguru import logger
from fastmcp.server.dependencies import get_http_request

async def graph_request_with_logging(method, path, user_email=None, json_body=None, company_cd="leodev901"):
    # 1. 컨텍스트 확보 (trace_id 등)
    try:
        req = get_http_request()
        trace_id = getattr(req.state, "trace_id", "internal")
    except:
        trace_id = "unknown"

    start_time = time.perf_counter() # 타이머 시작
    url = f"{GRAPH_BASE}/users/{user_email}{path}"
    
    # [Pre-Log] 요청 시작 기록
    logger.info(f"[GraphAPI Request] {method} {url} | Trace: {trace_id}")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.request(method, url, json=json_body)
            # 2. 결과 처리
            resp_json = resp.json()
            status_code = resp.status_code
            error_detail = None
    except Exception as e:
        resp_json = None
        status_code = 500
        error_detail = str(e)
        raise e
    finally:
        # 3. 지연 시간 계산 및 최종 기록
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        # 나중에 DB insert 로 쉽게 전환 가능한 구조화된 로그
        log_data = {
            "trace_id": trace_id,
            "method": method,
            "url": url,
            "request_body": json_body,            # <--- 요청 본문 추가
            "status_code": status_code,
            "response_body": resp_json,           # <--- 응답 본문 추가 (필요시 요약 가능)
            "latency_ms": round(latency_ms, 2),
            "error": error_detail
        }
        
        # 지금은 로거로, 나중엔 DB 처리 함수로!
        logger.bind(payload=log_data).info("Graph API Transaction Log")
        
    return resp_json
```

---

## 4. 왜 이렇게 해야 하나요?
1. **중앙 집중화**: 한 곳(`graph_request`)만 관리하면 모든 `calendar_tools`, `mail_tools` 등의 로그가 자동으로 기록됩니다.
2. **트레이싱**: `trace_id`를 함께 저장하면 사용자의 한 번의 요청이 어떤 API 호출들을 유발했는지 한눈에 꿸 수 있습니다.
3. **DB 전환 용이성**: 로그를 `dict` 형태로 모델링해두면, `insert_into_db(log_data)` 한 줄로 기능을 확장할 수 있습니다.

---

## 5. 한 줄 요약
**"API 호출 공통 함수 내부에 타이머와 컨텍스트(trace_id)를 포함한 구조화된 딕셔너리를 구성하여 로깅함으로써, 성능 모니터링과 DB 저장 확산성을 동시에 확보한다."**
