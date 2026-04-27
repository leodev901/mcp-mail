import json
import time
import asyncio 
from typing import Any

from fastmcp.server.middleware.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_request
from loguru import logger
from mcp.types import CallToolRequestParams

from app.clients.mcp_cmn_client import fetch_user_context_from_mcp_cmn, save_mcp_tool_log
from app.common.exception import CmnAuthError, GraphClientError
from app.schema.log import ToolLogRequest




def logging_message(
    record = ToolLogRequest
) -> None:
    """ MCP tool 호출 로그를 공통 포맷으로 남깁니다.
    """
    message = f"[mcp_tool_call] >> "
    message += f" trace_id={record.trace_id}"
    message += f" tool_name={record.tool_name}"
    message += f" http_method={record.http_method}"
    if record.http_status:
        message += f" http_status={record.http_status}"
    if record.status:
        message += f" status={record.status}"
    if record.message:
        message += f" message={record.message}"
    if record.request_body:
        req_body_json = json.dumps(record.request_body, indent=2, ensure_ascii=False )
        message += f" request_body={req_body_json}"
    if record.response_body:
        res_body_json = json.dumps(record.response_body, indent=2, ensure_ascii=False )
        message += f" response_body={res_body_json}"
    logger.info(message)
    

class MCPExceptionMiddleware(Middleware):
    """
    모든 tool 호출 예외를 한곳에서 MCP 응답으로 바꾸는 전역 예외 미들웨어입니다.
    FastMCP 에는 FastAPI 의 add_exception_handler 같은 tool 전용 API 가 없으므로, middleware 가 가장 가까운 전역 처리 지점입니다.
    """

    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: CallNext[CallToolRequestParams, Any],
    ) -> Any:
        try:
            return await call_next(context)
        except GraphClientError as exc:
            # FastMCP ToolError 는 code/message/detail 키워드 인자를 받지 않습니다.
            # 따라서 구조화 정보는 문자열에 명시적으로 담아 MCP tool error 로 올립니다.
            raise ToolError(f"[{exc.code}] {exc.message} detail={exc.error}") from exc
            
        except CmnAuthError as exc:
            raise ToolError(f"[{exc.code}] {exc.message} detail={exc.detail}") from exc
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError(f"[UNEXPECTED_TOOL_ERROR] {type(exc).__name__}: {exc}") from exc

class MCPLoggingMiddleware(Middleware):
    """
    tool 호출 전에는 CMN 에서 사용자 컨텍스트를 준비하고, 호출 후에는 성공/실패 로그를 남깁니다.
    요청별 데이터는 app.state 가 아니라 request.state 에 저장해야 동시 사용자 요청이 서로 섞이지 않습니다.
    """

    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: CallNext[CallToolRequestParams, Any],
    ) -> Any:
        params = context.message
        tool_name = params.name
        arguments = params.arguments or {}

        request = get_http_request()
        biz_user_token = getattr(request.state, "biz_user_token", None)
        trace_id = getattr(request.state, "trace_id", "-")
        current_user = None

        started = time.perf_counter()

        record = ToolLogRequest(
            trace_id=trace_id,
            tool_name=tool_name,
            http_method=request.method,
            request_body=arguments,          
        )

        try:
            # CMN 사전 조회는 tool 실행 전에 한 번만 수행합니다.
            # request.state 에 저장하면 service/graph 계층이 같은 요청 컨텍스트를 재사용할 수 있습니다.
            if biz_user_token and current_user is None:
                resp = await fetch_user_context_from_mcp_cmn(biz_user_token=biz_user_token, app_name="MAIL")
                # resp 는 이미 app.schema.credentials.MyAccessToken 으로 검증된 모델입니다.
                # service 계층은 graph_access_token/current_user/yellow_list 를 request.state 에서 읽습니다.
                request.state.graph_access_token = resp.access_token
                request.state.current_user = resp.user_info
                request.state.yellow_list = resp.yellow_list
                request.state.blacklist = resp.yellow_list
            
            # MCP tool 실행
            result = await call_next(context)

            record.status = "success"
            # FastMCP ToolResult 는 HTTP Response 가 아니므로 status_code 가 없습니다.
            # tool 호출 성공 로그에서는 내부 표준값으로 200 을 기록합니다.
            record.http_status = 200
            record.response_body = getattr(result, "structured_content", None) or {}
            
            
            return result
        except Exception as exc:
            
            record.status = "error"
            record.message = str(exc)

            raise
        finally:
            
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            logging_message( record ) 
            # 로그 저장은 tool 호출 스레드에 영향이 없도록 비동기 작업으로 생성
            asyncio.create_task(save_mcp_tool_log(record))
            
            
