# infrastructure/config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Dict
import json
import os

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
    # --- New: Dictionary for Language-Specific Voices ---
    # This dictionary maps language codes (e.g., 'fr', 'de') to Google TTS voice names.
    # It can be overridden via an environment variable GOOGLE_TTS_VOICES
    # Example .env entry:
    # GOOGLE_TTS_VOICES='{"fr": "fr-FR-Neural2-A", "de": "de-DE-Neural2-B", "es": "es-ES-Neural2-A"}'
    google_tts_voices: Dict[str, str] = {
        "fr": "fr-FR-Neural2-A",
        "de": "de-DE-Neural2-B",
        "es": "es-ES-Neural2-A",
        # Add more languages and voices here as needed
    }
    # --- End New Voice Dictionary ---

    # Translation
    translation_provider: str = "openai"

    # Dictionary
    dictionary_provider: str = "openai"

    # Language Settings
    default_source_language: str = "fr"
    default_target_language: str = "en"

    # Pydantic V2 configuration using model_config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Allow extra fields (useful if env file has more vars than defined here)
        extra='ignore'
    )

    # Custom validator/parser for the dictionary from env var if needed
    # (Pydantic might handle simple JSON strings automatically, but complex cases might need this)
    # @validator('google_tts_voices', pre=True)
    # def parse_google_tts_voices(cls, v):
    #     if isinstance(v, str):
    #         try:
    #             return json.loads(v)
    #         except json.JSONDecodeError:
    #             raise ValueError("GOOGLE_TTS_VOICES env var is not valid JSON")
    #     return v

