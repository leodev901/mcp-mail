from fastapi import APIRouter
from cmn.core.dependencies import get_db_session_for_compnay, get_db_session_authorize_header
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from cmn.db.models.mcp_log import M365McpToolLog, M365McpApiLog
from cmn.schemas.logs import ToolLogRequest, ApiLogRequest
from cmn.schemas.response import CommonResponse
from cmn.base.logger import logger


logs_router = APIRouter(prefix="/api/logs",tags=["logs"])



@logs_router.post("/tool", response_model=CommonResponse)
async def save_tool_log(
      payload: ToolLogRequest,
      session: AsyncSession = Depends(get_db_session_authorize_header)
):
    # MCPToolLog 저장 모델
    # Pydantic BaseModel -> SQLAlchemy Model로 주입 할 때 필드명이 같다면 **dict 형식으로 넣을 수 있음
    # Pydantic BaseModel 의 model_dump() 함수를 활용
    # tool_log = M365McpToolLog(
    #     trace_id=payload.trace_id,
    #     tool_name=payload.tool_name,
    #     http_method=payload.http_method,
    #     http_status=payload.http_status,
    #     status=payload.status,
    #     message=payload.message,
    #     request_body=payload.request_body,
    #     response_body=payload.response_body,
    # )
    
    tool_log = M365McpToolLog(**payload.model_dump())
    saved = await tool_log.save(session)

    if saved.id:
        logger.debug(f"save: {saved.__tablename__} - {saved.id}")
        return CommonResponse.ok(
            { "save": f"{saved.__tablename__} - {saved.id}"}
        )
    else:
        return CommonResponse.error("Tool Log 저장 실패")

@logs_router.post("/api", response_model=CommonResponse)
async def save_api_log(
    payload: ApiLogRequest,
    session: AsyncSession = Depends(get_db_session_authorize_header),
):
    api_log = M365McpApiLog(**payload.model_dump())
    saved = await api_log.save(session)
    
    if saved.id:
        logger.debug(f"save: {saved.__tablename__} - {saved.id}")
        return CommonResponse.ok({ "save": f"{saved.__tablename__} - {saved.id}"})
    else:
        return CommonResponse.error("Api Log 저장 실패")


