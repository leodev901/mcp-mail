from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware


from cmn.api.routers import register_router
from cmn.core.database import Database
from cmn.core.config import settings
from cmn.base.logger import logger
from cmn.base.exception import register_exception_handler
from cmn.base.middleware import RequestLoggingMiddleware
from cmn.base.opentelemetry import setup_opentelemetry, shutdown_opentelemetry









BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


if settings.ENV.lower() == "local":
    PREFIX = ""
else : 
    PREFIX = "/mcp-cmn"
   


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시 비동기 DB 엔진을 한 번 만든다.
    # engine = create_engine()
    # app.state.engine = engine
    # session_factory = async_sessionmaker(engine, expire_on_commit=False)
    # Direct OTLP는 앱 시작 시 1회만 연결합니다.
    # 왜냐하면 로거 handler와 provider는 요청마다 붙이는 자원이 아니라 앱 전역 자원이기 때문입니다.
    setup_opentelemetry()
    logger.info("Starting mcp-cmn server...")
    db = Database()
    app.state.db = db


    # yield 이전 구간은 startup, yield 이후 구간은 shutdown 이다.
    yield

    logger.info("Shutting down mcp-cmn server...")
    # 종료 시 엔진 연결 풀을 정리한다.
    # await engine.dispose()
    await db.dispose()
    shutdown_opentelemetry()




def create_app() -> FastAPI:
    # FastAPI 앱을 만들고 lifespan 훅과 라우터를 연결한다.
    app = FastAPI(
        title="MCP-CMN APIs",
        lifespan=lifespan,
        root_path=PREFIX,
    )

    # 라우터 등록
    register_router(app)

    # Exception 핸들러 등록
    register_exception_handler(app)

    # 미들웨어 등록
    app.add_middleware(RequestLoggingMiddleware)

    # # CORS 미들웨어 추가 (프론트엔드 호출 허용) - 가장 마지막에 추가
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], # 실무에서는 Vercel 도메인으로 특정하는 것이 안전합니다.
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app


app = create_app()


# ==================================================
# 정적 Swager UI 사용
# ==================================================




app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url=f"{PREFIX}/docs")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=f"{PREFIX}{app.openapi_url}",
        title=f"{app.title} - Swagger UI",
        # 정적 파일 경로에 Prefix 추가
        swagger_js_url=f"{PREFIX}/static/swagger-ui-bundle.js",
        swagger_css_url=f"{PREFIX}/static/swagger-ui.css",
        swagger_favicon_url=f"{PREFIX}/static/favicon.png"
    )
