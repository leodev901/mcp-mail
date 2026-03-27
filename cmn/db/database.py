from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine,async_sessionmaker
from cmn.core.config import settings

from loguru import logger

# 데이터베이스 URL은 환경 설정에서 읽어온다.
DATABASE_URL = settings.DATABASE_URL

class Database:
    def __init__(self ) -> None:
        logger.info("---- create datbase engein -----")
        self.engine = create_async_engine(
            url=DATABASE_URL,
            echo=True,
            future=True,
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine, 
            class_=AsyncSession,
            expire_on_commit=False,

        )
    
    def get_engine(self) -> AsyncEngine:
        return self.engine
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_factory() as session:
            yield session   
    
    async def dispose(self) -> None:
        logger.info("---- dispose datbase engein -----")
        await self.engine.dispose()

    async def get_session_schema(self, schema:str)->AsyncGenerator[AsyncSession, None]:

        async with self.session_factory() as session:
        # 트랜잭션 안에서만 search_path를 바꾸기 위해 begin()을 엽니다.
        # 왜:
        # - SET LOCAL은 현재 트랜잭션 안에서만 유효하고,
        # - 트랜잭션 종료 시 자동으로 원복되어 커넥션 풀 오염을 줄입니다.
            async with session.begin():
                # 주의:
                # - schema_name은 외부 입력을 직접 넣는 값이 아니라
                #   서버 내부 매핑 결과여야 합니다.
                await session.execute(text(f"SET LOCAL search_path TO {schema}"))

                # 이제부터 이 세션은 해당 회사 스키마를 기본 스키마처럼 사용합니다.
                yield session
    




    
    

    
    
    