from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    OSS_ACCESS_KEY_ID: str = ""
    OSS_ACCESS_KEY_SECRET: str = ""
    OSS_BUCKET_NAME: str = ""
    OSS_ENDPOINT: str = ""
    OSS_URL_EXPIRY_SECONDS: int = 604800

    WECHAT_TOKEN: str = ""
    WECHAT_APPID: str = ""
    WECHAT_APPSECRET: str = ""
    H5_BASE_URL: str = ""

    APP_ENV: str = "development"
    APP_VERSION: str = "1.0.0"


def get_settings() -> Settings:
    return Settings()
