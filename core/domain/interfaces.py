# core/domain/interfaces.py
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Any # Added Any for CacheService
from .models import (
    Sentence, Translation, WordBreakdown, AudioFile,
    GrammarNote, FlashCard, Deck, AudioFormat,
    Word, CardDifficulty, LanguageCode # Added LanguageCode
)

# Type alias for clarity
LanguagePair = Tuple[LanguageCode, LanguageCode]


class TranslationService(ABC):
    """Port for translation providers"""

    @abstractmethod
    async def translate(
        self,
        text: str,
        source_lang: LanguageCode,
        target_lang: LanguageCode
    ) -> Optional[Translation]: # Changed to Optional[Translation]
        """Translate text from source to target language"""
        pass

class DictionaryService(ABC):
    """Port for dictionary lookups"""

    @abstractmethod
    async def lookup_word(
        self,
        word: str,
        source_lang: LanguageCode,
        target_lang: LanguageCode
    ) -> Optional[Word]: # Changed to Optional[Word] for consistency
        """Get definition for a single word"""
        pass

    @abstractmethod
    async def analyze_sentence(
        self,
        sentence: str,
        source_lang: LanguageCode,
        target_lang: LanguageCode
    ) -> Optional[WordBreakdown]: # Changed to Optional[WordBreakdown]
        """Analyze all words in a sentence"""
        pass

class AudioService(ABC):
    """Port for text-to-speech"""

    @abstractmethod
    async def generate_audio(
        self,
        text: str,
        language: LanguageCode, # Base language code like 'fr'
        format: AudioFormat = AudioFormat.MP3
    ) -> Tuple[Optional[AudioFile], Optional[bytes]]: # Changed return type
        """
        Generate audio file model and data for text.
        Returns (None, None) on failure.
        """
        pass

class GrammarService(ABC):
    """Port for grammar explanations"""

    @abstractmethod
    async def explain_grammar(
        self,
        sentence: str,
        language: LanguageCode
    ) -> List[GrammarNote]: # Returns empty list on failure or if no notes
        """Generate grammar explanations"""
        pass

class SentenceSearchService(ABC):
    """Port for finding example sentences"""

    @abstractmethod
    async def search_by_topic(
        self,
        topic: str,
        language: LanguageCode,
        limit: int = 20
    ) -> List[Sentence]:
        """Find sentences about a topic"""
        pass

    @abstractmethod
    async def search_by_difficulty(
        self,
        difficulty: CardDifficulty,
        language: LanguageCode,
        limit: int = 20
    ) -> List[Sentence]:
        """Find sentences at difficulty level"""
        pass

class StorageService(ABC):
    """Port for file storage (e.g., audio files)"""

    @abstractmethod
    async def save_audio(self, audio: AudioFile, data: bytes) -> Optional[str]: # Return path/URL or None on failure
        """Save audio file and return its path or URL"""
        pass

    @abstractmethod
    async def get_audio(self, filename: str) -> Optional[bytes]: # Return bytes or None if not found
        """Retrieve audio file data"""
        pass

    @abstractmethod
    async def delete_audio(self, filename: str) -> bool: # Return True on success, False on failure
        """Delete audio file"""
        pass

class DeckExporter(ABC):
    """Port for exporting decks"""

    @abstractmethod
    async def export_deck(
        self,
        deck: Deck,
        output_path: str
    ) -> Optional[str]: # Return path or None on failure
        """Export deck to a file format (e.g., .apkg)"""
        pass

class CacheService(ABC):
    """Port for caching expensive operations"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]: # Updated typing
        """Get cached value"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None: # Updated typing
        """Cache value with optional TTL (Time To Live in seconds)"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool: # Return True/False for success
        """Remove from cache"""
        pass
