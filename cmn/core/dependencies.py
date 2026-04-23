from fastapi import Request, Depends, Header, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from cmn.core.database import Database
from cmn.schemas.user import User
from cmn.utils import jwt_manager

from loguru import logger



# db engine을 그대로 받아서 서비스에서 세션 연결
async def get_db(request: Request):
     return request.app.state.db

async def get_db_session_for_compnay(
        request: Request,
        schema: str = Header(..., alias="X-Company-Code")
) -> AsyncGenerator[AsyncSession , None]:
    
    schema = schema.strip()
    if not schema:
        logger.error(f"X-Company-Code is required: {schema}")
        raise HTTPException(status_code=400, detail="X-Company-Code is required")
    
    logger.info(f"get_company_schema: {schema}")
    db: Database = request.app.state.db

    async for session in db.get_session_schema(schema):
        yield session

# oauth m365 콜백에서 회사코드로 DB 세션 연결 
async def get_db_session_for_oauth_state(
    request: Request,
    state: str = Query(...),
) -> AsyncGenerator[AsyncSession , None]:
    
    if not state or "." not in state:
         raise HTTPException(status_code=400, detail="Invalid state format")

    company_code = state.split(".", 1)[0].strip()

    if not company_code:
        raise HTTPException(status_code=400, detail="Missing company code in state")
    
    db: Database = request.app.state.db
    
    async for session in db.get_session_schema(company_code):
            yield session




     
     