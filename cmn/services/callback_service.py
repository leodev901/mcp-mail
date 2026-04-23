from datetime import datetime, timedelta, timezone
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import HTMLResponse


from cmn.core.dependencies import get_db_session_for_oauth_state
from cmn.db.models.m365_user_toekn import M365UserToken
from cmn.repositories.auth_repository import AuthRepository
from cmn.base.logger import logger
from cmn.schemas.oauth_callback import OAuthCallbackParams
from cmn.base.http_client import get_httpx_client



KST = timezone(timedelta(hours=9))
VALID_APP_NAMES = { "TODO","MAIL" }


#TO-DO: get_db_session_for_oauth_state 여기에서 state가 없을 경우
# e.g 요청 할 때 안을 경우나 파싱이 잘못 됬을 경우
#   -> FastAPI dependency 실행
#   -> get_db_session_for_oauth_state(state=Query(...))
#   -> state 없음
#   -> 서비스 진입 전 422 또는 400 발생 할 수 있기 때문에... 
#
# 추천 되는 권장사항: get_db 세션만 가져오고, 
# error 와 state 파싱 검증이 끝났을 때 db seesion을 연결 해라 
class CallbackService():
    def __init__(self,
        session: AsyncSession = Depends(get_db_session_for_oauth_state),
    ):
        self.session=session
        self.auth_repo=AuthRepository(session)
        

    async def handle_callback(self, callback_params: OAuthCallbackParams, app_name:str):
        app_name = app_name.strip().upper()
        logger.debug(f"동의 callback 수신 - state:{callback_params.state} app_name:{app_name}")

        # 응답 오류 검증
        error = getattr(callback_params, "error", None)
        if error:
            error_description = getattr(callback_params, "error_description", None)
            logger.warning(f"OAuth callback error: {error}-{error_description}")
           
            return HTMLResponse(
                f"error: {error} -"
                f"description: {error_description}",
                status_code=400,
            )
        
        # APP_NAME=콜백 호출 경로 오류 검증
        if app_name not in VALID_APP_NAMES:
            return HTMLResponse(
                f"Invalid app_name - {app_name}",
                status_code=400,
            )
            
        # state 검증
        state = getattr(callback_params, "state", None)
        if not state or "." not in state:
            return HTMLResponse(
                f"Invalid state parameter - {state}",
                status_code=500,
            )
        parts = state.split(".", 1)
        if len(parts) != 2:
            return HTMLResponse(
                f"Invalid state parameter format  {state}",
                status_code=500,
            )
        
        company_code = parts[0]
        user_id = parts[1]

        
        # 위임 코드 검증
        code = getattr(callback_params, "code", None)
        if not code:
            return HTMLResponse(
                "Missing required query params: code, state",
                status_code=500,
            )


        # DB에서 회사 config 정보 조회해야 함
        graph_infos = await self.auth_repo.get_graph_infos(app_name=app_name)
        # 조회 결과를 dict으로 변환
        config = {row.key: row.value for row in graph_infos}
    
        required_keys = ("tenant_id", "client_id", "client_secret")
        missing_keys = [key for key in required_keys if not config.get(key)]
        if missing_keys:
            raise HTMLResponse(
                f"missing graph config keys: {', '.join(missing_keys)}",
                status_code=500
            )
        

        # 위임 코드를 사용하여  access_token, redirect_token 받아오기

        token_url = (
            f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/token"
        )

        payload = {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config["redirect_uri"],
            "scope": config["scopes"],
        }

        client = await get_httpx_client()
        response = await client.post(token_url, data=payload)

        if response.status_code != 200:
            return HTMLResponse(
                f"Token exchange failed: {response.text}",
                status_code=400,
            )

        token_data = response.json()
        logger.debug(f"token_data: {token_data}")
        
        
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = int(token_data.get("expires_in", 1800))
        expires_at = datetime.now(KST) + timedelta(seconds=expires_in)
        
        if not access_token or not refresh_token:
            return HTMLResponse(
                "Missing access_token or refresh_token in token response",
                status_code=400,
            )
        logger.debug(f"oauth_callback_expires_at: {expires_at.isoformat()}")

        # DB에 사용자 토큰 저장
        user_token = M365UserToken(
            app_name=app_name,
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,  
        )
        reuslt = await self.auth_repo.save_user_token(user_token)

            
        return HTMLResponse(
            f"""
            <html>
            <body>
                <h3>Microsoft 365 위임권한 동의 연결 완료</h3>
                <p>이제 본인 기준 메일/팀즈 도구를 사용할 수 있습니다.</p>
                <p>company_code: {company_code}</p>
                <p>user_id: {user_id}</p>
            </body>
            </html>
            """,
            status_code=200,
        )


