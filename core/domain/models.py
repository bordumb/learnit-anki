# core/domain/models.py
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, TypeAlias, Any # Added TypeAlias, Any
from datetime import datetime
from enum import Enum
import uuid
import logging # Added logging

# Configure logging
logger = logging.getLogger(__name__)

# --- Type Aliases ---
LanguageCode: TypeAlias = str # e.g., "en", "fr", "de"
LanguagePair: TypeAlias = Tuple[LanguageCode, LanguageCode] # e.g., ("fr", "en")

# --- Enums ---
class AudioFormat(Enum):
    MP3 = "mp3"
    OGG = "ogg"
    WAV = "wav"

class CardDifficulty(Enum):
    A1 = "beginner"
    A2 = "elementary"
    B1 = "intermediate"
    B2 = "upper_intermediate"
    C1 = "advanced"
    C2 = "proficient"

# --- Data Classes ---
@dataclass
class Word:
    """Individual word with definition."""
    text: str
    lemma: str  # Base form (e.g., "manger" for "mangent")
    pos: str    # Part of speech (e.g., "noun", "verb")
    definition: str # Definition in the target language (e.g., English)
    definition_native: Optional[str] = None # Definition in the source language (e.g., French)
    pronunciation: Optional[str] = None

@dataclass
class Sentence:
    """A sentence in the source language."""
    text: str
    language: LanguageCode # The language code of this sentence (e.g., "fr")
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: Optional[str] = None  # Where it came from (URL, book, etc.)
    difficulty: Optional[CardDifficulty] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class Translation:
    """Translation of a sentence."""
    text: str
    target_language: LanguageCode # The language code this text is translated into (e.g., "en")
    confidence: Optional[float] = None  # Confidence score (0-1), if available
    provider: str = "unknown" # Which service provided the translation

@dataclass
class WordBreakdown:
    """Word-by-word analysis of a sentence."""
    words: List[Word]

@dataclass
class AudioFile:
    """Audio recording of a sentence."""
    filename: str # Filename (e.g., "hash123.mp3")
    format: AudioFormat # e.g., MP3, OGG
    language: Optional[LanguageCode] = None # Language of the audio (e.g., "fr")
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    duration_seconds: Optional[float] = None
    url: Optional[str] = None  # URL if stored remotely (e.g., S3)
    provider: str = "unknown" # Which service generated the audio

@dataclass
class GrammarNote:
    """Grammar explanation related to a sentence."""
    title: str
    explanation: str
    examples: List[str] = field(default_factory=list)

@dataclass
class FlashCard:
    """Complete flashcard with all components."""
    sentence: Sentence
    translation: Translation
    word_breakdown: WordBreakdown
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    audio: Optional[AudioFile] = None
    grammar_notes: List[GrammarNote] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_anki_fields(self) -> dict:
        """
        Convert card data to a simple dictionary format.
        Note: This is a basic representation; the actual Anki fields
        depend on the exporter and card model used.
        """
        # Basic example, adjust based on actual exporter needs
        try:
            return {
                "SourceText": self.sentence.text,
                "TargetText": self.translation.text,
                "WordBreakdown": self._format_word_breakdown_simple(),
                "Audio": f"[sound:{self.audio.filename}]" if self.audio and self.audio.filename else "",
                "GrammarNotes": self._format_grammar_notes_simple(),
                "SourceLanguage": self.sentence.language,
                "TargetLanguage": self.translation.target_language,
                "Tags": " ".join(self.tags)
            }
        except AttributeError as e:
            logger.error(f"Error converting FlashCard (ID: {self.id}) to Anki fields: Missing attribute {e}", exc_info=True)
            # Return a minimal dict or raise an error depending on desired handling
            return {"SourceText": getattr(self.sentence, 'text', 'Error'), "TargetText": "Error"}


    def _format_word_breakdown_simple(self) -> str:
        """Generates a simple string representation for word breakdown."""
        if not self.word_breakdown or not self.word_breakdown.words:
            return ""
        lines = []
        for word in self.word_breakdown.words:
            native_def = f" ({self.sentence.language}: {word.definition_native})" if word.definition_native else ""
            lines.append(f"{word.text} ({word.pos}): {word.definition}{native_def}")
        return "\n".join(lines)

    def _format_grammar_notes_simple(self) -> str:
        """Generates a simple string representation for grammar notes."""
        if not self.grammar_notes:
            return ""
        lines = []
        for note in self.grammar_notes:
            lines.append(f"- {note.title}: {note.explanation}")
            if note.examples:
                lines.append("  Examples: " + "; ".join(note.examples))
        return "\n".join(lines)

@dataclass
class Deck:
    """Collection of flashcards for a specific language pair."""
    name: str
    language_pair: LanguagePair # Tuple of (source_lang_code, target_lang_code)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: Optional[str] = None
    cards: List[FlashCard] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)

