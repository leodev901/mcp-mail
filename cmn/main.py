from contextlib import asynccontextmanager

from fastapi import FastAPI

from cmn.api.routers import register_router
from cmn.db.database import Database


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시 비동기 DB 엔진을 한 번 만든다.
    # engine = create_engine()
    # app.state.engine = engine
    # session_factory = async_sessionmaker(engine, expire_on_commit=False)
    db = Database()
    app.state.db = db


    # yield 이전 구간은 startup, yield 이후 구간은 shutdown 이다.
    yield

    # 종료 시 엔진 연결 풀을 정리한다.
    # await engine.dispose()
    await db.dispose()
    


def create_app() -> FastAPI:
    # FastAPI 앱을 만들고 lifespan 훅과 라우터를 연결한다.
    app = FastAPI(
        title="MCP-CMN APIs",
        lifespan=lifespan,
    )

    register_router(app)

    return app


app = create_app()
