from fastapi import Request, Depends, Header
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from cmn.db.database import Database


async def get_company_schema(
        request: Request,
        schema: str = Header(..., alias="X-Company-Code")
) -> AsyncGenerator[AsyncSession , None]:
    db: Database = request.app.state.db

    async for session in db.get_session_schema():
        yield session