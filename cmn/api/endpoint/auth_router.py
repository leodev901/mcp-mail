from typing import Annotated
import httpx

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from starlette.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field

from cmn.utils import jwt_manager 
from cmn.db.crud.m365_oauth_crud import get_graph_infos, save_user_token, get_user_app_token
from cmn.db.models.m365_user_toekn import M365UserToken
from cmn.schemas.response import CommonResponse
from cmn.schemas.user import User
from cmn.schemas.callback import OAuthCallbackParams

from cmn.services.auth_service import AuthService
from cmn.services.delegated_auth_service import DelegatedAuthService





auth_router = APIRouter(prefix="/api/oauth",tags=["m365_oauth"])


class AuthRequest(BaseModel):
    company_cd: str = Field(...,description="회사 코드",example="leodev901")
    app_name: str = Field(...,description="앱 이름",example="TODO")



# Micorosoft 앱 권한 가져오기
@auth_router.get("/", response_model=CommonResponse)
async def auth(
    app_name: str = Query(..., description="MS 접근 권한을 받을 앱 이름", example="TODO"),
    current_user: User = Depends(jwt_manager.get_current_user),
    auth_service: AuthService = Depends(AuthService),
):
    print(current_user)
    data = await auth_service.get_oauth_token(current_user.company_code, app_name)
    return CommonResponse.ok(data)


# Micorosoft 위임으로 저장된 사용자 권한 토큰 가져오기 
@auth_router.get("/user/token/{app_name}", response_model=CommonResponse)
async def auth_user_token(
    app_name: str = Path(..., description="MS 접근 권한을 받을 앱 이름", example="MAIL"),
    current_user: User = Depends(jwt_manager.get_current_user),
    delegated_auth_service: DelegatedAuthService = Depends(DelegatedAuthService),
):
    """Micorosoft 사용자 위임 권한을 조회 또는 갱신하여 반환합니다."""
    data = await delegated_auth_service.fetch_auth_user_token(current_user, app_name)
    return CommonResponse.ok(data)
    




@auth_router.get("/m365/callback/{app_name}")
async def callback_m365_oauth_delegate(
    callback_params: Annotated[OAuthCallbackParams,Query()], # MS에서 보내주는 Query 스트링을 -> OAuthCallbackParams 모델에 담습니다.
    app_name:str = Path(...,description="앱 이름"),
    delegated_auth_service: DelegatedAuthService = Depends(DelegatedAuthService),
):
    """
    사용자 위임(Delegated) 권한 승인 시 
    Microsoft로부터 리다이렉트로 호출되는 콜백 엔드포인트입니다.
    파라미터롲 전달받는 state를 검증하고 실제 access_token / refresh_token을 저장합니다.
    """

    resp =  await delegated_auth_service.handle_callback(callback_params, app_name)
    return resp




# @auth_router.get("/m365/start")
# async def start_m365_oauth(request: Request):
#     """
#     브라우저에서 호출되는 OAuth 시작점입니다.
#     지금 단계에서는 학습을 위해 user_id, company_cd를 쿼리로 받습니다.
#     """
#     user_id = request.query_params.get("user_id")
#     company_cd = request.query_params.get("company_cd")

#     logger.info(f"사용자 동의 요청을 받았습니다. user_id={user_id} company_cd={company_cd}")


#     if not user_id or not company_cd:
#         return HTMLResponse(
#             "Missing required query params: user_id, company_cd",
#             status_code=400,
#         )

#     # 회사 코드별 OAuth 설정을 읽습니다.
#     config = settings.get_m365_config(company_cd)

#     # state는 로그인 시작 요청과 콜백 응답을 연결하는 1회용 랜덤 문자열입니다.
#     state = secrets.token_urlsafe(32)
#     token_manager.save_oauth_state(
#         state=state,
#         user_id=user_id,
#         company_cd=company_cd,
#     )

#     params = {
#         "client_id": config["client_id"], # 앱에 따른 cliente_id  
#         "response_type": "code",
#         "redirect_uri": config["redirect_uri"], #  prd,stg,dev 각각 환경에 따른 url X 앱 개수 분기 (앱별로 토큰 다릅니다)
#         "response_mode": "query",
#         "scope": config["scopes"], # 앱에 등록된 권한
#         "state": state, # 사용자 식별 문자열 ex.) skt.P016392
#     }

#     authorize_url = (
#         f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/authorize"
#         f"?{urlencode(params)}"
#     )

#     return RedirectResponse(authorize_url)






