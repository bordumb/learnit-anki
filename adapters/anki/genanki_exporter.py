# adapters/anki/genanki_exporter.py
import genanki
import hashlib
from pathlib import Path
from typing import List, Optional
from core.domain.interfaces import DeckExporter
from core.domain.models import Deck, FlashCard

class GenankiExporter(DeckExporter):
    """
    Adapter for exporting decks to Anki's .apkg format using genanki library.
    This adapter converts our domain models into genanki's format and
    handles the creation of proper Anki card templates with styling.
    """
    
    # Class-level constants for model IDs (must be unique and stable)
    # These are generated once and should not change
    DEFAULT_MODEL_ID = 1891667001
    DEFAULT_DECK_ID_SALT = "french-flashcard-generator"
    
    def __init__(self):
        self._card_model = self._create_card_model()
    
    def _create_card_model(self) -> genanki.Model:
        """
        Create the Anki card template (note type).
        This defines:
        - What fields each card has
        - How the front/back are rendered (HTML templates)
        - CSS styling for the cards
        """
        return genanki.Model(
            model_id=self.DEFAULT_MODEL_ID,
            name='French Language Card (Enhanced)',
            fields=[
                {'name': 'French'},           # Front: The sentence in French
                {'name': 'English'},          # Back: English translation
                {'name': 'WordBreakdown'},    # Back: Word-by-word definitions
                {'name': 'Audio'},            # Front/Back: Audio pronunciation
                {'name': 'GrammarNotes'},     # Back: Grammar explanations
                {'name': 'Tags'},             # Metadata: Tags for organization
                {'name': 'SentenceId'},       # Hidden: For tracking/updates
            ],
            templates=[
                {
                    'name': 'Card 1',
                    'qfmt': self._get_front_template(),  # Question (front) format
                    'afmt': self._get_back_template(),   # Answer (back) format
                },
            ],
            css=self._get_card_styles()
        )
    
    def _get_front_template(self) -> str:
        """HTML template for the front of the card"""
        return '''
        <div class="card-container">
            <div class="french-text">
                {{French}}
            </div>
            
            <div class="audio-container">
                {{Audio}}
            </div>
            
            <div class="hint">
                💡 Tap to reveal translation
            </div>
        </div>
        '''
    
    def _get_back_template(self) -> str:
        """HTML template for the back of the card"""
        return '''
        {{FrontSide}}
        
        <hr class="divider">
        
        <div class="card-container">
            <div class="english-text">
                {{English}}
            </div>
            
            {{#WordBreakdown}}
            <div class="breakdown-section">
                <div class="section-title">📚 Word Breakdown</div>
                <div class="breakdown-content">
                    {{WordBreakdown}}
                </div>
            </div>
            {{/WordBreakdown}}
            
            {{#GrammarNotes}}
            <div class="grammar-section">
                <div class="section-title">✏️ Grammar Notes</div>
                <div class="grammar-content">
                    {{GrammarNotes}}
                </div>
            </div>
            {{/GrammarNotes}}
        </div>
        '''
    
    def _get_card_styles(self) -> str:
        """CSS styling for the cards"""
        return '''
        /* Base card styling */
        .card {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 
                         'Helvetica Neue', Arial, sans-serif;
            font-size: 18px;
            line-height: 1.6;
            color: #2c3e50;
            background: #ffffff;
            padding: 20px;
            max-width: 600px;
            margin: 0 auto;
        }
        
        .card-container {
            text-align: center;
        }
        
        /* Header with language label */
        .card-header {
            margin-bottom: 15px;
        }
        
        .language-label {
            display: inline-block;
            padding: 6px 12px;
            background: #f8f9fa;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
            color: #6c757d;
        }
        
        /* Main text styling */
        .french-text {
            font-size: 28px;
            font-weight: 600;
            color: #2c3e50;
            margin: 25px 0;
            line-height: 1.4;
        }
        
        .english-text {
            font-size: 22px;
            font-weight: 500;
            color: #27ae60;
            margin: 20px 0;
            line-height: 1.4;
        }
        
        /* Audio player */
        .audio-container {
            margin: 20px 0;
        }
        
        /* Hint text on front */
        .hint {
            font-size: 14px;
            color: #95a5a6;
            margin-top: 30px;
            font-style: italic;
        }
        
        /* Divider between front and back */
        .divider {
            margin: 30px 0;
            border: none;
            border-top: 2px solid #ecf0f1;
        }
        
        /* Word breakdown section */
        .breakdown-section {
            margin-top: 30px;
            text-align: left;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 12px;
        }
        
        .section-title {
            font-size: 16px;
            font-weight: 700;
            color: #495057;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .breakdown-content {
            font-size: 15px;
            line-height: 1.8;
        }
        
        .breakdown-content b {
            color: #3498db;
            font-weight: 600;
        }

        /* --- Style for the new French definition --- */
        .definition-fr {
            font-style: italic;
            color: #555;
            padding-left: 15px;
            font-size: 0.95em;
        }
        /* --- End of new style --- */
        
        /* Grammar notes section */
        .grammar-section {
            margin-top: 20px;
            text-align: left;
            background: #fff9e6;
            padding: 20px;
            border-radius: 12px;
            border-left: 4px solid #f39c12;
        }
        
        .grammar-content {
            font-size: 15px;
            line-height: 1.8;
            color: #7f6d00;
        }
        
        /* Mobile responsiveness */
        @media (max-width: 600px) {
            .card {
                padding: 15px;
                font-size: 16px;
            }
            
            .french-text {
                font-size: 24px;
            }
            
            .english-text {
                font-size: 20px;
            }
        }
        
        /* Dark mode support (Anki 2.1.50+) */
        .nightMode .card {
            background: #1e1e1e;
            color: #e0e0e0;
        }
        
        .nightMode .french-text {
            color: #ffffff;
        }
        
        .nightMode .english-text {
            color: #4caf50;
        }
        
        .nightMode .breakdown-section {
            background: #2d2d2d;
        }

        .nightMode .definition-fr {
            color: #bbb;
        }
        
        .nightMode .grammar-section {
            background: #3d3520;
            border-left-color: #ffa726;
        }
        
        .nightMode .language-label {
            background: #2d2d2d;
            color: #b0b0b0;
        }
        '''
    
    async def export_deck(
        self, 
        deck: Deck, 
        output_path: str
    ) -> str:
        """
        Export a Deck to .apkg format.
        
        Args:
            deck: The Deck domain model to export
            output_path: Where to save the .apkg file
            
        Returns:
            The full path to the created .apkg file
        """
        # Generate a stable deck ID based on deck name
        deck_id = self._generate_deck_id(deck.name)
        
        # Create genanki deck
        anki_deck = genanki.Deck(
            deck_id=deck_id,
            name=deck.name
        )
        
        # Convert each card and add to deck
        media_files = []
        for card in deck.cards:
            note = self._convert_card_to_note(card)
            anki_deck.add_note(note)
            
            # Collect media files (audio)
            if card.audio and card.audio.filename:
                media_files.append(card.audio.filename)
        
        # Create package with media
        package = genanki.Package(anki_deck)
        
        # Add media files if they exist
        if media_files:
            package.media_files = self._resolve_media_paths(media_files)
        
        # Ensure output directory exists
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write .apkg file
        package.write_to_file(str(output_file))
        
        return str(output_file.absolute())
    
    def _convert_card_to_note(self, card: FlashCard) -> genanki.Note:
        """
        Convert a FlashCard domain model to a genanki Note.
        Args:
            card: The FlashCard to convert
            
        Returns:
            A genanki.Note instance ready to be added to a deck
        """
        # Format word breakdown as HTML
        word_breakdown_html = self._format_word_breakdown(card)
        
        # Format grammar notes as HTML
        grammar_notes_html = self._format_grammar_notes(card)
        
        # Format audio field
        audio_field = self._format_audio_field(card)
        
        # Format tags
        tags_str = " ".join(card.tags) if card.tags else ""
        
        # Create note with all fields
        note = genanki.Note(
            model=self._card_model,
            fields=[
                card.sentence.text,                    # French
                card.translation.text,                 # English
                word_breakdown_html,                   # WordBreakdown
                audio_field,                           # Audio
                grammar_notes_html,                    # GrammarNotes
                tags_str,                              # Tags
                card.id,                               # SentenceId (hidden)
            ],
            tags=card.tags if card.tags else []
        )
        
        return note
    
    def _format_word_breakdown(self, card: FlashCard) -> str:
        """Format word breakdown as HTML"""
        if not card.word_breakdown or not card.word_breakdown.words:
            return ""
        
        lines = []
        for word in card.word_breakdown.words:
            # Format: <b>word</b> (pos): definition
            line = f"<b>{word.text}</b> <span class='pos'>({word.pos})</span>: {word.definition}"
            lines.append(line)
            
            # --- This is the new part ---
            # Add the French definition if it exists
            if word.definition_fr:
                fr_line = f"<div class='definition-fr'>Fr: {word.definition_fr}</div>"
                lines.append(fr_line)
            # --- End of new part ---
        
        return "<br>".join(lines)
    
    def _format_grammar_notes(self, card: FlashCard) -> str:
        """Format grammar notes as HTML"""
        if not card.grammar_notes:
            return ""
        
        lines = []
        for note in card.grammar_notes:
            # Format with bullet points
            lines.append(f"• <strong>{note.title}:</strong> {note.explanation}")
            
            # Add examples if present
            if note.examples:
                for example in note.examples:
                    lines.append(f"  <em>Example: {example}</em>")
        
        return "<br>".join(lines)
    
    def _format_audio_field(self, card: FlashCard) -> str:
        """
        Format audio field for Anki.
        Anki expects: [sound:filename.mp3]
        """
        if not card.audio or not card.audio.filename:
            return ""
        
        return f"[sound:{card.audio.filename}]"
    
    def _generate_deck_id(self, deck_name: str) -> int:
        """
        Generate a stable deck ID from the deck name.
        Uses hash to ensure:
        1. Same deck name = same ID (for updates)
        2. Different deck names = different IDs
        3. IDs are valid positive integers for Anki
        """
        # Create hash of deck name + salt
        hash_input = f"{deck_name}{self.DEFAULT_DECK_ID_SALT}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()
        
        # Convert first 8 hex chars to int (ensures 32-bit positive int)
        deck_id = int(hash_value[:8], 16)
        
        # Ensure it's positive and within Anki's range
        return deck_id & 0x7FFFFFFF
    
    def _resolve_media_paths(self, filenames: List[str]) -> List[str]:
        """
        Resolve media file paths.
        This assumes audio files are stored in a known location.
        In production, this would interface with the StorageService.
        """
        # For now, assume files are in ./storage/audio/
        # In production, you'd get these from StorageService
        base_path = Path("./storage/audio")
        
        resolved_paths = []
        for filename in filenames:
            file_path = base_path / filename
            if file_path.exists():
                resolved_paths.append(str(file_path))
            else:
                # Log warning but don't fail
                print(f"⚠️  Warning: Audio file not found: {filename}")
        
        return resolved_paths


class GenankiExporterWithProgressTracking(GenankiExporter):
    """
    Enhanced version with progress tracking for large decks.
    
    Useful for API/background job scenarios where you want to
    report progress to users.
    """
    
    def __init__(self, progress_callback: Optional[callable] = None):
        super().__init__()
        self.progress_callback = progress_callback
    
    async def export_deck(
        self, 
        deck: Deck, 
        output_path: str
    ) -> str:
        """Export with progress updates"""
        
        total_cards = len(deck.cards)
        
        # Generate deck ID
        deck_id = self._generate_deck_id(deck.name)
        anki_deck = genanki.Deck(deck_id=deck_id, name=deck.name)
        
        # Process cards with progress tracking
        media_files = []
        for i, card in enumerate(deck.cards):
            note = self._convert_card_to_note(card)
            anki_deck.add_note(note)
            
            if card.audio and card.audio.filename:
                media_files.append(card.audio.filename)
            
            # Report progress
            if self.progress_callback:
                progress = (i + 1) / total_cards * 100
                self.progress_callback(progress, f"Processing card {i+1}/{total_cards}")
        
        # Create package
        if self.progress_callback:
            self.progress_callback(95, "Creating .apkg file...")
        
        package = genanki.Package(anki_deck)
        if media_files:
            package.media_files = self._resolve_media_paths(media_files)
        
        # Write file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        package.write_to_file(str(output_file))
        
        if self.progress_callback:
            self.progress_callback(100, "Complete!")
        
        return str(output_file.absolute())


# Convenience function for direct usage
def export_cards_to_anki(
    cards: List[FlashCard],
    deck_name: str,
    output_path: str
) -> str:
    """
    Quick utility function to export cards without using the full architecture.
    Useful for simple scripts or testing.
    
    Args:
        cards: List of FlashCard objects
        deck_name: Name for the Anki deck
        output_path: Where to save the .apkg file
        
    Returns:
        Path to the created .apkg file
    """
    from core.domain.models import Deck
    import asyncio
    
    # Create a deck from the cards
    deck = Deck(name=deck_name, cards=cards)
    
    # Export
    exporter = GenankiExporter()
    return asyncio.run(exporter.export_deck(deck, output_path))


# Example usage
# if __name__ == "__main__":
#     """
#     Example of how to use the exporter directly
#     """
#     from core.domain.models import (
#         FlashCard, Sentence, Translation, WordBreakdown, 
#         Word, AudioFile, AudioFormat, GrammarNote
#     )
    
#     # Create a sample card
#     card = FlashCard(
#         sentence=Sentence(text="Je mange une pomme."),
#         translation=Translation(text="I eat an apple."),
#         word_breakdown=WordBreakdown(words=[
#             Word(text="Je", lemma="je", pos="pronoun", definition="I"),
#             Word(text="mange", lemma="manger", pos="verb", definition="eat"),
#             Word(text="une", lemma="un", pos="article", definition="a/an"),
#             Word(text="pomme", lemma="pomme", pos="noun", definition="apple"),
#         ]),
#         audio=AudioFile(
#             filename="je_mmange_une_pomme.mp3",
#             format=AudioFormat.MP3,
#             provider="google-tts"
#         ),
#         grammar_notes=[
#             GrammarNote(
#                 title="Present tense",
#                 explanation="'mange' is the present tense conjugation of 'manger' for 'je'",
#                 examples=["Tu manges", "Il mange"]
#             )
#         ],
#         tags=["food", "beginner", "verbs"]
#     )
    
#     # Export single card
#     output = export_cards_to_anki(
#         cards=[card],
#         deck_name="French Practice",
#         output_path="./output/french_practice.apkg"
#     )
    
#     print(f"✅ Deck created: {output}")