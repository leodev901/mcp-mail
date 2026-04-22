from fastapi import APIRouter
from cmn.core.dependencies import get_db_session_for_compnay
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request,Depends
from loguru import logger
from pydantic import BaseModel, Field
from uuid import UUID
from cmn.db.models.m365_mcp_tool_log import M365McpToolLog





logs_router = APIRouter(prefix="/api/logs",tags=["logs"])

class LogsToolsRequest(BaseModel):
    # id: UUID | None = None
    trace_id: UUID | None = None
    tool_name: str | None = None
    http_method: str | None = None
    http_status: int | None = None
    status: str | None = None
    message: str | None = None
    request_body: dict = Field(default_factory=dict)
    response_body: dict = Field(default_factory=dict)



@logs_router.post("/tool")
async def log_tool(
      request: Request,
      payload: LogsToolsRequest,
      db: AsyncSession = Depends(get_db_session_for_compnay) # 회사코드(company_cd)에 따라 해라서 해당 schema에 DB seesion 가져와서 저장
):

    tool_log = M365McpToolLog(
        trace_id=payload.trace_id,
        tool_name=payload.tool_name,
        http_method=payload.http_method,
        http_status=payload.http_status,
        status=payload.status,
        message=payload.message,
        request_body=payload.request_body,
        response_body=payload.response_body,
    )
    saved = await tool_log.save(db)
    if saved.id:
        return {"save": f"{saved.__tablename__} - {saved.id}"}
    else:
        return {"save" : "error"}


@logs_router.post("/graph")
async def log_grphs(db: AsyncSession = Depends(get_db_session_for_compnay)):
    # 회사코드(company_cd)에 따라 해라서 해당 schema에 DB seesion 가져와서 저장
    return {"status": "api logging"}