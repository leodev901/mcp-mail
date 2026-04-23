from fastapi import Request, Depends, Header, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from cmn.core.database import Database
from cmn.schemas.user import User
from cmn.utils import jwt_manager

from loguru import logger




async def get_db(request: Request):
     """reqeust.state.app에 저장된 db engine을 그대로 반환"""
     return request.app.state.db


async def get_db_session_authorize_header(
    db: Database = Depends(get_db),
    user: User = Depends(jwt_manager.get_current_user)
) -> AsyncGenerator[AsyncSession , None]:
    """Request 헤더의 요청 Authroze(Bearer Token) 으로부터 사용자 정보를 파싱하여 회사 코드로 DB 세션 연결"""
    schema = user.company_code
    logger.debug(f"get_db_session_authorize: {schema}")

    async with db.session(schema) as session:
        try:
            yield session
            await session.commit() # 세션에서 DB 작업이 정상적으로 끝나면 commit 으로 마무리 

        except DBAPIError as exc:
            await session.rollback() # DB 예외가 나면 Rollback
            logger.error(f"Databse 실행 오류: {exc}")
            raise exc
        except Exception:
            await session.rollback() # 비즈니스 예외도 Rollback
            raise


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




     
     