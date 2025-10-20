# core/use_cases/generate_card.py
from typing import Optional
from ..domain.models import Sentence, FlashCard
from ..domain.interfaces import (
    TranslationService, DictionaryService, AudioService, GrammarService
)

class GenerateCardUseCase:
    """
    Single Responsibility: Generate one complete flashcard
    
    This is the core business logic - it orchestrates the adapters
    but doesn't know their implementations.
    """
    
    def __init__(
        self,
        translation_service: TranslationService,
        dictionary_service: DictionaryService,
        audio_service: AudioService,
        grammar_service: Optional[GrammarService] = None
    ):
        self.translator = translation_service
        self.dictionary = dictionary_service
        self.audio = audio_service
        self.grammar = grammar_service
    
    async def execute(
        self, 
        sentence_text: str,
        include_audio: bool = True,
        include_grammar: bool = True
    ) -> FlashCard:
        """
        Generate a complete flashcard from a sentence.
        
        This method is pure business logic - it can be tested
        without any real API calls by using mock adapters.
        """
        
        # Create sentence object
        sentence = Sentence(text=sentence_text, language="fr")
        
        # Get translation
        translation = await self.translator.translate(
            text=sentence_text,
            source_lang="fr",
            target_lang="en"
        )
        
        # Get word breakdown
        word_breakdown = await self.dictionary.analyze_sentence(
            sentence=sentence_text,
            source_lang="fr",
            target_lang="en"
        )
        
        # Generate audio (optional)
        audio = None
        if include_audio:
            audio = await self.audio.generate_audio(
                text=sentence_text,
                language="fr"
            )
        
        # Get grammar notes (optional)
        grammar_notes = []
        if include_grammar and self.grammar:
            grammar_notes = await self.grammar.explain_grammar(
                sentence=sentence_text,
                language="fr"
            )
        
        # Assemble card
        card = FlashCard(
            sentence=sentence,
            translation=translation,
            word_breakdown=word_breakdown,
            audio=audio,
            grammar_notes=grammar_notes
        )
        
        return card