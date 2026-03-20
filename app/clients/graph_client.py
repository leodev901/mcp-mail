import httpx
import time 
import json
from loguru import logger 

from fastmcp.server.dependencies import get_http_request 

from app.core.config import settings
from app.models.user_info import UserInfo
from app.core.token_manager import token_manager
from app.core.token_manager import AuthRequiredError





GRAPH_BASE = "https://graph.microsoft.com/v1.0"

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

async def graph_request(
    method: str,
    path: str,
    json_body: dict | None = None,
    custom_headers: dict | None = None,
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


    # 1순위: current_user
    # 2순위: 기본값
    if current_user:
        user_email = current_user.email
        company_cd = current_user.company_cd
        user_id = current_user.user_id
    else:
        # raise ValueError("현재 사용자 정보를 찾을 수 없습니다.")
        user_email = "admin@leodev901.onmicrosoft.com" #DEFAULT_USER_EMAIL
        company_cd = "leodev901" #DEFAULT_COMPANY_CD
        user_id = "20075487" #DEFAULT_COMPANY_CD
    
    if _is_black_list(user_email):
        raise GraphAccessDeniedError(user_email)
    try :
        access_token = await token_manager.get_valid_access_token(user_id, company_cd)
    except AuthRequiredError as e:
        logger.error(f" {type(e).__name__}:{str(e)}")
        raise e
    except Exception as e:
        raise e

    url = f"{GRAPH_BASE}/me{path}"
    headers = {
        "Authorization": f"Bearer {access_token}", 
        "Accept": "application/json"
    }

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


    
