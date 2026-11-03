import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    database_path: str = os.getenv("DATABASE_PATH", "runtime/lingua.db")
    token: str = os.getenv("WORKSPACE_TOKEN", "")
    provider: str = os.getenv("AI_PROVIDER", "openai").lower()
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_chat_model: str = os.getenv("GEMINI_CHAT_MODEL", "gemini-3.5-flash-lite")
    gemini_embedding_model: str = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    max_model_requests_per_day: int = int(os.getenv("MAX_MODEL_REQUESTS_PER_DAY", "50"))
    api_key: str = os.getenv("OPENAI_API_KEY", "")
    chat_model: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")
    embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    production: bool = os.getenv("APP_ENV", "development") == "production"
    demo_seed: bool = os.getenv("DEMO_SEED", "true").lower() == "true"
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "5"))
    cors_origins: str = os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    )

    def __post_init__(self):
        if self.provider not in {"openai", "gemini"}:
            raise ValueError("AI_PROVIDER must be openai or gemini.")
        if self.max_model_requests_per_day < 1:
            raise ValueError("MAX_MODEL_REQUESTS_PER_DAY must be positive.")
        if self.provider == "gemini":
            # Explicit selection: never fall back to an existing OpenAI key.
            self.api_key = self.gemini_api_key
            self.chat_model = self.gemini_chat_model
            self.embedding_model = self.gemini_embedding_model

    @property
    def embedding_cache_key(self):
        if self.provider == "gemini":
            return f"gemini:{self.embedding_model}:768:similarity"
        return self.embedding_model
