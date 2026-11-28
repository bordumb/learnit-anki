# infrastructure/config/dependency_injection.py
from functools import lru_cache
import os
from pathlib import Path
from core.domain.interfaces import (
    TranslationService, TranslationError, DictionaryService, AudioService,
    StorageService, CacheService, GrammarService, DeckExporter
)
from core.use_cases.generate_card import GenerateCardUseCase
from core.use_cases.generate_deck import GenerateDeckUseCase
from core.use_cases.transcribe_media import TranscribeMediaUseCase
from adapters.translation.deepl_adapter import DeepLTranslationAdapter
from adapters.translation.openai_adapter import OpenAITranslationAdapter
from adapters.grammar.openai_grammar_adapter import OpenAIGrammarAdapter
from adapters.storage.local_file_storage import LocalFileStorage
from adapters.storage.s3_storage import S3StorageAdapter
from .settings import Settings
from typing import Optional

# Define a simple mock or placeholder for when audio is disabled
class DisabledAudioService(AudioService):
    async def generate_audio(self, text: str, language: str, format = None) -> Optional[tuple]:
        print("Audio generation is disabled (no Google credentials).")
        return None, None # Return None for both model and data

class ServiceContainer:
    """Dependency injection container"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._translation_service: Optional[TranslationService] = None
        self._dictionary_service: Optional[DictionaryService] = None
        self._grammar_service: Optional[GrammarService] = None
        self._audio_service: Optional[AudioService] = None
        self._storage_service: Optional[StorageService] = None
        self._deck_exporter: Optional[DeckExporter] = None

    @property
    def translation_service(self) -> TranslationService:
        if self._translation_service is None:
            # Use source/target languages later if needed by adapter init
            if self.settings.translation_provider == "deepl" and self.settings.deepl_api_key:
                self._translation_service = DeepLTranslationAdapter(
                    api_key=self.settings.deepl_api_key
                )
            elif self.settings.openai_api_key:
                 self._translation_service = OpenAITranslationAdapter(
                    api_key=self.settings.openai_api_key
                )
            else:
                 raise TranslationError("Configure a translation provider in the project’s .env file.")
        return self._translation_service

    @property
    def dictionary_service(self) -> DictionaryService:
        if self._dictionary_service is None:
            if not self.settings.openai_api_key:
                 raise ValueError("OpenAI API key is required for the dictionary service.")
            from adapters.dictionary.openai_dictionary_adapter import OpenAIDictionaryAdapter

            self._dictionary_service = OpenAIDictionaryAdapter(
                api_key=self.settings.openai_api_key
            )
        return self._dictionary_service

    @property
    def grammar_service(self) -> GrammarService:
        if self._grammar_service is None:
            if not self.settings.openai_api_key:
                 raise ValueError("OpenAI API key is required for the grammar service.")
            self._grammar_service = OpenAIGrammarAdapter(
                api_key=self.settings.openai_api_key
            )
        return self._grammar_service

    @property
    def audio_service(self) -> AudioService:
        if self._audio_service is None:
            if self.settings.google_application_credentials:
                # Set the environment variable so the Google client can find it
                # Ensure the path exists before setting
                cred_path = self.settings.google_application_credentials
                if os.path.exists(cred_path):
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path
                    # Pass the voice dictionary to the adapter
                    from adapters.audio.google_tts_adapter import GoogleTTSAdapter

                    self._audio_service = GoogleTTSAdapter(
                        voice_map=self.settings.google_tts_voices
                    )
                else:
                    print(f"⚠️ Warning: Google credentials file not found at '{cred_path}'. Audio disabled.")
                    self._audio_service = DisabledAudioService()
            else:
                print("⚠️ Warning: GOOGLE_APPLICATION_CREDENTIALS not set. Audio generation will be disabled.")
                self._audio_service = DisabledAudioService()
        return self._audio_service

    @property
    def storage_service(self) -> StorageService:
        if self._storage_service is None:
            if self.settings.storage_type == "s3":
                if not self.settings.s3_bucket:
                     raise ValueError("S3_BUCKET must be set when storage_type is 's3'.")
                self._storage_service = S3StorageAdapter(
                    bucket_name=self.settings.s3_bucket,
                    region=self.settings.s3_region
                )
            else: # Default to local
                self._storage_service = LocalFileStorage(
                    base_path=self.settings.storage_path
                )
        return self._storage_service

    @property
    def deck_exporter(self) -> DeckExporter:
        """Provides the deck exporter instance."""
        if self._deck_exporter is None:
            # Currently only GenankiExporter is implemented
            from adapters.anki.genanki_exporter import GenankiExporter

            self._deck_exporter = GenankiExporter(Path(self.settings.storage_path) / "audio")
        return self._deck_exporter

    def create_image_transcriber(self) -> TranscribeMediaUseCase:
        from adapters.transcription.google_vision import GoogleVisionTranscriber

        return TranscribeMediaUseCase(
            GoogleVisionTranscriber(self.settings.google_application_credentials)
        )

    def create_audio_transcriber(self) -> TranscribeMediaUseCase:
        if not self.settings.openai_api_key:
            raise ValueError("Set OPENAI_API_KEY to transcribe audio.")
        from adapters.transcription.openai_speech import OpenAISpeechTranscriber

        return TranscribeMediaUseCase(
            OpenAISpeechTranscriber(
                self.settings.openai_api_key, self.settings.openai_transcription_model
            )
        )

    def create_card_generator(self, *, manual_translation: bool = False) -> GenerateCardUseCase:
        """Factory for card generation use case"""
        return GenerateCardUseCase(
            translation_service=None if manual_translation else self.translation_service,
            dictionary_service=None if manual_translation else self.dictionary_service,
            audio_service=self.audio_service,
            storage_service=self.storage_service,
            grammar_service=None if manual_translation else self.grammar_service,
            # Pass default languages from settings
            default_source_lang=self.settings.default_source_language,
            default_target_lang=self.settings.default_target_language
        )

    def create_deck_generator(self) -> GenerateDeckUseCase:
        """Factory for deck generation use case"""
        return GenerateDeckUseCase(
            card_generator=self.create_card_generator(),
            exporter=self.deck_exporter, # Use the property
            storage=self.storage_service,
             # Pass default languages from settings
            default_source_lang=self.settings.default_source_language,
            default_target_lang=self.settings.default_target_language
        )

@lru_cache()
def get_container() -> ServiceContainer:
    """Get singleton container"""
    # Load settings - this might raise validation errors if .env is incorrect
    try:
        settings = Settings()
    except Exception as e:
        # Provide a more helpful error message during startup
        print(f"❌ Error loading application settings: {e}")
        print("💡 Please check your .env file for missing or invalid values.")
        # Re-raise the exception to halt execution if settings are invalid
        raise
    return ServiceContainer(settings)
