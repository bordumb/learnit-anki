# tests/mocks.py
from core.domain.interfaces import TranslationService, DictionaryService, AudioService
from core.domain.models import Translation, Word, WordBreakdown, AudioFile, AudioFormat

class MockTranslationService(TranslationService):
    async def translate(self, text, source_lang, target_lang):
        # Simple mock translation
        translations = {
            "Je mange une pomme.": "I eat an apple.",
            "Bonjour": "Hello",
        }
        return Translation(
            text=translations.get(text, f"Translation of {text}"),
            target_language=target_lang,
            provider="mock"
        )

class MockDictionaryService(DictionaryService):
    async def lookup_word(self, word, source_lang, target_lang):
        return Word(
            text=word,
            lemma=word,
            pos="noun",
            definition=f"Definition of {word}"
        )
    
    async def analyze_sentence(self, sentence, source_lang, target_lang):
        words = sentence.replace(".", "").split()
        word_objects = [
            Word(text=w, lemma=w, pos="noun", definition=f"def:{w}")
            for w in words
        ]
        return WordBreakdown(words=word_objects)

class MockAudioService(AudioService):
    def __init__(self, disable: bool = False):
        self.disable = disable

    async def generate_audio(self, text, language, format=AudioFormat.MP3):
        if self.disable:
            return None # Don't generate audio
            
        return AudioFile(
            filename=f"{text[:10]}.mp3",
            format=format,
            provider="mock"
        )