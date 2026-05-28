from fastapi import APIRouter, Path, Query
from cmn.core.dependencies import get_db_session_authorize_header
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from cmn.db.models.mcp_log import M365McpToolLog, M365McpApiLog
from cmn.schemas.logs import ToolLogRequest, ApiLogRequest
from cmn.schemas.response import CommonResponse
from cmn.base.logger import logger
from sqlalchemy import func, select, text


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


@logs_router.get("/api/{provider}/count", response_model=CommonResponse)
async def get_api_log_count(
    provider: str = Path(..., description="apilog를 조회할 사용자 식별자", example="user@test.com"),
    interval: int = Query(10,description="apilog를 조회 interval 시간 (단위: 분)"),
    session: AsyncSession = Depends(get_db_session_authorize_header),
):
    # where()는 SQL의 WHERE 절을 만드는 SQLAlchemy 문법입니다.
    # DB 서버 시간을 기준으로 최근 10분 로그만 세면, 앱 서버와 DB 서버의 시간 차이 영향을 줄일 수 있습니다.
    stmt = select(func.count()).select_from(M365McpApiLog).where(
        M365McpApiLog.provider == provider,
        M365McpApiLog.created_at >= func.now() - text(f"interval '{interval} minutes'"),
    )
    result = await session.execute(stmt)
    count = result.scalar_one()

    return CommonResponse.ok({"count": count})
