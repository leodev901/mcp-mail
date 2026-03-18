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
    AUTH_JWT_USER_TOKEN:bool = False

    GRAFANA_ENDPOINT: str = "http://grafana-alloy.grafana-alloy:4317"
    GRAFANA_INSTANCE_ID: str = ""
    GRAFANA_API_TOKEN: str = ""

    # Company-wise MS365 config JSON string.
    MS365_CONFIGS: str = "{}"

    def get_m365_config(self, company_cd: str) -> dict:
        """Return MS365 configuration for the given company code."""

        configs = json.loads(self.MS365_CONFIGS)
        company = company_cd.lower()

        if company not in configs:
            raise ValueError(
                f"Company code '{company}' is not configured. Available: {list(configs.keys())}"
            )

        config = configs[company]
        config["default_user_email"] = config.get(
            "default_user_email",
            DEFAULT_USER_EMAILS.get(company, self.DEFAULT_USER_EMAIL),
        )
        return config


settings = Settings()
