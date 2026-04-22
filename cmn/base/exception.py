from fastapi import Request, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from http import HTTPStatus
from pydantic import ValidationError


from cmn.base.logger import logger


def register_exception_handler(app: FastAPI):
    """FastAPI exception handler 등록
    """
    logger.info("Registering exception handlers...")
    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handeler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_error_handler)
    # app.add_exception_handler(APIError, supabse_exception_handler)

    
# global exception handler  - 최상위 Exception을 잡기 위한 핸들러
async def global_exception_handler(request: Request, exc: Exception):
    """global exception handler  - 최상위 Exception을 잡기 위한 핸들러
    """
    # 최상위 핸들러는 보통 logger.exception(...)으로 남겨서 traceback까지 확보합니다.
    trace_id = getattr(request.state, "trace_id", "unknown")
    logger.exception(f"[{trace_id}] {type(exc).__name__} - {exc}")
    # 예외를 raise 하는 대신에 front에 에러가 발생 하였음을 알립니다.
    # raise HTTPException(status_code=500, detail="Internal server error")
    return JSONResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error_code": 500,
            "message": "요청 처리 중 오류가 발생했습니다.",
            "trace_id": trace_id,
        }
    )

# HTTPException을 던지면 이 핸들러가 잡아서 JSONResponse로 변환해서 리턴
async def http_exception_handeler(request: Request, exc: HTTPException):
    """HTTPException을 던지면 이 핸들러가 잡아서 JSONResponse로 변환해서 리턴
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    detail = exc.detail
    message = detail if isinstance(detail, str) else "요청 처리에 실패했습니다."
    logger.error(f"[{trace_id}] {type(exc).__name__} -{exc.status_code}- {exc}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": exc.status_code,
            "message": message,
            "trace_id": trace_id,
            "detail": detail
        }
    )

# RequestValidationError
async def request_validation_error_handler(request: Request, exc: RequestValidationError):
    trace_id = getattr(request.state, "trace_id", "unknown")
    logger.error(f"[{trace_id}] {type(exc).__name__} - {exc}")
    return JSONResponse(
        status_code=HTTPStatus.BAD_REQUEST,
        content={
            "success": False,
            "error_code": HTTPStatus.BAD_REQUEST,
            "message": "요청의 입력값 또는 형식이 잘못되었습니다.",
            "trace_id": trace_id,
            "detail": exc.errors()
        }
    )

# ValidationError
async def pydantic_validation_error_handler(request: Request, exc: ValidationError):
    trace_id = getattr(request.state, "trace_id", "unknown")
    logger.error(f"[{getattr(request.state,'trace_id','unknown')}] {type(exc).__name__} - {exc}")
    return JSONResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error_code": HTTPStatus.INTERNAL_SERVER_ERROR,
            "message": "입력값 또는 형식의 변환이 실패 하였습니다.",
            "trace_id": trace_id,
            "detail": exc.errors()
        }
    )