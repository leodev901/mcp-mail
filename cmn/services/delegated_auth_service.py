from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from starlette.responses import HTMLResponse

from cmn.base.exception import CallbackHTMLResponseException
from cmn.core.database import Database
from cmn.core.dependencies import get_db
from cmn.db.models.m365_user_toekn import M365UserToken
from cmn.repositories.auth_repository import AuthRepository
from cmn.base.logger import logger
from cmn.schemas.callback import OAuthCallbackParams, CallbackState
from cmn.schemas.token import TokenData
from cmn.schemas.credentials import MyAccessToken
from cmn.schemas.user import User
from cmn.base.http_client import get_httpx_client
from cmn.utils import jwt_manager




KST = timezone(timedelta(hours=9))

#TO-DO: get_db_session_for_oauth_state 여기에서 state가 없을 경우
# e.g 요청 할 때 안을 경우나 파싱이 잘못 됬을 경우
#   -> FastAPI dependency 실행
#   -> get_db_session_for_oauth_state(state=Query(...))
#   -> state 없음
#   -> 서비스 진입 전 422 또는 400 발생 할 수 있기 때문에... 
#
# 추천 되는 권장사항: get_db 세션만 가져오고, 
# error 와 state 파싱 검증이 끝났을 때 db seesion을 연결 해라 
class DelegatedAuthService():
    def __init__(self,
        # session: AsyncSession = Depends(get_db_session_for_oauth_state),
        db: Database = Depends(get_db)
    ):
        # self.session=session
        # self.auth_repo=AuthRepository(session)
        self.db=db



        
    

    def _validate_app_name(self, app_name: str) -> str:
        normalized = app_name.strip().upper()
        VALID_APP_NAMES = { "TODO","MAIL" } # 나중외 환경 변수 (env) 로 전환 고려
        if normalized not in VALID_APP_NAMES:
            raise CallbackHTMLResponseException(
                f"Invalid app_name: {app_name}",
                status_code=400
            )
        return normalized
        

    def _validate_callback_error(self, params: OAuthCallbackParams):
        """콜백 결과 error 검사"""
        error = getattr(params, "error", None)
        if error is not None:
            raise CallbackHTMLResponseException(
                f"error: {error} - error_description: {getattr(params, 'error_description', '')}",
                status_code=400
            )
        return None
    
    
    def _resolve_state(self, params: OAuthCallbackParams) -> CallbackState:
        """콜백 결과에서 state를 파싱하여 회사코드와 사번을 추출하여 CallbackState 객체로 반환합니다.
        """
        state = (getattr(params, "state", "") or "").strip()
        if not state or "." not in state:
            raise CallbackHTMLResponseException(
                f"Invalid state params - {state}",
                status_code=400
            )
        
        company_code, user_id = state.split(".", 1)
        company_code = company_code.strip()
        user_id = user_id.strip()

        if not company_code or not user_id:
            raise CallbackHTMLResponseException(
                f"Missing required state params - {state}",
                status_code=400
            )
        return CallbackState(company_code=company_code, user_id=user_id)

    def _resolve_code(self,params: OAuthCallbackParams) -> str:
        """콜백 결과에서 code를 추출하여 유효성 검사
        """
        code = (getattr(params, "code", "") or "").strip()
        if not code:
            raise CallbackHTMLResponseException(
                f"Missing code params",
                status_code=400
            )
        return code
    
    async def _fetch_graph_infos(self, company_code:str, app_name: str) -> dict[str, str]:
        """"데이터베이스에서 Graph Crendetail 정보 가져오기
        """
        async with self.db.session(company_code) as session:
            auth_repo = AuthRepository(session)
            graph_infos = await auth_repo.get_graph_infos(app_name)
            
        
        config = {row.key: row.value for row in graph_infos}

        # 조회 결과 dict으로 변환 후 필요한 key 누락 검증
        required_keys = ("tenant_id", "client_id", "client_secret","redirect_uri","scopes")
        missing_keys = [key for key in required_keys if not config.get(key)]
        if missing_keys:
            raise ValueError( f"missing graph config keys: {', '.join(missing_keys)}")
        
        return config
    
        
    async def _exchange_token(self, app_name: str, state: CallbackState, code: str) -> TokenData:
        """ 위임 코드를 기반으로 Microsoft의 OAuth 를 통해 access_token, refresh_token 가져오기
        """
        # 데이터베이스에서 Graph Crendetail 정보 가져오기 
        config = await self._fetch_graph_infos(state.company_code, app_name)
        
        # 외부 HTTP 호출 
        token_url=f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/token"

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
            raise CallbackHTMLResponseException(
                f"Token exchange failed: {response.text}",
                status_code=502,
            )
        
        token_data = TokenData(**response.json())
        logger.debug(token_data)
        return token_data
    
    async def _save_auth_user_token(self, app_name: str, company_code: str, user_id: str, token_data: TokenData):
        """사용자 토큰 데이터 저장"""
        

        access_token = getattr(token_data, "access_token", None)
        refresh_token = getattr(token_data, "refresh_token", None)
        id_token = getattr(token_data, "id_token", None)
        expires_in = getattr(token_data, "expires_in", 0)
        expires_at = datetime.now(KST) + timedelta(seconds=expires_in)

        # id_token 에서 "name", "preferred_username" 등 활용 가능
        if id_token:
            user_info = jwt_manager.decode_without_key(id_token)
            logger.debug(user_info)
        

        if not access_token :
            raise CallbackHTMLResponseException(
                "Missing access_token in response",
                status_code=400,
            )
        
        logger.debug(f"[access_token] {company_code}.{user_id} token expires_at: {expires_at}")
        
        # DB에 사용자 토큰 저장
        user_token = M365UserToken(
            app_name=app_name,
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,  
        )
        async with self.db.session(company_code) as session:
            try:
                auth_repo = AuthRepository(session)
                reuslt = await auth_repo.save_user_token(user_token)
                await session.commit()
                if not reuslt:
                    raise ValueError("사용자 토큰 저장 실패")
                return True
            except Exception:
                await session.rollback()
                raise
        return False



    async def handle_callback(self, callback_params: OAuthCallbackParams, app_name:str):
        """Microsoft 에서 위임권한을 받은 콜백 메소드 처리
        브라우저에서 Redirect로 전환되는 화면이기 때문에
        모든 예외 처리와 결과는 HTMLResponse로 반환 합니다 -> 화면에 출력.
        """
        
        try: 
            # app_name 호출 경로 검증
            app_name = self._validate_app_name(app_name)
            
            # 콜백 결과에 error 검증
            self._validate_callback_error(callback_params)
            
            
            # state와 위임코드 유효성을 검증하고 해석
            state: CallbackState= self._resolve_state(callback_params)
            code: str = self._resolve_code(callback_params)
            
            # 위임 코드를 사용하여 Microsoft로 부터 사용자의 토큰 데이터 받아오기 -> 외부 HTTP 호출
            token_data = await self._exchange_token(app_name, state, code)

            # 토큰데이터 저장하기
            result = await self._save_auth_user_token(app_name, state.company_code, state.user_id, token_data)

            if result:
                return HTMLResponse(
                    f"""
                    <html>
                    <body>
                        <h3>Microsoft 365 위임권한 동의 연결 완료</h3>
                        <p>이제 본인 기준 메일/팀즈 도구를 사용할 수 있습니다.</p>
                        <p> - 앱 이름: {app_name}</p>
                        <p> - 회사코드: {state.company_code}</p>
                        <p> - 사용자ID: {state.user_id}</p>
                    </body>
                    </html>
                    """,
                    status_code=200,
                )
            else:
                raise ValueError("Microsoft 365 위임권한 동의 연결 실패")
            
            
        except CallbackHTMLResponseException as e:
            logger.error(f"{type(e).__name__} - {str(e)}")
            return HTMLResponse(
                f"<html><body><h3>Error</h3>"
                f"<p>{e.message}</p>"
                f"</body></html>",
                status_code=e.status_code
            )
        
        except Exception as e:
            logger.exception(f"{type(e).__name__} - {str(e)}")
            return HTMLResponse(
                f"<html><body><h3>Microsoft 365 위임권한 동의 연결 실패</h3>"
                f"<p>예기치 못한 오류가 발생하였습다.</p>"
                f"</body></html>",
                status_code=500
            )
    




    async def fetch_auth_user_token(self, current_user: User, app_name: str):
        company_code = current_user.company_code.strip()
        user_id = current_user.user_id.strip()

        # app_name 호출 경로 검증
        app_name = self._validate_app_name(app_name)

        # 사용자 정보로 DB에서 데이터 조회 
        read_data = await self._get_auth_user_token(app_name, company_code, user_id)
        if read_data is None:
            # [중요] Dabase에 없다는 것은 '동의'를 받지 않은 것으로 사용자 동의부터 받아야 함
            raise HTTPException(
                status_code=404,
                detail=f"Microsoft 365 위임권한 동의를 받지 않았습니다. {company_code}.{user_id}",
            )
        
        # 버퍼 시간 5분으로 만료여부 검사
        if datetime.now(KST) + timedelta(seconds=300) < read_data.expires_at:
            if read_data.access_token and read_data.access_token.strip():
                logger.debug(f"[기존 accees_token 유효함] {company_code}.{user_id} token expires_at: {read_data.expires_at}")
                return MyAccessToken(
                    access_token=read_data.access_token,
                    user_info=current_user
                    )
        
        # 만료된 경우 refresh token으로 갱신 발급
        if not read_data.refresh_token or not read_data.refresh_token.strip():
            raise HTTPException(
                status_code=404,
                detail=f"refresh 토큰이 비어 있습니다. {company_code}.{user_id}",
            )

        token_data = await self._refresh_token(app_name, company_code, read_data.refresh_token)

        # 토큰 데이터 저장
        await self._save_auth_user_token(app_name, company_code, user_id, token_data)

        # 갱신 발급된 토큰 회신하기
        if token_data.access_token:
            return MyAccessToken(
                access_token=token_data.access_token,
                user_info=current_user
            )
        
        raise HTTPException(
            status_code=500,
            detail=f"토큰 갱신 발급에 실패하였습니다. {company_code}.{user_id}",
        )
        
        
    
    async def _refresh_token(self, app_name: str, company_code: str, refresh_token: str) -> TokenData:
        
        # 데이터베이스에서 Graph Crendetail 정보 가져오기 
        config = await self._fetch_graph_infos(company_code, app_name)
        
        # 외부 HTTP 호출 
        token_url=f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/token"

        payload = {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        client = await get_httpx_client()
        response = await client.post(token_url, data=payload)

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Token exchange failed: {response.text}"
            )
        
        token_data = TokenData(**response.json())
        return token_data
    

    async def _get_auth_user_token(self, app_name: str, company_cd: str, user_id: str):
        async with self.db.session(company_cd) as session:
            auth_repo = AuthRepository(session)
            result = await auth_repo.get_user_token(app_name, user_id)
            return result
            
        
    
    
        
        

            
        


