from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "NL2SQL-RAG"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True
    log_level: str = "INFO"

    openai_api_key: str = ""
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 2048

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "rag_user"
    postgres_password: str = "rag_password"
    postgres_db: str = "nl2sql_rag"

    @property
    def postgres_url(self) -> str:
        return (f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}")

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "nl2sql_schemas"

    dense_embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    sparse_embed_model: str = "prithivida/Splade_PP_en_v1"
    hybrid_search: bool = True
    reranker_model: str = "ms-marco-MiniLM-L-12-v2"

    target_db_type: str = "postgresql"
    target_db_host: str = "localhost"
    target_db_port: int = 5432
    target_db_user: str = "db_user"
    target_db_password: str = "db_password"
    target_db_name: str = "your_database"

    rate_limit_requests: int = 100
    rate_limit_window: int = 60

    secret_key: str = "change-me-in-production"
    api_key_header: str = "X-API-Key"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8",
        case_sensitive=False, extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
