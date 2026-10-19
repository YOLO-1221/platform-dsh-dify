from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "platform2-situation"
    secret_key: str = "platform2-dev-secret-change-me"
    access_token_expire_minutes: int = 60 * 12
    database_url: str = "postgresql+psycopg://platform2@127.0.0.1:5432/platform2"
    # Platform chat SSE adapter (harness_bridge). True `dsh web` usually listens on :3080.
    harness_base_url: str = "http://127.0.0.1:3081"
    dify_base_url: str = "http://127.0.0.1:5001"
    service_token: str = "platform2-dify-local"
    use_mock_ai: bool = False
    use_mock_detection: bool = True

    class Config:
        env_prefix = "PLATFORM2_"


settings = Settings()
