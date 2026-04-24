from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cmn.db.models.m365_mcp_graph_info import M365McpGraphInfo
from cmn.db.models.m365_user_toekn import M365UserToken
from cmn.base.logger import logger

class AuthRepository:
    def __init__(self, session: AsyncSession):
        self.session = session


    # MS Crendetail 정보 조회 
    async def get_graph_infos(self, app_name: str) -> list[M365McpGraphInfo]:
        stmt = select(M365McpGraphInfo).where(M365McpGraphInfo.app_name == app_name)
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    
    # 사용자 토큰 저장 (신규추가 or 업데이트)
    async def save_user_token(self, user_token: M365UserToken) -> M365UserToken:
        """사용자 토큰을 새로 저장 또는 갱신합니다."""
        
        # 기존 토큰 조회 
        existing = await self.get_user_token(
            user_token.app_name, 
            user_token.user_id
        )
        
        # 존재하지 않으면 신규 추가 - add
        if existing is None:
            logger.debug(f"Insert new user token: {user_token.user_id} for {user_token.app_name}")
            self.session.add(user_token)
            await self.session.flush()
            return user_token
        
        # 기존 토큰 업데이트
        else:
            logger.debug(f"Update user token: {existing.user_id} for {existing.app_name}")
            existing.access_token = user_token.access_token
            existing.refresh_token = user_token.refresh_token
            existing.expires_at = user_token.expires_at

            await self.session.flush()
            return existing


    async def get_user_token(self, app_name: str, user_id: str) -> M365UserToken | None:
        stmt = select(M365UserToken).where(M365UserToken.app_name == app_name, M365UserToken.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    
