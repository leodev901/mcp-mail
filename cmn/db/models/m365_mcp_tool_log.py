from uuid import UUID

from sqlalchemy import BigInteger, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession

from cmn.db.models.base import AuditMixin, Base

class M365McpToolLog(Base, AuditMixin):
    __tablename__ = "m365_mcp_tool_log"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), comment="로그 고유 ID")
    trace_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, comment="호출 요청 추적 ID")
    tool_name: Mapped[str | None] = mapped_column(String, nullable=True, comment="도구 이름")
    http_method: Mapped[str | None] = mapped_column(String, nullable=True, comment="HTTP 메소드")
    http_status: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="HTTP 상태 코드")
    status: Mapped[str | None] = mapped_column(String, nullable=True, comment="처리 상태")
    message: Mapped[str | None] = mapped_column(String, nullable=True, comment="메시지")
    request_body: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="요청 바디(JSON)")
    response_body: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="응답 바디(JSON)")

    async def save(self, db: AsyncSession) -> "M365McpToolLog":
        # 이 모델은 저장만 하므로 save를 아주 얇게 둔다.
        # - 로깅은 비즈니스 규칙이 거의 없고,
        # - 별도 CRUD 레이어를 만들면 오히려 과해질 수 있기 때문이다.
        db.add(self)
        # dependencies.py에서 스키마에 따라 세션 열결 할 때 이미 트랜잭션을 begin 하고 있기 때문에 여기서 commit 사용 안됨
        # await db.commit()
        # await db.refresh(self)
        await db.flush()
        return self

    