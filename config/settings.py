from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    stripe_public_key: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_currency: str = "usd"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
