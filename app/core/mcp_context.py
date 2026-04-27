from contextvars import ContextVar
from app.schema.user import User


# 요청을 추적-매핑하기 위한 trace_id.
_trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="-")

# HTTP 헤더로 들어오는 biz-user-token을 컨텍스트에 저장하여 CMN 호출에 사용합니다.
_biz_user_token_ctx: ContextVar[str|None] = ContextVar("biz_user_token", default=None)
_current_user_ctx: ContextVar[User|None] = ContextVar("current_user", default=None)



def set_trace_id(trace_id: str) -> None:
    _trace_id_ctx.set(trace_id)
def get_trace_id() -> str:
    return _trace_id_ctx.get()
def clear_trace_id() -> None:
    _trace_id_ctx.set("-")


def set_biz_user_token(biz_user_token: str) -> None:
    _biz_user_token_ctx.set(biz_user_token)
def get_biz_user_token() -> str | None:
    return _biz_user_token_ctx.get()
def clear_biz_user_token() -> None:
    _biz_user_token_ctx.set(None)


def set_current_user(user: User) -> None:
    _current_user_ctx.set(user)

def get_current_user() -> User | None:
    return _current_user_ctx.get()

def clear_current_user() -> None:
    _current_user_ctx.set(None)
