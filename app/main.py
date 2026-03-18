from fastmcp import FastMCP

from app.core.http_middleware import HttpMiddleware
from app.core.http_asgi_middleware import HttpLoggingASGIMiddleware
from app.core.mcp_midleware import MCPLoggingMiddleware
from app.tools.calendar_tools import register_calendar_tools
from app.tools.mail_tools import register_mail_tools
from app.tools.teams_tools import register_teams_tools
from app.tools.sharepoint_tools import register_sharepoint_tools
from app.common.logger import init_logger

init_logger()

def create_app():
    mcp = FastMCP(
        "MS365 FastMCP Server",
        instructions="MS365 Outlook mail/calendar/todo/teams tools",
    )

    register_calendar_tools(mcp)
    register_mail_tools(mcp)
    register_teams_tools(mcp)
    register_sharepoint_tools(mcp)
    mcp.add_middleware(MCPLoggingMiddleware())

    app = mcp.http_app(path="/mcp", transport="streamable-http")
    
    app.add_middleware(HttpLoggingASGIMiddleware)
    app.add_middleware(HttpMiddleware)

    return app

app = create_app()



# if __name__ == "__main__":
#     import uvicorn

#     uvicorn.run(app, host="0.0.0.0", port=8002, lifespan="on")
