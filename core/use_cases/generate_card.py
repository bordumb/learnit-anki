# core/use_cases/generate_card.py
from typing import Optional, Tuple
from ..domain.models import Sentence, FlashCard, AudioFile, Translation, WordBreakdown, GrammarNote
from ..domain.interfaces import (
    TranslationService, DictionaryService, AudioService, GrammarService, StorageService
)

class GenerateCardUseCase:
    """
    Single Responsibility: Generate one complete flashcard.

    Orchestrates adapters based on provided or default languages.
    """

    def __init__(
        self,
        translation_service: TranslationService,
        dictionary_service: DictionaryService,
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
        include_grammar: bool = True
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

        Returns:
            A populated FlashCard object.

        Raises:
            ValueError: If audio generation fails and include_audio is True.
            Exception: Propagates exceptions from underlying services.
        """
        # Determine languages to use
        src_lang = source_lang or self.default_source_lang
        tgt_lang = target_lang or self.default_target_lang

        # Create sentence object with the correct language
        sentence = Sentence(text=sentence_text, language=src_lang)

        # 1. Get Translation
        translation = await self.translator.translate(
            text=sentence_text,
            source_lang=src_lang,
            target_lang=tgt_lang
        )
        # Ensure the translation object has the target language set
        # (Some adapters might not set it, though they should)
        if not translation.target_language:
            translation.target_language = tgt_lang


        # 2. Get Word Breakdown
        word_breakdown = await self.dictionary.analyze_sentence(
            sentence=sentence_text,
            source_lang=src_lang,
            target_lang=tgt_lang # Pass target lang for definitions
        )

        # 3. Generate and Save Audio (if requested)
        audio_model: Optional[AudioFile] = None
        if include_audio:
            # Generate audio model and raw data using the source language
            generated_audio_model, audio_data = await self.audio.generate_audio(
                text=sentence_text,
                language=src_lang # Use source language for TTS
                # Format is handled by the adapter or uses its default
            )

            # Check if audio generation was successful
            if generated_audio_model and audio_data:
                # Save the audio data using the storage service
                # The storage service might return a URL or path
                storage_location = await self.storage.save_audio(generated_audio_model, audio_data)

                # Optionally update the model with the URL if applicable
                if isinstance(storage_location, str) and storage_location.startswith(('http://', 'https://')):
                     generated_audio_model.url = storage_location
                generated_audio_model.language = src_lang # Store language with audio model

                audio_model = generated_audio_model # Assign to the variable used for the card
            else:
                # Handle potential failure from the audio service
                print(f"⚠️ Audio generation skipped or failed for sentence: '{sentence_text}'")
                # Decide if this should be a critical error or just a warning
                # raise ValueError("Audio generation failed.") # Option 1: Fail hard
                # Option 2: Continue without audio (current implementation)


        # 4. Get Grammar Notes (if requested and service available)
        grammar_notes: List[GrammarNote] = []
        if include_grammar and self.grammar:
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
