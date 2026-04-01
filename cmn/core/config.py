from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8",extra=None)

    DATABASE_URL:str = ""
    COMPANY_CODES:list[str] = []

    

settings = Settings()