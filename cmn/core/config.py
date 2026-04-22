from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8",extra=None)

    APP_NAME:str = "Smaple App"
    LOG_LEVEL:str = "INFO"
    LOG_FILE_PATH:str = "logs/mcp-cmn.log"
    ENV:str = "local"
    
    DATABASE_URL:str = ""
    COMPANY_CODES:list[str] = ["leodev901"]
    

    GRAFANA_ENDPOINT: str = ""
    GRAFANA_INSTANCE_ID: str = ""
    GRAFANA_API_TOKEN: str = ""

    ENABLE_OTEL_DIRECT: bool = False
    OTEL_SERVICE_NAME: str = "mcp-cmn"
    OTEL_SERVICE_VERSION: str = "1.0.0"

settings = Settings()
