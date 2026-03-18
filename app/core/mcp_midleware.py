import time
from typing import Any

from fastmcp.server.middleware.middleware import CallNext, Middleware, MiddlewareContext
from loguru import logger
from mcp.types import CallToolRequestParams
from fastmcp.server.dependencies import get_http_request
from app.security.jwt_auth import get_user_from_token
import json




def logging_message(
        status:str,
        tool_name:str,
        trace_id:str,
        elapsed_ms:float | None= None,
        arguments:dict | None= None,
        current_user:dict | None= None,  
        input: dict | None= None, 
        output: dict | None= None,
        error_message: str | None = None,
)->None:
    message=f"[mcp_tool_call] >>> trace_id={trace_id}"
    message+=f" status={status} tool_name={tool_name}"
    # message+=f" arguments={arguments if arguments else '-'}"
    message+=f" elapsed_ms={elapsed_ms if elapsed_ms else '' :.1f}"
    message+=f" email={current_user.email if current_user else '-'}"
    message+=f" company_cd={current_user.company_cd if current_user else '-'}"
    message+=f"\n input={input if input else '-'}"
    message+=f"\n output={output if output else '-'}"
    
    if(status=="error"):
        message+=f"\n error={error_message}"
        logger.exception(message)
    else:
        logger.info(message)


class MCPLoggingMiddleware(Middleware):
    """
    HTTP 요청에서 저장한 trace_id를 MCP tool 로그에도 붙인다.
    그래서 HTTP 로그 한 줄과 tool 로그 한 줄을 바로 연결해서 볼 수 있다.
    """

    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: CallNext[CallToolRequestParams, Any],
    ) -> Any:
        params = context.message
        tool_name = params.name
        arguments = params.arguments or {}
        data = {
            "name": tool_name,
            "arguments": arguments,
        }
        input_json = json.dumps(data, ensure_ascii=False, indent=2)


        # 사용자 JWT_Token에서 사용자 정보 파싱하여 저장

        request = get_http_request()
        trace_id = getattr(request.state, "trace_id", "-")
        user_token = getattr(request.state, "user_token", None)
        current_user = getattr(request.state, "current_user", None)

        if current_user is None and user_token:
            current_user = await get_user_from_token(user_token)
            if current_user:
                request.state.current_user = current_user
                logger.debug(f"get user_info from token success!!! current_user={current_user}")
        

        started = time.perf_counter()
        try:
            result = await call_next(context)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            
            content_json = json.dumps(
                        result.structured_content,
                        ensure_ascii=False,
                        indent=2,
                        default=str,
                        ) if result.structured_content else None
    
            logging_message(
                status="success",
                tool_name=tool_name,
                trace_id=trace_id,
                elapsed_ms=elapsed_ms,
                arguments=arguments,
                current_user=current_user,
                input=input_json,
                output=content_json,
            )
            return result
        except Exception as e: 
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            logging_message(
                status="error",
                tool_name=tool_name,
                trace_id=trace_id,
                elapsed_ms=elapsed_ms,
                arguments=arguments,
                current_user=current_user,
                input=input_json,
                output=None,
                error_message=f"{type(e).__name__}: {e}",
                        

            )
            raise
