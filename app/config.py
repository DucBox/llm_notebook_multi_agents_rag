from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql+asyncpg://llm_user:llm_pass@localhost:5432/llm_notebook"
    STORAGE_PATH: str = "/app/storage/documents"
    MAX_FILE_SIZE_MB: int = 50
    APP_VERSION: str = "1.0.0"

    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    EMBEDDING_BATCH_SIZE: int = 100

    GENERATION_MODEL: str = "gpt-5.4-mini"

    CONTEXT_LIMIT_TOKENS: int = 1000
    COMPACT_THRESHOLD: float = 0.8

    JWT_SECRET: str = "change-me-in-production-use-a-random-32-byte-hex"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    RERANKER_ENABLED: bool = True
    RERANKER_USE_FP16: bool = False  # False = CPU-safe; set True if GPU available

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


settings = Settings()
