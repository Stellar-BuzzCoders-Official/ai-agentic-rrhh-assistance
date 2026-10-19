from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General & Execution Mode
    ENVIRONMENT: Literal["development", "production", "test"] = "development"
    APP_NAME: str = "RRHH Screening Assistance API"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = True
    PORT: int = 5000
    HOST: str = "0.0.0.0"

    # Providers selection (Hexagonal architecture switches)
    LLM_PROVIDER: Literal["azure_openai", "gemini", "ollama"] = "azure_openai"
    JUDGE_LLM_PROVIDER: Literal["azure_openai", "gemini", "ollama"] = "azure_openai"
    EMBEDDING_PROVIDER: Literal["azure_openai", "gemini", "ollama"] = "azure_openai"
    STORAGE_PROVIDER: Literal["blob", "minio", "memory"] = "blob"
    PERSISTENCE_PROVIDER: Literal["cosmos", "memory"] = "cosmos"
    EXTRACTOR_PROVIDER: Literal["document_intelligence", "legacy_local"] = "document_intelligence"
    SAFETY_PROVIDER: Literal["azure", "noop"] = "noop"
    AUTH_PROVIDER: Literal["entra_id", "dev"] = "dev"

    # Talent pool & bulk upload limits
    BULK_UPLOAD_MAX_FILES: int = 10
    MAX_RELEVANT_CANDIDATES: int = 5
    EMBEDDING_DIMENSIONS: int = 1536

    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: Optional[str] = Field(default=None, alias="AZURE_ENDPOINT")
    AZURE_OPENAI_API_KEY: Optional[str] = Field(default=None, alias="AZURE_API_KEY")
    AZURE_OPENAI_DEPLOYMENT: str = Field(default="gpt-4o-mini", alias="AZURE_DEPLOYMENT")
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str = "text-embedding-3-small"
    AZURE_OPENAI_JUDGE_DEPLOYMENT: Optional[str] = None
    AZURE_OPENAI_API_VERSION: str = "2024-08-01-preview"

    # Google Gemini
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"

    # Azure Cosmos DB NoSQL
    COSMOS_ENDPOINT: Optional[str] = None
    COSMOS_KEY: Optional[str] = None
    COSMOS_CONNECTION_STRING: Optional[str] = None
    COSMOS_DATABASE_NAME: str = "rrhh"
    COSMOS_CHECKPOINTS_CONTAINER: str = "checkpoints"
    COSMOS_THREADS_CONTAINER: str = "threads"
    COSMOS_USERS_CONTAINER: str = "users"
    COSMOS_CANDIDATES_CONTAINER: str = "candidates"
    COSMOS_FILES_CONTAINER: str = "files"

    # Azure Blob Storage
    AZURE_STORAGE_CONNECTION_STRING: Optional[str] = None
    AZURE_STORAGE_ACCOUNT_NAME: Optional[str] = None
    AZURE_STORAGE_ACCOUNT_KEY: Optional[str] = None
    AZURE_STORAGE_CONTAINER_NAME: str = "rrhh-documents"

    # MinIO (legacy)
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: Optional[str] = None
    MINIO_SECRET_KEY: Optional[str] = None
    MINIO_BUCKET_NAME: str = "document-bucket"
    MINIO_SECURE: bool = False

    # Azure AI Document Intelligence
    DOCUMENT_INTELLIGENCE_ENDPOINT: Optional[str] = None
    DOCUMENT_INTELLIGENCE_KEY: Optional[str] = None

    # Azure AI Content Safety
    CONTENT_SAFETY_ENDPOINT: Optional[str] = None
    CONTENT_SAFETY_KEY: Optional[str] = None

    # Microsoft Entra ID
    ENTRA_TENANT_ID: Optional[str] = None
    ENTRA_CLIENT_ID: Optional[str] = None
    ENTRA_AUDIENCE: Optional[str] = None

    # Dev token for local testing without Entra ID config
    DEV_AUTH_USER_ID: str = "a8f0569a-46fd-457f-847e-e233af403114"
    DEV_AUTH_USER_EMAIL: str = "recruiter@joyit.ai"
    DEV_AUTH_USER_NAME: str = "Recruiter Default"


settings = Settings()
