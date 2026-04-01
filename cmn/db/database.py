from collections.abc import AsyncGenerator
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine,async_sessionmaker
from sqlalchemy.pool import NullPool

from cmn.core.config import settings

from loguru import logger

# 데이터베이스 URL은 환경 설정에서 읽어온다.
DATABASE_URL = settings.DATABASE_URL
COMPANY_CODES = settings.COMPANY_CODES

class Database:
    # DB 연결과 세션 팩토리를 한 곳에 묶는다.
    # 왜:
    # - engine은 앱 전역 자원이고,
    # - session은 요청 단위 자원이라 함께 관리하면 구조가 단순해진다.
    def __init__(self ) -> None:
        logger.info("---- create datbase engein -----")
        logger.info(f"DATABASE_URL = {DATABASE_URL}")
        # engine 커넥션 풀을 관리하는 앱 전역 객체다.
        # - 요청마다 새로 만들면 비효율적이기 때문이다.
        self.engine = create_async_engine(
        url=DATABASE_URL,
        echo=True,
        future=True,
        pool_pre_ping=True,
        poolclass=NullPool,
        connect_args={
            "prepared_statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
        },
    )
        # async_sessionmaker는 요청마다 새 AsyncSession을 만드는 팩토리다.
        # - 세션은 공유하지 않고 요청 단위로 분리해야 안전하기 때문이다.
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
        # 앱 종료 시 커넥션 풀을 정리한다.
        logger.info("---- dispose datbase engein -----")
        await self.engine.dispose()

    async def get_session_schema(self, schema:str)->AsyncGenerator[AsyncSession, None]:
        
        schema = schema.strip()
        if schema not in COMPANY_CODES:
            logger.error(f"회사코드 스키마 {schema}는 정의되어 있지 않습니다.")
            raise ValueError(f"회사코드 스키마 {schema}는 정의되어 있지 않습니다.")

        # 회사별 스키마를 적용한 세션을 제공한다.
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
    




    
    

    
    
    