import secrets
from urllib.parse import urlencode

import httpx
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from loguru import logger

from app.core.config import settings
from app.core.token_manager import token_manager



def register_m365_oauth_routes(mcp: FastMCP) -> None:
    """
    OAuth 시작/콜백 라우트를 FastMCP에 등록합니다.
    """

    @mcp.custom_route("/auth/m365/start", methods=["GET"], include_in_schema=False)
    async def start_m365_oauth(request: Request):
        """
        브라우저에서 호출되는 OAuth 시작점입니다.
        지금 단계에서는 학습을 위해 user_id, company_cd를 쿼리로 받습니다.
        """
        user_id = request.query_params.get("user_id")
        company_cd = request.query_params.get("company_cd")

        logger.info(f"사용자 동의 요청을 받았습니다. user_id={user_id} company_cd={company_cd}")


        if not user_id or not company_cd:
            return HTMLResponse(
                "Missing required query params: user_id, company_cd",
                status_code=400,
            )

        # 회사 코드별 OAuth 설정을 읽습니다.
        config = settings.get_m365_config(company_cd)
        scopes = settings.get_m365_scopes(company_cd)

        # state는 로그인 시작 요청과 콜백 응답을 연결하는 1회용 랜덤 문자열입니다.
        state = secrets.token_urlsafe(32)
        token_manager.save_oauth_state(
            state=state,
            user_id=user_id,
            company_cd=company_cd,
        )

        params = {
            "client_id": config["client_id"], # 앱에 따른 cliente_id  
            "response_type": "code",
            "redirect_uri": config["redirect_uri"], #  prd,stg,dev 각각 환경에 따른 url X 앱 개수 분기 (앱별로 토큰 다릅니다)
            "response_mode": "query",
            "scope": " ".join(scopes), # 앱에 등록된 권한
            "state": state, # 사용자 식별 문자열 ex.) skt.P016392
        }

        authorize_url = (
            f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/authorize"
            f"?{urlencode(params)}"
        )

        return RedirectResponse(authorize_url)

    @mcp.custom_route("/auth/m365/callback", methods=["GET"], include_in_schema=False)
    async def callback_m365_oauth(request: Request):
        """
        Microsoft 로그인 완료 후 돌아오는 콜백 엔드포인트입니다.
        code와 state를 검증하고 실제 access_token / refresh_token을 저장합니다.
        """
        error = request.query_params.get("error")
        error_description = request.query_params.get("error_description")
        code = request.query_params.get("code")
        state = request.query_params.get("state")

        logger.info("동의를 callback 받았습니다.")

        if error:
            return HTMLResponse(
                f"Microsoft login failed: {error} / {error_description}",
                status_code=400,
            )

        if not code or not state:
            return HTMLResponse(
                "Missing required query params: code, state",
                status_code=400,
            )

        # state는 1회성이라 꺼내면서 삭제합니다.
        state_record = token_manager.pop_oauth_state(state)
        if state_record is None:
            return HTMLResponse(
                "Invalid or expired state",
                status_code=400,
            )
        
        logger.info(f"동의한 사용자 '{state_record.company_cd}:{state_record.user_id}'" )

        config = settings.get_m365_config(state_record.company_cd)
        scopes = settings.get_m365_scopes(state_record.company_cd)

        token_url = (
            f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/token"
        )

        payload = {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config["redirect_uri"],
            "scope": " ".join(scopes),
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(token_url, data=payload)

        if response.status_code != 200:
            return HTMLResponse(
                f"Token exchange failed: {response.text}",
                status_code=400,
            )

        token_data = response.json()
        
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = int(token_data.get("expires_in", 3600))

        if not access_token or not refresh_token:
            return HTMLResponse(
                "Missing access_token or refresh_token in token response",
                status_code=400,
            )

        token_manager.save_tokens(
            user_id=state_record.user_id,
            company_cd=state_record.company_cd,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )

        return HTMLResponse(
            """
            <html>
              <body>
                <h3>Microsoft 365 위임권한 동의 연결 완료</h3>
                <p>이제 본인 기준 메일/팀즈 도구를 사용할 수 있습니다.</p>
              </body>
            </html>
            """,
            status_code=200,
        )
    


    @mcp.custom_route("/auth/m365/delegate/callback", methods=["GET"], include_in_schema=False)
    async def callback_m365_oauth_delegate(request: Request):
        """
        Microsoft 로그인 완료 후 돌아오는 콜백 엔드포인트입니다.
        code와 state를 검증하고 실제 access_token / refresh_token을 저장합니다.
        """
        error = request.query_params.get("error")
        error_description = request.query_params.get("error_description")
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        logger.info("동의를 callback 받았습니다.")

        headers = request.headers
        print(headers)
        


        values = state.split(".")
        company_cd = values[0]
        user_id = values[1]
        

        return HTMLResponse(
                f"""
                <html>
                <body>
                    <h3>Microsoft 365 위임권한 동의 연결 완료</h3>
                    <p>이제 본인 기준 메일/팀즈 도구를 사용할 수 있습니다.</p>
                    <p>company_cd: {company_cd}</p>
                    <p>user_id: {user_id}
                </body>
                </html>
                """,
                status_code=200,
            )
