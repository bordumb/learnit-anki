# core/use_cases/generate_deck.py
import asyncio
from typing import List, Optional, Tuple
from core.domain.models import Deck, FlashCard
from core.domain.interfaces import StorageService, DeckExporter
from .generate_card import GenerateCardUseCase # Assuming GenerateCardUseCase is in the same directory or adjust path

class GenerateDeckUseCase:
    """
    Single Responsibility: Generate a complete deck of flashcards
    from a list of sentences, handling language specification.
    """

    def __init__(
        self,
        card_generator: GenerateCardUseCase,
        exporter: DeckExporter,
        storage: StorageService, # Keep storage if needed directly, though card_generator handles audio saving
        default_source_lang: str,
        default_target_lang: str
    ):
        """
        Initializes the use case.

        Args:
            card_generator: The use case for generating individual cards.
            exporter: The service for exporting the final deck.
            storage: Storage service (potentially for deck metadata or future use).
            default_source_lang: Default source language code.
            default_target_lang: Default target language code.
        """
        self.card_generator = card_generator
        self.exporter = exporter
        self.storage = storage
        self.default_source_lang = default_source_lang
        self.default_target_lang = default_target_lang

    async def execute(
        self,
        sentences: List[str],
        deck_name: str,
        output_path: str,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
        include_audio: bool = False, # Keep default as False for CLI batch safety
        include_grammar: bool = True
    ) -> str:
        """
        Generates a complete deck for a specific language pair.

        Args:
            sentences: A list of sentences in the source language.
            deck_name: The name for the Anki deck.
            output_path: The file path to save the .apkg file.
            source_lang: The source language code (e.g., 'fr'). Defaults if None.
            target_lang: The target language code (e.g., 'en'). Defaults if None.
            include_audio: Whether to generate audio (can be slow).
            include_grammar: Whether to generate grammar notes.

        Returns:
            The absolute path to the generated .apkg file.
        """
        # Determine languages to use for this deck
        src_lang = source_lang or self.default_source_lang
        tgt_lang = target_lang or self.default_target_lang
        lang_pair: Tuple[str, str] = (src_lang, tgt_lang)

        print(f"🔄 Generating deck '{deck_name}' for {src_lang} -> {tgt_lang}...")

        cards: List[FlashCard] = []

        # Create tasks for generating each card in parallel
        tasks = []
        for i, sentence_text in enumerate(sentences):
            print(f"  [{i+1}/{len(sentences)}] Queuing card generation for: '{sentence_text[:30]}...'")
            tasks.append(
                self.card_generator.execute(
                    sentence_text=sentence_text,
                    source_lang=src_lang, # Pass determined languages
                    target_lang=tgt_lang,
                    include_audio=include_audio,
                    include_grammar=include_grammar
                )
            )

        # Wait for all card generation tasks to complete
        generated_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results, handling potential errors
        successful_cards = 0
        for i, result in enumerate(generated_results):
            if isinstance(result, FlashCard):
                cards.append(result)
                successful_cards += 1
            elif isinstance(result, Exception):
                print(f"⚠️ Skipping card for sentence '{sentences[i][:50]}...': Error -> {result}")
            else:
                print(f"⚠️ Skipping card for sentence '{sentences[i][:50]}...': Unknown result type -> {type(result)}")

        print(f"📊 Generated {successful_cards} cards successfully out of {len(sentences)} sentences.")

        if not cards:
             print("❌ No cards were generated successfully. Aborting deck export.")
             # Consider raising an error or returning a specific indicator
             return f"Failed: No cards generated for deck '{deck_name}'."

        # Create the deck domain model with the correct language pair
        deck = Deck(
            name=deck_name,
            cards=cards,
            language_pair=lang_pair # Set the language pair
        )

        # Export the deck to an .apkg file
        print(f"📦 Exporting deck '{deck_name}' with {len(cards)} cards...")
        try:
            file_path = await self.exporter.export_deck(
                deck=deck,
                output_path=output_path
            )
            print(f"✅ Deck export complete: {file_path}")
            return file_path
        except Exception as e:
            print(f"❌ Deck export failed: {e}")
            # Propagate or handle the export error appropriately
            raise


# Example (Conceptual - would need runner context)
# async def main():
#     # Assuming container setup as before...
#     container = get_container()
#     deck_generator = container.create_deck_generator()
#     sentences = ["Bonjour.", "Comment ça va?", "Je vais bien."]
#     output = await deck_generator.execute(
#         sentences=sentences,
#         deck_name="German Test",
#         output_path="./output/german_test.apkg",
#         source_lang="de", # Override default
#         target_lang="en",
#         include_audio=False
#     )
#     print(output)
#
# if __name__ == "__main__":
#     asyncio.run(main())
