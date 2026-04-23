import httpx
from fastapi import Depends, HTTPException
from loguru import logger
from datetime import datetime, timedelta, timezone


from cmn.core.database import Database
from cmn.core.dependencies import get_db
from cmn.db.crud.m365_oauth_crud import get_graph_infos
from cmn.repositories.auth_repository import AuthRepository
from cmn.utils.token_manager import token_manager


KST = timezone(timedelta(hours=9))


class AuthService:
    # 이 서비스는 현재 회사 schema가 적용된 DB 세션으로
    # 앱 권한(Client Credentials) 토큰 발급에 필요한 설정을 조회합니다.
    def __init__(self, db: Database = Depends(get_db)):
        # 생성자에서 AsyncSession을 받아 두면 같은 요청 안에서 재사용할 수 있습니다.
        self.db = db

    async def get_oauth_token(self, company_cd: str, app_name: str) -> dict[str, str]:

        # 입력값 정규화를 먼저 해야 설정 조회 실패를 줄일 수 있습니다.
        company_cd = company_cd.strip()
        app_name = app_name.strip().upper()

        if not company_cd or not app_name:
            raise HTTPException(
                status_code=400,
                detail="company_cd and app_name are required",
            )
            
        token = await self._handle_token(company_cd, app_name)
                

        # TO-DO 그 외 다른 서비스 로직이 있을 경우 여기에서 처리 
        # user info 해석
        user_info = "user"

        result = {
            "user_info":user_info,
            "token":token
        }

        # 최종 반환
        return result 
    

    async def _handle_token(self, company_cd: str, app_name: str) -> dict[str, str]:
        key = token_manager.build_key(company_cd, app_name)

        cached_token = token_manager.get_valid_access_token(key)
        if cached_token:
            logger.debug(f"Hit cached_token -> {key}")
            return {"access_token": cached_token}

        async with token_manager.get_lock(key):
            cached_token = token_manager.get_valid_access_token(key)
            if cached_token:
                logger.debug(f"Hit cached_token -> {key}")
                return {"access_token": cached_token}

            logger.info(f"issue token -> {key}")

            async with self.db.session(company_cd) as session:
                repo = AuthRepository(session)
                graph_infos = await repo.get_graph_infos(app_name)

            if not graph_infos:
                raise HTTPException(
                    status_code=404,
                    detail=f"graph config not found: app_name={app_name}",
                )

            config = {row.key: row.value for row in graph_infos}
            required_keys = ("tenant_id", "client_id", "client_secret")
            missing_keys = [key for key in required_keys if not config.get(key)]
            if missing_keys:
                raise HTTPException(
                    status_code=500,
                    detail=f"missing graph config keys: {', '.join(missing_keys)}",
                )

            token_url = f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/token"
            request_payload = {
                "grant_type": "client_credentials",
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "scope": "https://graph.microsoft.com/.default",
            }

            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(token_url, data=request_payload)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"token exchange failed: {response.text}",
                )

            token_data = response.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise HTTPException(
                    status_code=502,
                    detail="access_token missing in token response",
                )

            expiread_at = datetime.now(KST) + timedelta(
                seconds=int(token_data.get("expires_in", 1800))
            )

            token_manager.save_token(key, access_token, expiread_at)
            return {"access_token": access_token}


    

    


