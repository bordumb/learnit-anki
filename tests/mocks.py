# tests/mocks.py
from typing import Optional, List, Tuple, Any
from core.domain.interfaces import (
    TranslationService, DictionaryService, AudioService, GrammarService,
    StorageService, DeckExporter, CacheService, LanguageCode, LanguagePair
)
from core.domain.models import (
    Translation, Word, WordBreakdown, AudioFile, AudioFormat, GrammarNote,
    Sentence, Deck, CardDifficulty
)
import hashlib
import time

# --- Mock Implementations ---

class MockTranslationService(TranslationService):
    """Simulates translation, returning predefined text or a default."""
    async def translate(
        self,
        text: str,
        source_lang: LanguageCode,
        target_lang: LanguageCode
    ) -> Optional[Translation]:
        translations = {
            "fr": {
                "en": {
                    "Je mange une pomme.": "I eat an apple.",
                    "Bonjour": "Hello",
                    "Comment allez-vous ?": "How are you?",
                }
            },
            "de": {
                "en": {
                    "Ich esse einen Apfel.": "I eat an apple.",
                    "Hallo": "Hello",
                }
            }
        }
        # Look up based on languages and text
        translated_text = translations.get(source_lang, {}).get(target_lang, {}).get(text)

        if translated_text:
            return Translation(
                text=translated_text,
                target_language=target_lang,
                provider="mock",
                confidence=0.95 # Simulate some confidence
            )
        else:
            # Fallback for unknown text
            return Translation(
                text=f"Mock translation of '{text}' from {source_lang} to {target_lang}",
                target_language=target_lang,
                provider="mock-fallback",
                confidence=0.5
            )

class MockDictionaryService(DictionaryService):
    """Simulates dictionary lookups and sentence analysis."""
    async def lookup_word(
        self,
        word: str,
        source_lang: LanguageCode,
        target_lang: LanguageCode
    ) -> Optional[Word]:
         # Simulate failure for a specific word for testing
        if word.lower() == "failme":
            return None

        return Word(
            text=word,
            lemma=word.lower(), # Simple lemma mock
            pos="noun",
            definition=f"Mock definition of '{word}' ({target_lang})",
            definition_native=f"Mock native def of '{word}' ({source_lang})"
        )

    async def analyze_sentence(
        self,
        sentence: str,
        source_lang: LanguageCode,
        target_lang: LanguageCode
    ) -> Optional[WordBreakdown]:
         # Simulate failure for a specific sentence for testing
        if "fail this sentence" in sentence.lower():
            return None

        # Simple split, ignoring punctuation
        words_text = ''.join(c for c in sentence if c.isalnum() or c.isspace()).split()

        word_objects = []
        for w_text in words_text:
             word_obj = await self.lookup_word(w_text, source_lang, target_lang)
             if word_obj: # Handle potential lookup failure
                 word_objects.append(word_obj)

        if not word_objects: # Return None if no words were analyzed (e.g., all failed)
             return None

        return WordBreakdown(words=word_objects)

class MockAudioService(AudioService):
    """Simulates audio generation, optionally can be disabled."""
    def __init__(self, disable: bool = False, simulate_failure: bool = False):
        self.disable = disable
        self.simulate_failure = simulate_failure

    async def generate_audio(
        self,
        text: str,
        language: LanguageCode, # Base language code e.g. 'fr'
        format: AudioFormat = AudioFormat.MP3
    ) -> Tuple[Optional[AudioFile], Optional[bytes]]:
        if self.disable:
            # Service explicitly disabled
            return (None, None)

        if self.simulate_failure:
            # Simulate an API or processing error
            print(f"MOCK AUDIO: Simulating failure for '{text}' ({language})")
            return (None, None)

        # Generate a unique filename based on text and language
        text_hash = hashlib.md5(f"{language}-{text}".encode()).hexdigest()
        filename = f"{language}_{text_hash[:8]}.{format.value}"

        audio_model = AudioFile(
            filename=filename,
            format=format,
            provider="mock-audio",
            language=language # Store the language
        )
        # Simulate some audio data (e.g., just the text itself as bytes)
        mock_data = f"Audio data for '{text}' ({language})".encode()

        print(f"MOCK AUDIO: Generated '{filename}' for '{text}' ({language})")
        return (audio_model, mock_data)

class MockGrammarService(GrammarService):
    """Simulates grammar explanations."""
    async def explain_grammar(
        self,
        sentence: str,
        language: LanguageCode
    ) -> List[GrammarNote]:
        # Simulate simple grammar notes based on keywords
        notes = []
        if "mange" in sentence and language == "fr":
            notes.append(GrammarNote(
                title="Verb: Manger (Present Tense)",
                explanation="'mange' is the first-person singular present indicative of 'manger' (to eat).",
                examples=["Je mange une pomme."]
            ))
        if "Ich esse" in sentence and language == "de":
             notes.append(GrammarNote(
                title="Verb: Essen (Present Tense)",
                explanation="'esse' is the first-person singular present indicative of 'essen' (to eat).",
                examples=["Ich esse einen Apfel."]
            ))

        if not notes:
             # Default note if no keywords match
              notes.append(GrammarNote(
                title=f"Basic Grammar ({language.upper()})",
                explanation=f"This mock sentence uses basic {language} structure.",
                examples=[]
            ))
        return notes

class MockStorageService(StorageService):
    """Simulates file storage (in memory)."""
    def __init__(self):
        self.storage = {} # filename: bytes

    async def save_audio(self, audio: AudioFile, data: bytes) -> Optional[str]:
        if not audio or not audio.filename or not data:
            return None
        self.storage[audio.filename] = data
        print(f"MOCK STORAGE: Saved '{audio.filename}' ({len(data)} bytes)")
        # Simulate returning a path/URL
        return f"/mock/storage/audio/{audio.filename}"

    async def get_audio(self, filename: str) -> Optional[bytes]:
         if not filename:
             return None
         data = self.storage.get(filename)
         if data:
              print(f"MOCK STORAGE: Retrieved '{filename}' ({len(data)} bytes)")
         else:
              print(f"MOCK STORAGE: File not found '{filename}'")
         return data

    async def delete_audio(self, filename: str) -> bool:
        if not filename:
            return False
        if filename in self.storage:
            del self.storage[filename]
            print(f"MOCK STORAGE: Deleted '{filename}'")
            return True
        else:
            print(f"MOCK STORAGE: Delete failed - '{filename}' not found")
            return True # Per interface, return True if not found

class MockDeckExporter(DeckExporter):
    """Simulates exporting a deck."""
    async def export_deck(
        self,
        deck: Deck,
        output_path: str
    ) -> Optional[str]:
        if not deck or not deck.cards:
             print("MOCK EXPORTER: Cannot export empty deck.")
             return None
        # Simulate creating the file
        print(f"MOCK EXPORTER: Simulating export of deck '{deck.name}' ({len(deck.cards)} cards) for {deck.language_pair} to '{output_path}'")
        # In a real scenario, you'd create the directory if needed
        # Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        return output_path # Return the intended path

class MockCacheService(CacheService):
    """Simulates caching (in memory)."""
    def __init__(self):
        self.cache = {} # key: (value, expiry_time)

    async def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            value, expiry = self.cache[key]
            if expiry is None or time.time() < expiry:
                print(f"MOCK CACHE: Cache hit for '{key}'")
                return value
            else:
                # Expired
                print(f"MOCK CACHE: Cache expired for '{key}'")
                del self.cache[key]
                return None
        else:
             print(f"MOCK CACHE: Cache miss for '{key}'")
             return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        expiry = (time.time() + ttl) if ttl is not None else None
        self.cache[key] = (value, expiry)
        ttl_str = f"with TTL {ttl}s" if ttl else "indefinitely"
        print(f"MOCK CACHE: Set '{key}' {ttl_str}")

    async def delete(self, key: str) -> bool:
        if key in self.cache:
            del self.cache[key]
            print(f"MOCK CACHE: Deleted '{key}'")
            return True
        else:
             print(f"MOCK CACHE: Delete failed - '{key}' not found")
             return False

# --- Disabled Service for DI ---

class DisabledAudioService(AudioService):
    """A service implementation that does nothing, for when audio is disabled."""
    async def generate_audio(
        self,
        text: str,
        language: LanguageCode,
        format: AudioFormat = AudioFormat.MP3
    ) -> Tuple[Optional[AudioFile], Optional[bytes]]:
        logger.debug("Audio generation is disabled. Skipping.")
        return (None, None)
