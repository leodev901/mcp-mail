from app.clients.mcp_cmn_client import fetch_recent_api_log_count
from app.common.logger import logger
from fastmcp.exceptions import ToolError



class MailGuardService():
    def __init__(self):
        pass

    async def ensure_api_call_allowed(self,*,user_email:str):
        # 호출 횟수를 확인합니다.
        log_count = await fetch_recent_api_log_count(
            provider_email=user_email,
            interval_minutes=10,
        )

        # 제한을 넘으면 FastMCP Tool 에러로 중단합니다.
        if log_count >= 9999:
            raise ToolError("최근 10분 API 호출 제한을 초과했습니다.")
        



