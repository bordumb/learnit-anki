# core/use_cases/generate_deck.py
import asyncio
from typing import List
from core.domain.models import Deck, FlashCard
from core.domain.interfaces import StorageService, DeckExporter
from .generate_card import GenerateCardUseCase

class GenerateDeckUseCase:
    """
    Single Responsibility: Generate a complete deck of flashcards
    from a list of sentences.
    """
    
    def __init__(
        self,
        card_generator: GenerateCardUseCase,
        exporter: DeckExporter,
        storage: StorageService
    ):
        self.card_generator = card_generator
        self.exporter = exporter
        self.storage = storage # Used for saving audio
    
    async def execute(
        self, 
        sentences: List[str],
        deck_name: str,
        output_path: str,
        include_audio: bool = False, # Disable audio by default for CLI batch
        include_grammar: bool = True
    ) -> str:
        """
        Generate a complete deck.
        
        Args:
            sentences: A list of French sentences.
            deck_name: The name for the .apkg deck.
            output_path: The file path to save the .apkg.
            include_audio: Whether to generate audio (slow).
            include_grammar: Whether to generate grammar notes.
            
        Returns:
            The absolute path to the generated .apkg file.
        """
        
        cards: List[FlashCard] = []
        
        # We can run card generation in parallel
        tasks = []
        for sentence in sentences:
            tasks.append(
                self.card_generator.execute(
                    sentence_text=sentence,
                    include_audio=include_audio,
                    include_grammar=include_grammar
                )
            )
        
        # Wait for all cards to be generated
        # Note: This will make many parallel API calls
        generated_cards = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(generated_cards):
            if isinstance(result, Exception):
                print(f"⚠️  Skipping card for '{sentences[i]}': {result}")
            else:
                cards.append(result)
        
        # Create the deck domain model
        deck = Deck(
            name=deck_name,
            cards=cards
        )
        
        # Export the deck to an .apkg file
        # The exporter will handle saving media files if audio was generated
        file_path = await self.exporter.export_deck(
            deck=deck,
            output_path=output_path
        )
        
        return file_path