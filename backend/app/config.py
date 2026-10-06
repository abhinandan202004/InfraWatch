from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./infrawatch.db"  # compose overrides with Postgres
    jwt_secret: str = "dev-secret-change-me"
    jwt_expire_minutes: int = 60 * 12
    google_client_id: str = ""

    kafka_enabled: bool = False
    kafka_bootstrap: str = "localhost:9092"

    zinc_url: str = "http://localhost:4080"
    zinc_user: str = "admin"
    zinc_password: str = "admin123"

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "infrawatch@localhost"


settings = Settings()
