import httpx
import time 
import json
from loguru import logger 


from fastmcp.server.dependencies import get_http_request 

from app.core.config import settings
from app.models.user_info import UserInfo

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TOKEN_URL_TPL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

DEFAULT_USER_EMAIL = ""

BLACKLIST = [
    "admin@skcc.com",
]


class GraphClientError(Exception):
    """Graph API 호출을 LLM이 처리할 수 있도록 정의한 에러의 기본 클래스"""
    def __init__(self, code:str, message:str, error:str=""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.error = error

class GraphCompanyConfigNotFoundError(GraphClientError):
    def __init__(self, company_cd:str):
        super().__init__("GRAPH_COMPANY_CONFIG_NOT_FOUND", f"해당 company_cd의 MS365 config가 없습니다. 관리자에게 문의하세요 company_cd:{company_cd}")

class GraphAccessDeniedError(GraphClientError):
    """MS Graph API 접근 불가한 사용자 대상"""
    def __init__(self, email:str):
        super().__init__("GRAPH_ACCESS_DENIED", f"해당 사용자는 접근이 허용되지 않습니다. email:{email}")

#400
class GraphBadRequestError(GraphClientError):
    """MS Graph API 잘못된 요청 파라미터"""
    def __init__(self, error_msg:str):
        super().__init__("GRAPH_BAD_REQUEST", f"잘못된 요청 파라미터/문법입니다.", error_msg)

#401
class GraphUnauthorizedError(GraphClientError):
    """MS Graph API 인증 실패"""
    def __init__(self, error_msg:str):
        super().__init__("GRAPH_UNAUTHORIZED", f"인증 실패입니다.", error_msg)

#403
class GraphForbiddenError(GraphClientError):
    """MS Graph API 접근 권한 없음"""
    def __init__(self, error_msg:str):
        super().__init__("GRAPH_FORBIDDEN", f"접근 권한이 없습니다.", error_msg)

#404
class GraphResourceNotFoundError(GraphClientError):
    """MS Graph API 리소스 없음 대상"""
    def __init__(self, error_msg:str):
        super().__init__("GRAPH_RESOURCE_NOT_FOUND", f"해당 리소스를 찾을 수 없습니다. 사용자 이메일 또는 이벤트 ID를 확인해주세요.", error_msg)




def _is_black_list(email: str) -> bool:
    return email in BLACKLIST


def logging_message(
        status_code:int,
        method:str,
        trace_id:str,
        elapsed_ms:float | None= None,
        current_user:UserInfo | None= None,  
        req_json: dict | None= None, 
        resp_json: dict | None= None,
        error_message: str | None = None,
)->None:
    message=f"[GraphAPI Request] >>> trace_id={trace_id}"
    message+=f" status_code={status_code}"
    message+=f" method={method}"
    latency_str = f"{elapsed_ms:.1f}" if elapsed_ms is not None else "0.0"
    message+=f" elapsed_ms={latency_str}"
    message+=f" email={current_user.email if current_user else '-'}"
    message+=f" company_cd={current_user.company_cd if current_user else '-'}"
    message+=f"\n request={req_json if req_json else '-'}"
    if resp_json is not None :
        message+=f"\n response={resp_json if resp_json else '-'}"
    if error_message is not None :
        message+=f"\n error={error_message}"        
    
    if(status_code==200):
        logger.info(message)
    else:
        logger.error(message)

async def get_access_token(company_cd: str = "leodev901") -> str:
    """Return (access_token, default_user_email)."""

    ms365_config = settings.get_m365_config(company_cd)
    tenant_id = ms365_config["tenant_id"]
    client_id = ms365_config["client_id"]
    client_secret = ms365_config["client_secret"]
    DEFAULT_USER_EMAIL = ms365_config.get("default_user_email","admin@leodev901.onmicrosoft.com")

    if not client_id or not client_secret or not tenant_id:
        # raise ValueError(f"MS365 config is incomplete for company_cd='{company_cd}'")
        raise GraphCompanyConfigNotFoundError(company_cd)

    token_url = TOKEN_URL_TPL.format(tenant_id=tenant_id)
    data = {
        "client_id": client_id,
        "scope": "https://graph.microsoft.com/.default",
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }
    
    try:
        print(f"get access token for '{company_cd}'")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(token_url, data=data)
            resp.raise_for_status()
            return resp.json()["access_token"]
    except Exception as e:
        raise e


async def graph_request(
    method: str,
    path: str,
    user_email: str | None = None,
    json_body: dict | None = None,
    company_cd: str = "leodev901",
    custom_headers: dict | None = None,
    is_replace_path: bool = False,
) -> dict:
    """Common wrapper for Microsoft Graph user-scoped APIs."""

    # 로깅을 위한 컨텍스트 확보
    current_user = None
    try:
        req = get_http_request()
        trace_id = getattr(req.state, "trace_id", "internal")
        current_user = getattr(req.state, "current_user", None)
    except Exception as e:
        logger.error(f"HTTP 요청 정보를 가져오는 중 오류 발생: {str(e)}")
        trace_id = "unknown"
    

    token = await get_access_token(company_cd)
    # email = user_email or DEFAULT_USER_EMAIL

    if not user_email:
        raise ValueError("user_email is required or default_user_email must be configured")

    if _is_black_list(user_email):
        raise GraphAccessDeniedError(user_email)

    url = f"{GRAPH_BASE}/users/{user_email}{path}"
    if is_replace_path:
        url = f"{GRAPH_BASE}{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if custom_headers:
        headers.update(custom_headers)

    start_time = time.perf_counter() # 타이머 시작
    req_body = {
        "method": method,
        "url": url,
        "body": json_body,
    } or None
    req_json = json.dumps(req_body, ensure_ascii=False, indent=2)
    # logger.info(f"[GraphAPI Request] Trace={trace_id} | User={current_user.user_id} \n Request={req_json}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(method.upper(), url, headers=headers, json=json_body)
            resp.raise_for_status()
            status_code = resp.status_code
            if status_code == 204:
                resp_json = None
                return {"status_code": status_code,"status":"success"}
            error_detail = None
            resp_json = json.dumps(resp.json(), ensure_ascii=False, indent=2)
            return resp.json()
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        resp_json = None
        error_detail = f"{type(e).__name__}: {e}"

        if status_code == 400:
            raise GraphBadRequestError(error_detail)
        elif status_code == 401:
            raise GraphUnauthorizedError(error_detail)
        elif status_code == 403:
            raise GraphForbiddenError(error_detail)
        elif status_code == 404:
            raise GraphResourceNotFoundError(error_detail)
        raise e

    except Exception as e:
        status_code = 500
        resp_json = None
        error_detail = f"{type(e).__name__}: {e}"
        raise e
    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logging_message(
            status_code=status_code,
            trace_id=trace_id,
            elapsed_ms=elapsed_ms,
            current_user=current_user,
            method=method,
            req_json=req_json,
            resp_json=resp_json,
            error_message=error_detail,
        )


    
