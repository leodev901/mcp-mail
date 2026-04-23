
import json
import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from cmn.base.logger import logger

# 로깅 제외 경로
EXCLUDE_PATHS = {
    "/health",
    "/healthz",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/openapi.yaml",
}

# 민감 정보는 로그에 그대로 남기지 않기 위해 별도 상수로 관리합니다.
SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "proxy-authorization",
}

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # OPTIONS 메소드는 보통 CORS preflight 용도라서 skiip
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # health check, docs 등은 트래픽이 많고 신호 대비 잡음이 커서 skip
        if request.url.path in EXCLUDE_PATHS:
            return await call_next(request)
        
        started = time.perf_counter()


        # 추적을 위한 trace_id
        trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
        request.state.trace_id = trace_id

        # ========= ========= ========= ========= 
        # Request 요청 로깅
        # ========= ========= ========= ========= 

        logger.info(f"Request-[{trace_id}] {request.method} {request.url.path} {request.client.host if request.client else 'unknown'}")
        logger.info(f"Headers-[{trace_id}] {json.dumps(dict(_mask_sensitive_headers(request.headers)), indent=2, ensure_ascii=False)}")

        
        try:
            # awiat 비동 작업중 응답을 받지 못할 경우를 고려하여 응답 객체를 None으로 먼저 초기화합니다.
            response = None
            response = await call_next(request)
            response.headers["x-trace-id"] = trace_id
            return response
        
        except Exception:
            # exception.py 에서 예외를 핸들링 하기 때문에 그대로 넘깁니다.
            raise
        finally:
            # ========= ========= ========= ========= 
            # Response 응답 로깅
            # ========= ========= ========= ========= 
            duration = (time.perf_counter() - started) * 1000
            status_code = response.status_code if response else "error"

            logger.info(f"Response-[{trace_id}] {request.method} {request.url.path} {status_code} {duration:.2f}ms")

        

    
def _mask_sensitive_headers(headers: dict) -> dict:
    # 민감정보를 포함한 헤더는 마스킹 합니다. 
    masked_header: dict[str,any] = {}

    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            masked_header[key] = "***MASKED***"
        else:
            masked_header[key] = value
    
    return masked_header