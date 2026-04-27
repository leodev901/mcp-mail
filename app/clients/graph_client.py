import json
import time
import asyncio
import httpx

from loguru import logger

from app.clients.http_client import get_httpx_client
from app.schema.log import ApiLogRequest
from app.schema.user import User
from app.common.exception import (
    GraphBadRequestError,
    GraphForbiddenError,
    GraphResourceNotFoundError,
    GraphUnauthorizedError,
)
from app.clients.mcp_cmn_client import save_external_api_log




GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _logging_message(
    record: ApiLogRequest
) -> None:
    """
    Graph 요청/응답 로그를 공통 포맷으로 남깁니다.
    trace_id 와 current_user 를 함께 기록하면 MCP tool 로그와 Graph API 로그를 같은 요청으로 연결할 수 있습니다.
    """

    message = f"[GraphAPI Request] >>> "
    message += f" trace_id={record.trace_id}"
    message += f" actor={record.actor}"
    message += f" provider={record.provider}"
    message += f" endpoint={record.endpoint}"
    message += f" status={record.status}"
    message += f" http_method={record.http_method}"
    message += f" http_status={record.http_status}"
    if record.message:
        message += f" message={record.message}"
    
    if record.request_body:
        req_body_json = json.dumps(record.request_body, ensure_ascii=False, indent=2)
        message += f"\n request={req_body_json}"
    if record.response_body:
        resp_body_json = json.dumps(record.response_body, ensure_ascii=False, indent=2)
        message += f"\n response={resp_body_json}"

    logger.info(message)
    
    #req_json = json.dumps(request_snapshot, ensure_ascii=False, indent=2)


async def graph_request(
    *,
    method: str,
    path: str,
    access_token: str,
    json_body: dict | None = None,
    custom_headers: dict | None = None,
    trace_id: str = "-",
    current_user: User | None = None,
) -> dict:
    """
    Microsoft Graph API 를 호출하는 공통 클라이언트 함수입니다.
    access_token 은 service 계층에서 명시적으로 넘기며, 이 함수는 토큰 발급/사용자 판단 같은 비즈니스 로직을 하지 않습니다.
    """

    url = f"{GRAPH_BASE}/me{path}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Prefer": 'outlook.timezone="Korea Standard Time"'
    }
    if custom_headers:
        # dict.update 는 기존 헤더 dict 에 추가 헤더를 병합하는 문법입니다.
        # Graph 의 ConsistencyLevel 같은 선택 헤더를 호출부에서 명시적으로 넘길 수 있게 합니다.
        headers.update(custom_headers)

    status_code = 500
    started_at = time.perf_counter()
    record = ApiLogRequest(
        trace_id=trace_id,
        actor=current_user.user_id if current_user else "-",
        provider="Microsoft Graph",
        endpoint=path,
        http_method=method.upper(),
    )


    try:
        client = await get_httpx_client()
        response = await client.request(
            method.upper(),
            url,
            headers=headers,
            json=json_body,
            timeout=30.0,
        )
        response.raise_for_status()
        
        if status_code == 204:
            return {"status_code": status_code, "status": "success"}

        response_data = response.json()
        
        record.status="success"
        record.http_status = response.status_code
        record.response_body = response_data

        return response_data
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        error_detail = f"{type(exc).__name__}: {exc}"

        record.status = "fail"
        record.http_status = status_code
        record.message = error_detail

        if status_code == 400:
            raise GraphBadRequestError(error_detail)
        if status_code == 401:
            raise GraphUnauthorizedError(error_detail)
        if status_code == 403:
            raise GraphForbiddenError(error_detail)
        if status_code == 404:
            raise GraphResourceNotFoundError(error_detail)
        raise
    except Exception as exc:
        error_detail = f"{type(exc).__name__}: {exc}"
        record.status = "fail"
        record.message = error_detail
        raise
    finally:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        _logging_message( record )

        asyncio.create_task(save_external_api_log(record))
