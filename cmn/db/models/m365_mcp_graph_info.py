# create table leodev901.m365_mcp_graph_info (
#   app_name character varying not null,
#   key character varying not null,
#   value text null,
#   created_at timestamp with time zone not null default now(),
#   updated_at timestamp with time zone null default now(),
#   constraint m365_mcp_graph_info_pkey primary key (app_name, key)
# ) TABLESPACE pg_default;

from cmn.db.models.base import Base, AuditMixin
from sqlalchemy import String, Text, select
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession



class M365McpGraphInfo(Base, AuditMixin):
    __tablename__ = "m365_mcp_graph_info"

    app_name: Mapped[str] = mapped_column(String, primary_key=True, comment="앱 이름")
    key: Mapped[str] = mapped_column(String, primary_key=True, comment="설정 키")
    value: Mapped[str | None] = mapped_column(Text, nullable=True, comment="설정 값")



async def get_graph_infos(db: AsyncSession, app_name: str) -> list[M365McpGraphInfo]:
    stmt = select(M365McpGraphInfo).where(M365McpGraphInfo.app_name == app_name)
    result = await db.execute(stmt)
    return result.scalars().all()
