# infrastructure/config/settings.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # API Keys
    openai_api_key: str
    deepl_api_key: Optional[str] = None
    google_application_credentials: Optional[str] = None

    # Storage
    storage_type: str = "local"
    storage_path: str = "./storage"
    s3_bucket: Optional[str] = None
    s3_region: str = "us-east-1"

    # Audio
    audio_provider: str = "google"
    google_tts_voice: str = "fr-FR-Neural2-A"

    # Translation
    translation_provider: str = "openai"

    # Dictionary
    dictionary_provider: str = "openai"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        
        # This allows pydantic to find an env var like `OPENAI_API_KEY`
        # and map it to the field `openai_api_key`
        case_sensitive = False