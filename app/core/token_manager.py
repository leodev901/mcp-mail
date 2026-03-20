import httpx
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from app.core.config import settings
from loguru import logger


BASE_URL = "http://localhost:8003/auth/m365/start"

class AuthRequiredError(Exception):
    def __init__(self, code:str, message: str,connect_url:str):
        super().__init__(message)
        self.code = code
        self.message = message
        self.connect_url = connect_url



@dataclass
class TokenRecord:
    # dataclass는 여러 값을 묶어서 다루기 쉽게 만드는 문법입니다.
    # 여기서는 "사용자 1명의 M365 토큰 세트"를 표현합니다.
    user_id:str
    company_cd:str
    access_token:str
    refresh_token:str
    access_token_expires_at: datetime

@dataclass
class OAuthStateRecord:
    # OAuth 로그인 시작 시 만든 state 값을 콜백에서 검증하기 위한 임시 데이터입니다.
    user_id: str
    company_cd :str
    created_at: datetime



class TokenManager:
    """
    지금 단계에서는 메모리 기반 저장소로 구현합니다.
    나중에 DB로 바꿔도 메서드 이름을 유지하면 다른 코드 수정이 적어집니다.
    """

    def __init__(self):
        # 사용자별 토큰 저장소입니다.
        # {key : TokenRecoard} 형식의 Dictionary로 저장
        # key 예시: "leodev901.20075487"
        self._tokens: dict[str, TokenRecord] = {}


        # OAuth state 임시 저장소입니다.
        # key 예시: "랜덤-state-문자열"
        self._states: dict[str,OAuthStateRecord] = {}
    
    def _build_token_key(self, user_id:str, company_cd:str ) -> str:
        # 회사가 다르면 같은 user_id라도 다른 사용자로 봐야 하므로 복합 키를 만듭니다.
        return f"{company_cd}.{user_id}"

    def save_tokens(self, 
            user_id:str, 
            company_cd:str, 
            access_token:str, 
            refresh_token:str, 
            expires_in
        ) -> TokenRecord:
        # expires_in은 "지금부터 몇 초 뒤 만료되는지"를 뜻합니다.
        # 실제 만료 직전 오차를 줄이기 위해 2분 먼저 만료로 간주합니다.
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=max(expires_in - 120, 0)
        )

        record = TokenRecord(
            user_id=user_id,
            company_cd=company_cd,
            access_token=access_token,
            refresh_token=refresh_token,
            access_token_expires_at=expires_at
        )

        # TO-DO 세이브 전에 기존 메모리 혹은 DB에 key값이 중복될 경우에는?

        key = self._build_token_key(user_id, company_cd)
        self._tokens[key] = record

        logger.info(f"save token {record}")

        return record

    def get_tokens(self, user_id:str, company_cd:str) -> TokenRecord | None:
        key = self._build_token_key(user_id, company_cd)
        return self._tokens.get(key)
    
    def delete_tokens(self, user_id:str, company_cd:str) -> None:
        key = self._build_token_key(user_id, company_cd)
        logger.info(f"delete token {user_id, company_cd}")
        self._tokens.pop(key, None)
        
    
    def is_access_token_valid(self, user_id: str, company_cd: str) -> bool:
        record = self.get_tokens(user_id, company_cd)
        if record is None:
            return False

        # 현재 시간이 만료 시각보다 이전이면 아직 유효하다고 판단합니다.
        return datetime.now(timezone.utc) < record.access_token_expires_at

    def save_oauth_state(self, state: str, user_id: str, company_cd: str) -> OAuthStateRecord:
        record = OAuthStateRecord(
            user_id=user_id,
            company_cd=company_cd,
            created_at=datetime.now(timezone.utc),
        )
        self._states[state] = record
        logger.info(f"save oauth state {record}")
        return record

    def pop_oauth_state(self, state: str) -> OAuthStateRecord | None:
        # pop은 "꺼내면서 삭제"하는 문법입니다.
        # OAuth state는 1회성 값이라 재사용되면 안 되므로 pop이 맞습니다.
        logger.info(f"clear oauth state {state}")
        return self._states.pop(state, None)
    

    async def refresh_access_token(self, record:TokenRecord) -> str:
        """refresh 토큰을 사용하여 acceess token을 갱신 합니다."""

        configs = settings.get_m365_config(record.company_cd)

        refresh_token_url = f"https://login.microsoftonline.com/{configs['tenant_id']}/oauth2/v2.0/token"

        payload = {
            "client_id":configs['client_id'],
            "client_secret":configs['client_secret'],
            "grant_type":"refresh_token",
            "refresh_token":record.refresh_token,
            "redirect_uri":configs['redirect_uri'],
            "scope":configs['scopes'],
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(refresh_token_url, data=payload)
            # resp.raise_for_status()

        if resp.status_code != 200:
            # TO-DO: 토큰 갱신 실패 
            # 재동의를 해버리면 _tokens에 키가 중복되어서 안됨
            # 어떻게 해결 할 것인지? 무조건 _tokens 지우고 다시 동의?
            raise NotImplementedError("refresh_access_toeken에서 토큰 갱신 요청 http 응답이 200이 아님")
        
        data = resp.json()
        
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token",record.refresh_token)
        expires_in = int(data.get("expires_in", 3600))


        if not access_token:
            # TO-DO: refersh
            raise NotImplementedError("refresh_access_toeken에서 토큰 갱신 응답 받았으나 acceess_toekn이 비어있음")
        
        # 토큰 메모리 or DB에 업데이트
        self.save_tokens(
            user_id=record.user_id,
            company_cd=record.company_cd,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )

        return access_token




    async def get_valid_access_token(self, user_id: str, company_cd:str) -> str | None:
        record = self.get_tokens(user_id, company_cd)

        if record is None:
            #TO-DO 신규 동의를 받아야 함
            raise AuthRequiredError(
                code="AUTH_REQUIRED_NOT_FOUND_TOKEN",
                message="token이 없으므로 신규 동의를 받아야 합니다. 연결 URL에 접속하여 동의를 먼저 진행해주세요",
                connect_url=f"{BASE_URL}?user_id={user_id}&company_cd={company_cd}",
            )
        
        if not self.is_access_token_valid(user_id, company_cd):
            #TO-DO rfersh 토큰으로 새로 발급 받기 
            access_token = await self.refresh_access_token(record)
            return access_token
        
        return record.access_token
    


# 다른 파일에서 바로 import 해서 쓸 수 있도록 단일 인스턴스를 만듭니다.
token_manager = TokenManager()