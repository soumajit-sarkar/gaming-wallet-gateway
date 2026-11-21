from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Also populate process environment so dynamic PROVIDER_<CODE>_API_KEY values
# are available to adapters and standalone worker scripts.
load_dotenv()


class Settings(BaseSettings):
    app_name: str = "Gaming Wallet Gateway"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    database_url: str
    redis_url: str | None = None
    rabbitmq_host: str = "127.0.0.1"
    rabbitmq_port: int = 5672
    rabbitmq_vhost: str = "/"
    rabbitmq_username: str = "guest"
    rabbitmq_password: str = "guest"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
