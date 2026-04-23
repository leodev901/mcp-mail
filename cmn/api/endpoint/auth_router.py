from typing import Annotated
import httpx

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from starlette.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field

from cmn.utils import jwt_manager 
from cmn.core.database import Database
from cmn.core.dependencies import get_db_session_for_oauth_state, get_db_session_for_compnay
from cmn.db.crud.m365_oauth_crud import get_graph_infos, save_user_token, get_user_app_token
from cmn.db.models.m365_user_toekn import M365UserToken
from cmn.schemas.response import CommonResponse
from cmn.schemas.user import User
from cmn.schemas.oauth_callback import OAuthCallbackParams

from cmn.services.auth_service import AuthService
from cmn.services.callback_service import CallbackService





auth_router = APIRouter(prefix="/api/auth",tags=["m365_oauth"])


class AuthRequest(BaseModel):
    company_cd: str = Field(...,description="회사 코드",example="leodev901")
    app_name: str = Field(...,description="앱 이름",example="TODO")



# MS 접근 권한 가져오기 
@auth_router.get("/", response_model=CommonResponse)
async def auth(
    app_name: str = Query(..., description="MS 접근 권한을 받을 앱 이름", example="TODO"),
    current_user: User = Depends(jwt_manager.get_current_user),
    auth_service: AuthService = Depends(AuthService),
):
    print(current_user)
    data = await auth_service.get_oauth_token(current_user.company_code, app_name)
    return CommonResponse.ok(data)




@auth_router.get("/m365/callback/{app_name}")
async def callback_m365_oauth_delegate(
    callback_params: Annotated[OAuthCallbackParams,Query()], # MS에서 보내주는 Query 스트링을 -> OAuthCallbackParams 모델에 담습니다.
    app_name:str = Path(...,description="앱 이름"),
    callback_service: CallbackService = Depends(CallbackService),
):
    """
    사용자 위임(Delegated) 권한 승인 시 
    Microsoft로부터 리다이렉트로 호출되는 콜백 엔드포인트입니다.
    파라미터롲 전달받는 state를 검증하고 실제 access_token / refresh_token을 저장합니다.
    """

    resp =  await callback_service.handle_callback(callback_params, app_name)
    return resp



# user 위임 권한 가져오기
@auth_router.get("/user/token")
async def user_toekn(
    app_name: str = Query(...,description="앱 이름"),
    user_id: str = Query(...,description="사용자 ID"),
    db: AsyncSession = Depends(get_db_session_for_compnay)
):
    logger.info(f"app_name: {app_name}")
    logger.info(f"user_id: {user_id}")

    app_name = app_name.strip()
    user_id = user_id.strip()

    if not app_name or not user_id:
        raise HTTPException(
            status_code=400,
            detail="Missing required query params: app_name, user_id",
        )

    result = await get_user_app_token(db,app_name,user_id)

    if result is None:
        # [중요] Dabase에 없다는 것은 '동의'를 받지 않은 것으로 사용자로 부터 '동의'를 먼저 벋아야 합니다.
        raise HTTPException(
            status_code=404,
            detail="user token not found",
        )
    
    # 동의하여 받은 토큰이 있으면 갱신(refresh) 하고 전달한다.

    # expiread_at 에서 시간이 충분하면 DB의 값을 그대로 반환
    if result.expires_at and result.expires_at - timedelta(seconds=300) > datetime.now(timezone(timedelta(hours=9))):
        return {
            "access_token": result.access_token
        }
        

    graph_infos = await get_graph_infos(db,"MAIL")
    # 조회 결과를 dict으로 변환
    config = { row.key: row.value for row in graph_infos}


    refresh_token_url = f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/token"

    payload = {
        "client_id":config['client_id'],
        "client_secret":config['client_secret'],
        "grant_type":"refresh_token",
        "refresh_token":result.refresh_token,
        "redirect_uri":config['redirect_uri'],
        "scope":config['scopes'],
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(refresh_token_url, data=payload)
        # resp.raise_for_status()

    if resp.status_code != 200:
        # 토큰 갱신 실패 
        raise HTTPException(
            status_code=502,
            detail="토큰 갱신 발급이 실패 하였습니다.",
        )
        # fail count로 몇 회의상 토큰 발급이 실패하면 database에서 삭제여부 날리고 다시 동의발급 진행 해야 함
        # refresh 토큰이 만료 된 경우도 있을텐데 refersh 토큰의 만료 여부는 알 수 없음
    
    data = resp.json()
    
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token",result.refresh_token)
    expires_in = int(data.get("expires_in", 3600))
    expires_at = datetime.now(timezone(timedelta(hours=9))) + timedelta(seconds=expires_in)
    logger.info(f"user_token_refresh_expires_in: {expires_in}")
    logger.info(
        f"user_token_refresh_now_kst_iso: {datetime.now(timezone(timedelta(hours=9))).isoformat()}"
    )
    logger.info(f"user_token_refresh_expires_at: {expires_at}")
    logger.info(f"user_token_refresh_expires_at_iso: {expires_at.isoformat()}")
    
    if not access_token:
        # TO-DO: refersh
        raise HTTPException(
            status_code=500,
            detail="refresh_access_toeken에서 토큰 갱신 응답 받았으나 acceess_toekn이 비어있음"
        )

    # DB에 사용자 토큰 저장
    user_token = M365UserToken(
        app_name=app_name,
        user_id=user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,  
    )
    reuslt = await save_user_token(db,user_token)

    if not reuslt:
        return HTMLResponse(
            "access token 저장이 실패 했습니다.",
            status_code=500,
        )

    return {
        "access_token": access_token
    }



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






