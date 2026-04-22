from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cmn.db.models.m365_mcp_graph_info import M365McpGraphInfo

class AuthRepository:
    def __init__(self, session: AsyncSession):
        self.session = session


    # MS Crendetail 정보 조회 
    async def get_graph_infos(self, app_name: str) -> list[M365McpGraphInfo]:
        stmt = select(M365McpGraphInfo).where(M365McpGraphInfo.app_name == app_name)
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    
