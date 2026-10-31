from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    env: str = "development"
    log_level: str = "INFO"
    database_url: str = (
        "postgresql+psycopg://sunpower:local_dev_password_change_me@db:5432/sunpower"
    )
    redis_url: str = "redis://redis:6379/0"
    jwt_secret: str = "local_only_change_me_to_a_long_random_secret"
    jwt_expire_minutes: int = 60
    cors_origins: str = "http://localhost,http://localhost:5173"
    storage_dir: str = "/app/storage"
    max_upload_mb: int = 10

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
