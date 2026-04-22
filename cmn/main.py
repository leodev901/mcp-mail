from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles


from cmn.api.routers import register_router
from cmn.core.database import Database
from cmn.core.config import settings


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


if settings.ENV.lower() == "local":
    PREFIX = ""
else : 
    PREFIX = "/abiz-mcp-cmn"
   


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
        root_path=PREFIX,
    )


    # 라우터 등록
    register_router(app)

    # 미들웨어 등록


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