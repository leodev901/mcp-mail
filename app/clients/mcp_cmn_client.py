from __future__ import annotations

from typing import Any

from loguru import logger
from pydantic import BaseModel, Field
from fastmcp.server.dependencies import get_http_request


from app.clients.http_client import get_httpx_client
from app.core.config import settings
from app.schema.credentials import MyAccessToken
from app.schema.log import ToolLogRequest, ApiLogRequest





def _get_biz_user_token() -> str:
    try:
        request = get_http_request()
    except RuntimeError:
        return "unknown"
    return getattr(request.state, "biz_user_token", "unknown")


def _get_trace_id() -> str:
    try:
        request = get_http_request()
    except RuntimeError:
        return "unknown"
    return getattr(request.state, "trace_id", "unknown")
    


async def fetch_user_context_from_mcp_cmn(
    biz_user_token: str,
    app_name: str | None = None,
) -> MyAccessToken:
    """
    CMN 의 사용자 위임 토큰 API를 호출해 tool 실행에 필요한 사전 컨텍스트를 가져옵니다.
    """

    resolved_app_name = (app_name or settings.M365_USER_TOKEN_APP_NAME).strip().upper()
    
    url = (
        f"{settings.CMN_API_BASE_URL.rstrip('/')}"
        f"/api/oauth/user/token/{resolved_app_name}"
    )
    headers = {
        "Authorization": f"Bearer {biz_user_token}",
        "Accept": "application/json",
    }

    logger.debug(f"CMN tool context request url={url} app_name={resolved_app_name}")

    client = await get_httpx_client()
    response = await client.get(
        url,
        headers=headers,
    )

    response.raise_for_status()

    try:
        response_payload: dict[str, Any] | None = response.json()
    except ValueError:
        response_payload = None

    data = response_payload.get("data")
    
    return MyAccessToken.model_validate(data)




async def save_mcp_tool_log(
    record: ToolLogRequest
):
    url = (
        f"{settings.CMN_API_BASE_URL.rstrip('/')}"
        f"/api/logs/tool"
    )
    headers = {
        "Accept": "application/json",
        "x-trace-id": _get_trace_id(),
        "Authorization": f"Bearer {_get_biz_user_token()}",
    }

    client = await get_httpx_client()

    try:
        response = await client.post(
            url,
            headers=headers,
            json=record.model_dump(mode="json"),
        )
        response.raise_for_status()
    except: 
        logger.error("Fail to save mcp tool log")
    


async def save_external_api_log(
    record: ApiLogRequest
):
    url = (
        f"{settings.CMN_API_BASE_URL.rstrip('/')}"
        f"/api/logs/api"
    )
    headers = {
        "Accept": "application/json",
        "x-trace-id": _get_trace_id(),
        "Authorization": f"Bearer {_get_biz_user_token()}",
    }

    client = await get_httpx_client()

    try:
        response = await client.post(
            url,
            headers=headers,
            json=record.model_dump(mode="json"),
        )
        response.raise_for_status()
    except: 
        logger.error("Fail to save external api log")



    
