import uuid

from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware



class HttpMiddleware(BaseHTTPMiddleware):
    """
        http 요청 헤더를 읽고 사용자 JWT_TOKEN 파싱
        request.state에 값을 저장한다 -> 나중에 tool call 및 login에서 사용
    """

    async def dispatch(self, request: Request, call_next):
        # health check 는 \PASS
        if request.url.path == "/api/health":
            return await call_next(request)


        # request.state에 컨텍스트에 필요한 값 저장        
        trace_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.trace_id = trace_id

        user_token = request.headers.get("mcp_user_token") 
        if user_token:
            request.state.user_token = user_token
        else: 
            request.state.user_token = None
            # logger.warning(f"no mcp_user_token in trace_id={trace_id}")    

        request.state.current_user = None
        
        # request 다음으로 전달
        response = await call_next(request)

        response.headers["x-request-id"] = trace_id

        return response

           