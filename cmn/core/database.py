from collections.abc import AsyncGenerator
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from cmn.core.config import settings

from cmn.base.logger import logger

# 데이터베이스 URL은 환경 설정에서 읽어 옵니다.
DATABASE_URL = settings.DATABASE_URL
COMPANY_CODES = settings.COMPANY_CODES


class Database:
    # DB 연결과 세션 팩토리를 한 곳에 모아 둡니다.
    #
    # - engine 은 앱 전역 자원이라 한 번만 만들고,
    # - session 은 요청/작업 단위 자원이라 필요할 때마다 새로 만듭니다.
    def __init__(self) -> None:
        logger.info("---- create datbase engein -----")
        logger.info(f"DATABASE_URL = {DATABASE_URL}")

        # engine 은 실제 DB 연결 풀을 관리하는 전역 객체입니다.
        # 요청마다 새 engine 을 만들면 비용이 크므로 앱 시작 시 한 번만 만듭니다.
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

        # async_sessionmaker 는 필요할 때마다 새 AsyncSession 을 만드는 공장입니다.
        # 세션은 공유하지 않고 작업 단위로 나눠 써야 안전합니다.
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    def get_engine(self) -> AsyncEngine:
        return self.engine
    
    async def dispose(self) -> None:
        # 앱 종료 시 engine 이 가진 연결 자원을 정리합니다.
        logger.info("---- dispose datbase engein -----")
        await self.engine.dispose()


    # Databse 에서는 오직 '세션 연결'을 담당하며 '트랜젝션'에 대한 부분은 
    def session(self, schema: str ):
        """
        - 이 함수는 `async with db.session("company") as session:` 형태로 쓰기 위한
          비동기 컨텍스트 매니저 객체를 반환합니다.
        - 즉, 여기서 바로 `AsyncSession` 을 주는 것이 아니라 `__aenter__` 와
          `__aexit__` 메서드를 가진 내부 클래스를 만들어 `async with` 문법으로
          세션을 열고 닫게 합니다.
        """
        schema = schema.strip() 
        if schema not in COMPANY_CODES:
            raise ValueError(f"Invalid schema: {schema}")
        logger.debug(f"get_db_session: {schema}")

        session = self.session_factory()

        class _SessionContext:
            async def __aenter__(self) -> AsyncSession:
                # `schema` 가 있으면 PostgreSQL 의 기본 조회 schema(search_path)를 바꿉니다.
                # `await` 를 쓰는 이유는 `session.execute(...)` 가 실제 DB I/O 이기 때문입니다.
                if schema:
                    # `SET LOCAL search_path TO ...`
                    # - 현재 트랜잭션 안에서만 유효합니다.
                    # - 트랜잭션이 끝나면 원래 설정으로 돌아가므로 요청 간 schema 오염 위험이 더 낮습니다.
                    #
                    # 반대로 `SET search_path TO ...` 는 현재 연결(connection)에 설정이 남습니다.
                    # 즉 같은 연결을 pool 이 재사용하면 다음 요청도 이전 schema 를 볼 수 있어
                    # 멀티 테넌트 환경에서는 더 조심해서 써야 합니다.
                    await session.execute(text(f"SET search_path TO {schema}"))
                return session

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                # `async with` 블록이 끝나면 세션을 닫아 커넥션을 빨리 반환합니다.
                # 이렇게 해야 외부 API 호출 대기 동안 DB 자원을 오래 점유하지 않습니다.
                await session.close()

        return _SessionContext()

