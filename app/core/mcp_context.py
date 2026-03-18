from contextvars import ContextVar
from app.models.user_info import UserInfo


# 요청을 추적-매핑하기 위한 trace_id.
_trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="-")

# HTTP 헤더로 들어오는 사용자 식별 토큰을 mcp_user_token 컨텍스트에 저장하여 tool에서 참조
_user_token_ctx: ContextVar[str|None] = ContextVar("user_token", default=None)
_current_user_ctx: ContextVar[UserInfo|None] = ContextVar("current_user", default=None)



def set_trace_id(trace_id: str) -> None:
    _trace_id_ctx.set(trace_id)
def get_trace_id() -> str:
    return _trace_id_ctx.get()
def clear_trace_id() -> None:
    _trace_id_ctx.set("-")


def set_user_token(user_token: str) -> None:
    _user_token_ctx.set(user_token)
def get_user_token() -> str | None:
    return _user_token_ctx.get()
def clear_user_token() -> None:
    _user_token_ctx.set(None)


def set_current_user(user_info: UserInfo) -> None:
    _current_user_ctx.set(user_info)

def get_current_user() -> UserInfo | None:
    return _current_user_ctx.get()

def clear_current_user() -> None:
    _current_user_ctx.set(None)