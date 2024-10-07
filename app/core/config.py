# Package imports
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    This class defines the settings for the application, including environment variables and configuration.
    """
    # Celery settings
    celery_broker_url: str
    celery_result_backend: str
    
    # PostgreSQL settings
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_host: str = 'db'
    postgres_port: str = '5432'

    # The name of the collection in the vector database
    faq_collection_name: str

    # The algorithm used for encoding and decoding JWT tokens
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    secret_key: str

    # The batch size for the vector database
    batch_size: int = 30

    # The similarity between local and prompt embeddings
    similarity_threshold: float = 0.85

    # OpenAI model settings
    openai_api_key: str
    openai_model_name: str = "gpt-3.5-turbo"
    openai_model_max_tokens: int = 200
    openai_model_n: int = 1
    openai_model_temperature: float = 0.3

    model_config = SettingsConfigDict(env_file=".env")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache()
def get_settings() -> Settings:
    """
    This function returns the settings instance, using the lru_cache decorator to improve performance.
    """
    return Settings()
