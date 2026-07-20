from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # asyncpg, not psycopg: psycopg's async mode hard-refuses to run under
    # Windows' ProactorEventLoop, which Playwright's async API requires for
    # its subprocess-based browser driver. asyncpg has no such restriction,
    # so both can share one event loop in-process (see Module 1's crawler).
    database_url: str = "postgresql+asyncpg://mxrating:mxrating@localhost:5432/mxrating"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
