# core/use_cases/generate_card.py
import logging
from typing import Optional
from ..domain.models import Sentence, FlashCard, AudioFile, GrammarNote, Translation, WordBreakdown
from ..domain.interfaces import (
    TranslationService, TranslationError, DictionaryService, AudioService, GrammarService, StorageService
)

class GenerateCardUseCase:
    """
    Single Responsibility: Generate one complete flashcard.

    Orchestrates adapters based on provided or default languages.
    """

    def __init__(
        self,
        translation_service: Optional[TranslationService],
        dictionary_service: Optional[DictionaryService],
        audio_service: AudioService,
        storage_service: StorageService,
        grammar_service: Optional[GrammarService],
        default_source_lang: str,
        default_target_lang: str
    ):
        """
        Initializes the use case with necessary services and default languages.

        Args:
            translation_service: Service for translating text.
            dictionary_service: Service for word analysis.
            audio_service: Service for generating audio.
            storage_service: Service for saving audio files.
            grammar_service: Optional service for grammar explanations.
            default_source_lang: Default source language code (e.g., 'fr').
            default_target_lang: Default target language code (e.g., 'en').
        """
        self.translator = translation_service
        self.dictionary = dictionary_service
        self.audio = audio_service
        self.storage = storage_service
        self.grammar = grammar_service
        self.default_source_lang = default_source_lang
        self.default_target_lang = default_target_lang

    async def execute(
        self,
        sentence_text: str,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
        include_audio: bool = True,
        include_grammar: bool = True,
        source: Optional[str] = None,
        manual_translation: Optional[str] = None,
    ) -> FlashCard:
        """
        Generates a complete flashcard for a given sentence.

        Uses provided languages or falls back to defaults set during initialization.

        Args:
            sentence_text: The sentence in the source language.
            source_lang: The source language code (e.g., 'fr', 'de'). Defaults if None.
            target_lang: The target language code (e.g., 'en', 'es'). Defaults if None.
            include_audio: Whether to generate and save audio.
            include_grammar: Whether to generate grammar notes.
            source: Optional URL or label for the original material.
            manual_translation: Approved translation to export without cloud text enrichment.

        Returns:
            A populated FlashCard object.

        Raises:
            ValueError: If translation or dictionary analysis fails.
            Exception: Propagates exceptions from underlying services.
        """
        # Determine languages to use
        src_lang = source_lang or self.default_source_lang
        tgt_lang = target_lang or self.default_target_lang

        # Create sentence object with the correct language
        sentence = Sentence(text=sentence_text, language=src_lang, source=source)

        if manual_translation is not None:
            approved = manual_translation.strip()
            if not approved:
                raise TranslationError("Enter a translation before creating the card.")
            translation = Translation(text=approved, target_language=tgt_lang, provider="manual")
            word_breakdown = WordBreakdown(words=[])
        else:
            if self.translator is None or self.dictionary is None:
                raise TranslationError("Configure a translation provider or enter a translation manually.")
            translation = await self.translator.translate(
                text=sentence_text, source_lang=src_lang, target_lang=tgt_lang,
            )
            if translation is None or not translation.text.strip():
                raise TranslationError("Translation failed. Check the configured translation provider.")
            if not translation.target_language:
                translation.target_language = tgt_lang

            word_breakdown = await self.dictionary.analyze_sentence(
                sentence=sentence_text, source_lang=src_lang, target_lang=tgt_lang,
            )
            if word_breakdown is None:
                raise ValueError("Word breakdown analysis failed.")

        # 3. Generate and Save Audio (if requested)
        audio_model: Optional[AudioFile] = None
        if include_audio:
            try:
                generated_audio, data = await self.audio.generate_audio(sentence_text, src_lang)
                if generated_audio and data:
                    location = await self.storage.save_audio(generated_audio, data)
                    if location:
                        if location.startswith(("http://", "https://")):
                            generated_audio.url = location
                        generated_audio.language = src_lang
                        audio_model = generated_audio
            except Exception:
                logging.getLogger(__name__).warning("Pronunciation audio failed.", exc_info=True)

            if audio_model is None:
                logging.getLogger(__name__).warning("Saving the card without pronunciation audio.")

        # 4. Get Grammar Notes (if requested and service available)
        grammar_notes: list[GrammarNote] = []
        if manual_translation is None and include_grammar and self.grammar:
            grammar_notes = await self.grammar.explain_grammar(
                sentence=sentence_text,
                language=src_lang # Explain grammar based on source language
            )

        # 5. Assemble FlashCard
        card = FlashCard(
            sentence=sentence,
            translation=translation,
            word_breakdown=word_breakdown,
            audio=audio_model, # Will be None if audio failed or was skipped
            grammar_notes=grammar_notes
            # Tags could potentially be added based on language, topic, etc. later
        )

        return card
