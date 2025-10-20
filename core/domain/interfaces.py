# core/domain/interfaces.py
from abc import ABC, abstractmethod
from typing import List, Optional
from .models import (
    Sentence, Translation, WordBreakdown, AudioFile, 
    GrammarNote, FlashCard, Deck, AudioFormat,
    Word, CardDifficulty
)

class TranslationService(ABC):
    """Port for translation providers"""
    
    @abstractmethod
    async def translate(
        self, 
        text: str, 
        source_lang: str, 
        target_lang: str
    ) -> Translation:
        """Translate text from source to target language"""
        pass

class DictionaryService(ABC):
    """Port for dictionary lookups"""
    
    @abstractmethod
    async def lookup_word(
        self, 
        word: str, 
        source_lang: str,
        target_lang: str
    ) -> Word:
        """Get definition for a single word"""
        pass
    
    @abstractmethod
    async def analyze_sentence(
        self, 
        sentence: str,
        source_lang: str,
        target_lang: str
    ) -> WordBreakdown:
        """Analyze all words in a sentence"""
        pass

class AudioService(ABC):
    """Port for text-to-speech"""
    
    @abstractmethod
    async def generate_audio(
        self, 
        text: str, 
        language: str,
        format: AudioFormat = AudioFormat.MP3
    ) -> AudioFile:
        """Generate audio file for text"""
        pass

class GrammarService(ABC):
    """Port for grammar explanations"""
    
    @abstractmethod
    async def explain_grammar(
        self, 
        sentence: str,
        language: str
    ) -> List[GrammarNote]:
        """Generate grammar explanations"""
        pass

class SentenceSearchService(ABC):
    """Port for finding example sentences"""
    
    @abstractmethod
    async def search_by_topic(
        self, 
        topic: str,
        language: str,
        limit: int = 20
    ) -> List[Sentence]:
        """Find sentences about a topic"""
        pass
    
    @abstractmethod
    async def search_by_difficulty(
        self,
        difficulty: CardDifficulty,
        language: str,
        limit: int = 20
    ) -> List[Sentence]:
        """Find sentences at difficulty level"""
        pass

class StorageService(ABC):
    """Port for file storage"""
    
    @abstractmethod
    async def save_audio(self, audio: AudioFile, data: bytes) -> str:
        """Save audio file and return path/URL"""
        pass
    
    @abstractmethod
    async def get_audio(self, filename: str) -> bytes:
        """Retrieve audio file"""
        pass
    
    @abstractmethod
    async def delete_audio(self, filename: str) -> None:
        """Delete audio file"""
        pass

class DeckExporter(ABC):
    """Port for exporting decks"""
    
    @abstractmethod
    async def export_deck(
        self, 
        deck: Deck,
        output_path: str
    ) -> str:
        """Export deck to file format (.apkg, JSON, etc.)"""
        pass

class CacheService(ABC):
    """Port for caching expensive operations"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[any]:
        """Get cached value"""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: any, ttl: Optional[int] = None) -> None:
        """Cache value with optional TTL"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove from cache"""
        pass