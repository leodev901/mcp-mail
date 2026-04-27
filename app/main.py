from fastmcp import FastMCP

from app.core.http_middleware import HttpMiddleware
from app.core.http_asgi_middleware import HttpLoggingASGIMiddleware
from app.core.mcp_midleware import MCPExceptionMiddleware, MCPLoggingMiddleware
from app.tools.mail_tools import register_mail_tools
from app.common.logger import init_logger


def create_app():
    # 로거는 앱 조립 시 한 번만 초기화하면 되므로 진입점에서 명시적으로 호출합니다.
    # 이렇게 두면 Tool/Client 어디서 로그를 남겨도 동일한 설정을 공유합니다.
    init_logger()

    mcp = FastMCP(
        "MS365 FastMCP Server",
        instructions="MS365 Outlook mail/teams tools",
    )

    # register_calendar_tools(mcp)
    register_mail_tools(mcp)
    # register_teams_tools(mcp)
    # register_sharepoint_tools(mcp)
    
    
    # FastMCP middleware 는 등록 순서대로 바깥에서 안쪽으로 감쌉니다.
    # 예외 미들웨어를 먼저 등록해 tool/service/client 예외를 마지막에 MCP 응답으로 변환합니다.
    mcp.add_middleware(MCPExceptionMiddleware())
    mcp.add_middleware(MCPLoggingMiddleware())

    app = mcp.http_app(path="/mcp", transport="streamable-http")
    
    # app.add_middleware(HttpLoggingASGIMiddleware)
    app.add_middleware(HttpMiddleware)

    return app

app = create_app()


