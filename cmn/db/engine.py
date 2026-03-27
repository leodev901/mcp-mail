from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from cmn.core.config import settings

from loguru import logger

# 데이터베이스 URL은 환경 설정에서 읽어온다.
DATABASE_URL = settings.DATABASE_URL


def create_engine() -> AsyncEngine:
    # AsyncEngine은 비동기 DB 연결을 관리하는 객체다.
    # 앱 시작 시 한 번 생성하고, 종료 시 dispose()로 정리한다.
    logger.info("---- create datbase engein -----")
    return create_async_engine(
        DATABASE_URL,
        echo=True,
        future=True,
        pool_pre_ping=True,
    )
