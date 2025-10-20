# core/domain/models.py
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid

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

@dataclass
class Word:
    """Individual word with definition"""
    text: str
    lemma: str  # Base form (e.g., "manger" for "mangent")
    pos: str    # Part of speech
    definition: str # This is the English definition
    pronunciation: Optional[str] = None
    definition_fr: Optional[str] = None # <-- Add this line
    
@dataclass
class Sentence:
    """A sentence in the source language"""
    # Non-default fields must come first
    text: str
    
    # Fields with defaults
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    language: str = "fr"
    source: Optional[str] = None  # Where it came from (URL, book, etc.)
    difficulty: Optional[CardDifficulty] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class Translation:
    """Translation of a sentence"""
    # Non-default fields must come first
    text: str
    
    # Fields with defaults
    target_language: str = "en"
    confidence: float = 1.0  # 0-1
    provider: str = "unknown"
    
@dataclass
class WordBreakdown:
    """Word-by-word analysis"""
    words: List[Word]
    
@dataclass
class AudioFile:
    """Audio recording of sentence"""
    # Non-default fields must come first
    filename: str
    format: AudioFormat
    
    # Fields with defaults
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    duration_seconds: Optional[float] = None
    url: Optional[str] = None  # For cloud storage
    provider: str = "unknown"

@dataclass
class GrammarNote:
    """Grammar explanation for the sentence"""
    # Non-default fields must come first
    title: str
    explanation: str
    
    # Fields with defaults
    examples: List[str] = field(default_factory=list)

@dataclass
class FlashCard:
    """Complete flashcard with all components"""
    # Non-default fields must come first
    sentence: Sentence
    translation: Translation
    word_breakdown: WordBreakdown
    
    # Fields with defaults
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    audio: Optional[AudioFile] = None
    grammar_notes: List[GrammarNote] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_anki_fields(self) -> dict:
        """Convert to Anki card format"""
        return {
            "French": self.sentence.text,
            "English": self.translation.text,
            "WordBreakdown": self._format_word_breakdown(),
            "Audio": f"[sound:{self.audio.filename}]" if self.audio else "",
            "GrammarNotes": self._format_grammar_notes(),
            "Tags": " ".join(self.tags)
        }
    
    def _format_word_breakdown(self) -> str:
        lines = []
        for word in self.word_breakdown.words:
            lines.append(f"<b>{word.text}</b> ({word.pos}): {word.definition}")
        return "<br>".join(lines)
    
    def _format_grammar_notes(self) -> str:
        if not self.grammar_notes:
            return ""
        return "<br>".join(f"• {note.explanation}" for note in self.grammar_notes)

@dataclass
class Deck:
    """Collection of flashcards"""
    # Non-default fields must come first
    name: str
    
    # Fields with defaults
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: Optional[str] = None
    cards: List[FlashCard] = field(default_factory=list)
    language_pair: tuple[str, str] = ("fr", "en")
    created_at: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)