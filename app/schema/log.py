from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field


class ToolLogRequest(BaseModel):
    # id: UUID | None = None
    trace_id: UUID | None = None
    tool_name: str | None = None
    http_method: str | None = None
    http_status: int | None = None
    status: str | None = None
    message: str | None = None
    request_body: dict = Field(default_factory=dict)
    response_body: dict = Field(default_factory=dict)

class ApiLogRequest(BaseModel):
    # id: UUID | None = None
    trace_id: Annotated[UUID, Field(...,description="호출 요청 추적 ID")]
    actor: Annotated[str, Field(...,description="외부 API 호출자",examples=["20075487"])]
    provider: str | None = None
    endpoint: str | None = None
    http_method: str | None = None
    http_status: int | None = None
    status: str | None = None
    message: str | None = None
    request_body: dict = Field(default_factory=dict)
    response_body: dict = Field(default_factory=dict)