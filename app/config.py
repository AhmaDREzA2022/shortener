from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://shortener:shortener@localhost:5432/shortener"
    test_database_url: str = (
        "postgresql+psycopg://shortener:shortener@localhost:5432/shortener_test"
    )
    base_url: str = "http://127.0.0.1:8000"


settings = Settings()
