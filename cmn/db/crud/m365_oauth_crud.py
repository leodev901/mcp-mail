from cmn.db.models.m365_mcp_graph_info import M365McpGraphInfo
from cmn.db.models.m365_user_toekn import M365UserToken
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


async def get_graph_infos(db: AsyncSession, app_name: str) -> list[M365McpGraphInfo]:
    stmt = select(M365McpGraphInfo).where(M365McpGraphInfo.app_name == app_name)
    result = await db.execute(stmt)
    return result.scalars().all()



async def save_user_token(db: AsyncSession, user_token: M365UserToken) -> M365UserToken:
    existing = await get_user_app_token(
        db, 
        user_token.app_name, 
        user_token.user_id
    )

    
    if existing is None:
        # 새로 추가 
        db.add(user_token)
        # await db.commit()
        # await db.refresh(user_token)
        await db.flush()
        return user_token
    
    else: 
        # 기존 토큰 업데이트
        existing.access_token = user_token.access_token
        existing.refresh_token = user_token.refresh_token
        existing.expires_at = user_token.expires_at

        await db.flush()
        return existing



async def get_user_app_token(db:AsyncSession, app_name: str, user_id: str) -> M365UserToken:
    stmt = select(M365UserToken).where(M365UserToken.app_name == app_name, M365UserToken.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

