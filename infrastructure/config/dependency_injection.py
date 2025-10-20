# infrastructure/config/dependency_injection.py
from functools import lru_cache
import os
from core.domain.interfaces import (
    TranslationService, DictionaryService, AudioService,
    StorageService, CacheService, GrammarService
)
from core.use_cases.generate_card import GenerateCardUseCase
from core.use_cases.generate_deck import GenerateDeckUseCase
from adapters.translation.deepl_adapter import DeepLTranslationAdapter
from adapters.translation.openai_adapter import OpenAITranslationAdapter
from adapters.dictionary.openai_dictionary_adapter import OpenAIDictionaryAdapter
from adapters.grammar.openai_grammar_adapter import OpenAIGrammarAdapter
from adapters.audio.google_tts_adapter import GoogleTTSAdapter
from adapters.storage.local_file_storage import LocalFileStorage
from adapters.storage.s3_storage import S3StorageAdapter
from .settings import Settings

class ServiceContainer:
    """Dependency injection container"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._translation_service = None
        self._dictionary_service = None
        self._grammar_service = None
        self._audio_service = None
        self._storage_service = None
    
    @property
    def translation_service(self) -> TranslationService:
        if self._translation_service is None:
            if self.settings.translation_provider == "deepl":
                self._translation_service = DeepLTranslationAdapter(
                    api_key=self.settings.deepl_api_key
                )
            else:
                self._translation_service = OpenAITranslationAdapter(
                    api_key=self.settings.openai_api_key
                )
        return self._translation_service
    
    @property
    def dictionary_service(self) -> DictionaryService:
        if self._dictionary_service is None:
            self._dictionary_service = OpenAIDictionaryAdapter(
                api_key=self.settings.openai_api_key
            )
        return self._dictionary_service

    @property
    def grammar_service(self) -> GrammarService:
        if self._grammar_service is None:
            self._grammar_service = OpenAIGrammarAdapter(
                api_key=self.settings.openai_api_key
            )
        return self._grammar_service
    
    @property
    def audio_service(self) -> AudioService:
        if self._audio_service is None:
            # Check if the path is set in our settings
            if self.settings.google_application_credentials:
                
                # Set the environment variable so the Google client can find it
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.settings.google_application_credentials
                
                self._audio_service = GoogleTTSAdapter(
                    voice_name=self.settings.google_tts_voice
                )
            else:
                print("⚠️  Warning: GOOGLE_APPLICATION_CREDENTIALS not set. Audio generation will be disabled.")
                # Return a mock or disabled service
                from tests.mocks import MockAudioService
                self._audio_service = MockAudioService(disable=True)
        return self._audio_service
    
    @property
    def storage_service(self) -> StorageService:
        if self._storage_service is None:
            if self.settings.storage_type == "s3":
                self._storage_service = S3StorageAdapter(
                    bucket_name=self.settings.s3_bucket,
                    region=self.settings.s3_region
                )
            else:
                self._storage_service = LocalFileStorage(
                    base_path=self.settings.storage_path
                )
        return self._storage_service
    
    def create_card_generator(self) -> GenerateCardUseCase:
        """Factory for card generation use case"""
        return GenerateCardUseCase(
            translation_service=self.translation_service,
            dictionary_service=self.dictionary_service,
            audio_service=self.audio_service,
            grammar_service=self.grammar_service
        )
    
    def create_deck_generator(self) -> GenerateDeckUseCase:
        """Factory for deck generation use case"""
        from adapters.anki.genanki_exporter import GenankiExporter
        
        return GenerateDeckUseCase(
            card_generator=self.create_card_generator(),
            exporter=GenankiExporter(),
            storage=self.storage_service
        )

@lru_cache()
def get_container() -> ServiceContainer:
    """Get singleton container"""
    settings = Settings()
    return ServiceContainer(settings)