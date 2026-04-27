import uuid

from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware



class HttpMiddleware(BaseHTTPMiddleware):
    """
        HTTP 요청 헤더에서 trace_id와 biz-user-token을 읽어 request.state에 저장합니다.
        app은 사용자 토큰을 직접 해석하지 않고, 이후 MCP middleware에서 CMN API 호출에 사용합니다.
    """

    async def dispatch(self, request: Request, call_next):
        # health check 는 \PASS
        if request.url.path == "/api/health":
            return await call_next(request)


        # request.state에 컨텍스트에 필요한 값 저장
        trace_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.trace_id = trace_id

        biz_user_token = request.headers.get("biz-user-token")
        if biz_user_token:
            request.state.biz_user_token = biz_user_token
        else:
            request.state.biz_user_token = None
            logger.warning(f"no biz-user-token in trace_id={trace_id}")

        request.state.current_user = None

        # request 다음으로 전달
        response = await call_next(request)

        response.headers["x-request-id"] = trace_id

        return response

