from pydantic_settings import BaseSettings, SettingsConfigDict
import json

env_file = ".env"

DEFAULT_USER_EMAILS: dict[str, str] = {
    "skcc": "no@skcc.com",
    "skt": "no@sktelecom.com",
    "leodev901": "admin@leodev901.onmicrosoft.com",
}

EMAIL_COMPANY_MAP: dict[str, str] = {
    "skcc": "skcc.com",
    "skt": "sktelecom.com",
    "leodev901": "admin@leodev901.onmicrosoft.com",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=env_file,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Legacy env keys kept for backward compatibility.
    AZURE_CLIENT_ID: str = ""
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_SECRET: str = ""
    DEFAULT_USER_EMAIL: str = ""
    DEFAULT_COMPANY_CD: str = ""

    LOG_LEVEL: str
    ENV: str = "local"
    # app은 사용자 토큰을 직접 검증하지 않습니다.
    # 이 값은 이전 설정 파일과의 호환을 위해 읽기만 유지합니다.
    AUTH_JWT_USER_TOKEN: bool = False
    # CMN API 기본 주소입니다.
    # FastMCP 앱이 공통 인증/토큰 API를 호출할 때 사용하므로 명시적으로 분리합니다.
    CMN_API_BASE_URL: str = "http://127.0.0.1:8004"
    # 내부 API 타임아웃을 설정값으로 분리해 두면 운영 환경에서 조정이 쉽습니다.
    CMN_API_TIMEOUT_SECONDS: float = 10.0
    # 어떤 앱 이름으로 사용자 위임 토큰을 요청할지 명시적으로 고정합니다.
    M365_USER_TOKEN_APP_NAME: str = "MAIL"
    # 로컬 학습/테스트 환경에서 CMN용 테스트 토큰을 만들 때 참조할 수 있는 공통 JWT 설정입니다.
    # app 런타임은 이 값을 사용해 사용자 토큰을 직접 해석하지 않습니다.
    JWT_SECRET_KEY: str = "your_jwt_decode_secret_key"
    JWT_ALGORITHM: str = "HS256"

    GRAFANA_ENDPOINT: str = "http://grafana-alloy.grafana-alloy:4317"
    GRAFANA_INSTANCE_ID: str = ""
    GRAFANA_API_TOKEN: str = ""



    # Company-wise MS365 config JSON string.
    MS365_CONFIGS: str = "{}"
    # {
    #   "leodev901": {
    #       "tenant_id": "...",
    #       "client_id": "...",
    #       "client_secret": "...",
    #       "scopes": "...",
    #   }
    # }

    def get_m365_config(self, company_cd: str) -> dict:
        """Return MS365 configuration for the given company code."""

        # 문자열 JSON을 파이썬 딕셔너리로 전환 json.loads(str)
        configs = json.loads(self.MS365_CONFIGS)
        company = company_cd.lower()

        if company not in configs:
            raise ValueError(
                f"Company code '{company}' is not configured. Available: {list(configs.keys())}"
            )

        config = configs[company]
        # 위임 권한에서는 default user email 필요치 않음
        # config["default_user_email"] = config.get(
        #     "default_user_email",
        #     DEFAULT_USER_EMAILS.get(company, self.DEFAULT_USER_EMAIL),
        # )

        required_keys = [
            "tenant_id",
            "client_id",
            "client_secret",
            "redirect_uri",
            "scopes",
        ]

        missing_keys = [key for key in required_keys if not config.get(key)]
        if missing_keys:
            raise ValueError(
                f"Company code '{company}' is missing required keys: {missing_keys}"
            )
        return config
    
    def get_m365_scopes(self,company_cd:str) -> list[str]:
        config = self.get_m365_config(company_cd)
        scoeps = config["scopes"]
        return [  scope for scope in scoeps.split(" ") if scope ] 



settings = Settings()
