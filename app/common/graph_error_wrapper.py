# app/common/graph_error_wrapper.py

import functools
from loguru import logger
from app.clients.graph_client import GraphClientError

def graph_error_wrapper(as_list: bool = False):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
                
            except GraphClientError as e:
                # 예상 가능한 비즈니스 에러는 정상응답으로 LLM에 반환 합니다.
                logger.warning(f"[LLM 반환 에러] {func.__name__} - {e.code}:{e.message}")
                rtn_dict = {"status":"error", "code": e.code, "message": e.message, "error": e.error}
                return [rtn_dict] if as_list else rtn_dict
                
            except Exception as e:
                logger.error(f"[예기치 못한 에러 발생] {func.__name__} - {type(e).__name__}:{str(e)}")
                raise e

        return wrapper
    return decorator        
