# adapters/anki/genanki_exporter.py
import genanki
import hashlib
import logging
import uuid
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Set

from core.domain.interfaces import DeckExporter
from core.domain.models import Deck, FlashCard, LanguagePair, LanguageCode

# Configure logging
logger = logging.getLogger(__name__)

# --- Language Configuration ---
# Map language codes to human-readable names
LANGUAGE_NAMES: Dict[LanguageCode, str] = {
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "en": "English",
    "it": "Italian",
    "pt": "Portuguese",
    # Add more as needed
}

# --- Default/Fallback Values ---
DEFAULT_DECK_ID_SALT = "anki-card-generator-deck-salt"
DEFAULT_MODEL_ID_SALT = "anki-card-generator-model-salt"
DEFAULT_SOURCE_LANG_CODE = "src"
DEFAULT_TARGET_LANG_CODE = "tgt"
DEFAULT_SOURCE_LANG_NAME = "Source Language"
DEFAULT_TARGET_LANG_NAME = "Target Language"

class GenankiExporter(DeckExporter):
    """
    Adapter for exporting decks to Anki's .apkg format using genanki.

    Handles dynamic creation of Anki card models (Note Types) based on
    the language pair of the deck being exported.
    """
    def __init__(self, storage_path: str = "./storage/audio"):
        """
        Initializes the exporter.

        Args:
            storage_path: Base path where generated audio files are stored locally.
        """
        self._model_cache: Dict[LanguagePair, genanki.Model] = {}
        self.storage_path = Path(storage_path).resolve()
        logger.info(f"GenankiExporter initialized. Audio storage path: {self.storage_path}")

    def _generate_stable_id(self, base_string: str, salt: str) -> int:
        """
        Generates a stable, positive 31-bit integer ID from a string.
        Ensures the same input string always produces the same ID.
        """
        hash_input = f"{base_string}-{salt}"
        # Use sha256 for better collision resistance than md5, take first 8 hex chars
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:8]
        # Convert hex to int and ensure it fits in a signed 32-bit int, keeping it positive
        stable_id = int(hash_value, 16) & 0x7FFFFFFF
        # Ensure ID is not zero, as Anki might reserve 0
        return stable_id if stable_id != 0 else 1

    def _get_language_name(self, lang_code: LanguageCode, default: str) -> str:
        """Safely get the full language name from the code."""
        return LANGUAGE_NAMES.get(lang_code, default)

    def _get_or_create_card_model(self, lang_pair: LanguagePair) -> genanki.Model:
        """
        Creates or retrieves a cached genanki.Model for a specific language pair.

        Generates stable, unique model IDs based on the language pair.
        Dynamically sets field names (e.g., "German", "English").

        Args:
            lang_pair: A tuple (source_lang_code, target_lang_code).

        Returns:
            A genanki.Model instance for the given language pair.
        """
        if lang_pair in self._model_cache:
            return self._model_cache[lang_pair]

        source_lang_code, target_lang_code = lang_pair
        source_lang_name = self._get_language_name(source_lang_code, DEFAULT_SOURCE_LANG_NAME)
        target_lang_name = self._get_language_name(target_lang_code, DEFAULT_TARGET_LANG_NAME)

        # Generate a unique, stable model ID based on the language pair
        model_id_str = f"{source_lang_code}-{target_lang_code}"
        model_id = self._generate_stable_id(model_id_str, DEFAULT_MODEL_ID_SALT)

        model_name = f'Language Card ({source_lang_name} -> {target_lang_name})'
        logger.info(f"Creating new Anki model for {source_lang_name} -> {target_lang_name} (ID: {model_id})")

        # Define fields dynamically
        field_names = [
            source_lang_name,       # Field 0: Source language text (e.g., "German")
            target_lang_name,       # Field 1: Target language text (e.g., "English")
            "WordBreakdown",        # Field 2: Analysis of words
            "Audio",                # Field 3: Pronunciation
            "GrammarNotes",         # Field 4: Grammar explanations
            "Tags",                 # Field 5: Metadata tags
            "SentenceId",           # Field 6: Unique ID for the source sentence (often hidden)
            "SourceLangCode",       # Field 7: Hidden field for source language code
            "TargetLangCode",       # Field 8: Hidden field for target language code
        ]
        fields = [{'name': name} for name in field_names]

        # Define templates
        templates = [
            {
                'name': f'{source_lang_name} -> {target_lang_name}',
                'qfmt': self._get_front_template(source_lang_name, target_lang_name),
                'afmt': self._get_back_template(source_lang_name, target_lang_name),
            },
            # Optional: Add a reverse card template if desired
            # {
            #     'name': f'{target_lang_name} -> {source_lang_name}',
            #     'qfmt': self._get_front_template(target_lang_name, source_lang_name), # Swap languages
            #     'afmt': self._get_back_template(target_lang_name, source_lang_name), # Swap languages
            # },
        ]

        # Create the model
        model = genanki.Model(
            model_id=model_id,
            name=model_name,
            fields=fields,
            templates=templates,
            css=self._get_card_styles(),
            # sortf = 0 # Sort by the first field (Source Language Text)
        )

        self._model_cache[lang_pair] = model
        return model

    def _get_front_template(self, source_lang_name: str, target_lang_name: str) -> str:
        """HTML template for the front of the card."""
        # Uses standard Anki template syntax {{FieldName}}
        return f'''
        <div class="card-container">
            <div class="source-text">
                {{{source_lang_name}}}
            </div>

            <div class="audio-container">
                {{{{Audio}}}}
            </div>

            <div class="hint">
                💡 Tap to reveal translation ({target_lang_name})
            </div>
        </div>
        '''

    def _get_back_template(self, source_lang_name: str, target_lang_name: str) -> str:
        """HTML template for the back of the card."""
        return f'''
        {{{{FrontSide}}}}

        <hr class="divider">

        <div class="card-container">
            <div class="target-text">
                {{{target_lang_name}}}
            </div>

            {{{{#WordBreakdown}}}}
            <div class="breakdown-section">
                <div class="section-title">📚 Word Breakdown</div>
                <div class="breakdown-content">
                    {{{{WordBreakdown}}}}
                </div>
            </div>
            {{{{/WordBreakdown}}}}

            {{{{#GrammarNotes}}}}
            <div class="grammar-section">
                <div class="section-title">✏️ Grammar Notes</div>
                <div class="grammar-content">
                    {{{{GrammarNotes}}}}
                </div>
            </div>
            {{{{/GrammarNotes}}}}
        </div>
        '''

    def _get_card_styles(self) -> str:
        """CSS styling for the cards."""
        # Using more generic class names like .source-text, .target-text
        return '''
        /* Base card styling */
        .card {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                         'Helvetica Neue', Arial, sans-serif;
            font-size: 18px;
            line-height: 1.6;
            color: #2c3e50; /* Dark Grey */
            background: #ffffff; /* White */
            padding: 25px;
            border-radius: 12px; /* Added rounded corners */
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08); /* Subtle shadow */
            max-width: 650px; /* Slightly wider */
            margin: 20px auto; /* Centering with margin */
            border: 1px solid #e0e0e0; /* Light border */
        }

        .card-container {
            text-align: center;
        }

        /* Main text styling */
        .source-text { /* Renamed from .french-text */
            font-size: 30px; /* Slightly larger */
            font-weight: 600;
            color: #34495e; /* Darker Blue-Grey */
            margin: 25px 0;
            line-height: 1.4;
        }

        .target-text { /* Renamed from .english-text */
            font-size: 24px; /* Slightly larger */
            font-weight: 500;
            color: #16a085; /* Teal */
            margin: 20px 0;
            line-height: 1.4;
        }

        /* Audio player */
        .audio-container {
            margin: 20px 0;
        }
        /* Style the default Anki audio buttons */
        .replay-button svg {
             fill: #3498db; /* Blue */
             width: 30px;
             height: 30px;
        }
        .replay-button:hover svg {
             fill: #2980b9; /* Darker Blue */
        }


        /* Hint text on front */
        .hint {
            font-size: 14px;
            color: #95a5a6; /* Grey */
            margin-top: 30px;
            font-style: italic;
        }

        /* Divider between front and back */
        .divider {
            margin: 35px 0;
            border: none;
            border-top: 2px solid #ecf0f1; /* Light Grey */
        }

        /* Section Styling (Breakdown & Grammar) */
        .breakdown-section, .grammar-section {
            margin-top: 30px;
            text-align: left;
            padding: 20px;
            border-radius: 10px; /* Slightly less rounded */
            border-left: 5px solid; /* Accent border on the left */
        }

        .breakdown-section {
            background: #f8f9fa; /* Very Light Grey */
            border-left-color: #3498db; /* Blue */
        }

        .grammar-section {
            background: #fff9e6; /* Light Yellow */
            border-left-color: #f39c12; /* Orange */
        }

        .section-title {
            font-size: 16px;
            font-weight: 700;
            color: #495057; /* Medium Grey */
            margin-bottom: 15px; /* Increased spacing */
            text-transform: uppercase;
            letter-spacing: 0.8px; /* Increased letter spacing */
            border-bottom: 1px solid #e0e0e0; /* Underline */
            padding-bottom: 8px; /* Space below underline */
        }

        .breakdown-content, .grammar-content {
            font-size: 16px; /* Slightly larger */
            line-height: 1.8;
            color: #555; /* Darker Grey for better readability */
        }

        /* Word Breakdown Specific Styles */
        .breakdown-content b { /* Source Word */
            color: #2980b9; /* Darker Blue */
            font-weight: 600;
        }
        .breakdown-content .pos { /* Part of Speech */
            font-style: italic;
            color: #7f8c8d; /* Medium Grey */
            font-size: 0.9em;
        }
        .definition-target { /* Definition in Target Language */
             /* Main definition color is inherited */
        }
        .definition-native { /* Definition in Source Language */
            font-style: italic;
            color: #888; /* Lighter Grey */
            padding-left: 15px;
            font-size: 0.95em;
            display: block; /* Ensure it's on a new line */
            margin-top: 2px;
        }

        /* Grammar Notes Specific Styles */
        .grammar-content ul {
            padding-left: 20px;
            margin-top: 10px;
        }
        .grammar-content li {
            margin-bottom: 8px;
        }
        .grammar-content strong { /* Title of the note */
            color: #d35400; /* Dark Orange */
        }
         .grammar-content em { /* Examples */
            color: #7f8c8d; /* Medium Grey */
            font-size: 0.95em;
            margin-left: 15px;
            display: block;
        }

        /* Mobile responsiveness */
        @media (max-width: 600px) {
            .card {
                padding: 15px;
                font-size: 16px;
                margin: 10px auto;
            }

            .source-text {
                font-size: 26px;
            }

            .target-text {
                font-size: 22px;
            }
             .breakdown-content, .grammar-content {
                 font-size: 15px;
             }
        }

        /* Dark mode support (Anki 2.1.50+) */
        .nightMode .card {
            background: #2e3440; /* Nord Dark Background */
            color: #d8dee9; /* Nord Light Text */
            border-color: #434c5e; /* Nord Grey */
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }

        .nightMode .source-text {
            color: #eceff4; /* Nord Brightest White */
        }

        .nightMode .target-text {
            color: #88c0d0; /* Nord Cyan */
        }

        .nightMode .hint {
            color: #a3be8c; /* Nord Green */
        }

        .nightMode .divider {
            border-top-color: #4c566a; /* Nord Darker Grey */
        }

        .nightMode .breakdown-section {
            background: #3b4252; /* Nord Slightly Lighter Dark Background */
            border-left-color: #81a1c1; /* Nord Blue */
        }

        .nightMode .grammar-section {
            background: #434c5e; /* Nord Grey */
            border-left-color: #ebcb8b; /* Nord Yellow */
        }

        .nightMode .section-title {
            color: #e5e9f0; /* Nord Lighter Text */
            border-bottom-color: #4c566a;
        }

        .nightMode .breakdown-content, .nightMode .grammar-content {
            color: #d8dee9; /* Nord Light Text */
        }

        .nightMode .breakdown-content b {
            color: #81a1c1; /* Nord Blue */
        }
        .nightMode .breakdown-content .pos {
            color: #b48ead; /* Nord Purple */
        }
        .nightMode .definition-native {
            color: #a3be8c; /* Nord Green */
        }
        .nightMode .grammar-content strong {
            color: #d08770; /* Nord Orange */
        }
        .nightMode .grammar-content em {
            color: #b48ead; /* Nord Purple */
        }
        .nightMode .replay-button svg {
             fill: #81a1c1; /* Nord Blue */
        }
        .nightMode .replay-button:hover svg {
             fill: #8fbcbb; /* Nord Teal */
        }
        '''

    async def export_deck(
        self,
        deck: Deck,
        output_path: str
    ) -> Optional[str]:
        """
        Export a Deck domain model to an .apkg file.

        Args:
            deck: The Deck object containing cards and language info.
            output_path: The desired path for the output .apkg file.

        Returns:
            The absolute path to the created .apkg file, or None if export fails.
        """
        if not deck.cards:
            logger.warning(f"Deck '{deck.name}' has no cards. Skipping export.")
            return None
        if not deck.language_pair or len(deck.language_pair) != 2:
             logger.error(f"Deck '{deck.name}' is missing a valid language pair. Cannot export.")
             return None

        lang_pair = deck.language_pair
        source_lang_code, target_lang_code = lang_pair
        logger.info(f"Exporting deck '{deck.name}' ({source_lang_code} -> {target_lang_code}) to {output_path}")

        # Generate a stable deck ID based on deck name AND language pair
        deck_id = self._generate_stable_deck_id(deck.name, lang_pair)

        # Create or get the language-specific card model
        try:
            card_model = self._get_or_create_card_model(lang_pair)
        except Exception as e:
            logger.error(f"Failed to create/get card model for {lang_pair}: {e}", exc_info=True)
            return None

        # Create genanki deck
        anki_deck = genanki.Deck(deck_id=deck_id, name=deck.name)

        # Convert each card and add to deck, collecting media files
        media_filenames: Set[str] = set()
        successful_cards = 0
        failed_cards = 0

        for i, card in enumerate(deck.cards):
            try:
                note = self._convert_card_to_note(card, card_model, lang_pair)
                anki_deck.add_note(note)
                successful_cards += 1

                # Collect media files (audio) if present
                if card.audio and card.audio.filename:
                    media_filenames.add(card.audio.filename)
            except Exception as e:
                failed_cards += 1
                logger.error(f"Failed to convert card {i+1}/{len(deck.cards)} (Sentence: '{card.sentence.text[:50]}...'): {e}", exc_info=True)
                # Continue processing other cards

        if successful_cards == 0:
             logger.error(f"All cards failed conversion for deck '{deck.name}'. Check logs.")
             # Raise an error to signal failure clearly, especially for CLI
             raise RuntimeError(f"All cards failed conversion for deck '{deck.name}'. Check logs.")
             # return None # Alternative: return None if you want the caller to handle it silently


        logger.info(f"Successfully converted {successful_cards} cards for deck '{deck.name}'. {failed_cards} failed.")

        # Create package
        package = genanki.Package(anki_deck)

        # Resolve and add media files if any exist
        if media_filenames:
            resolved_media = self._resolve_media_paths(list(media_filenames))
            if resolved_media:
                package.media_files = resolved_media
                logger.info(f"Adding {len(resolved_media)} media file(s) to the package.")
            else:
                 logger.warning("No valid media files found or resolved despite filenames being present.")

        # Ensure output directory exists and write .apkg file
        try:
            output_file = Path(output_path).resolve()
            output_file.parent.mkdir(parents=True, exist_ok=True)
            package.write_to_file(str(output_file))
            logger.info(f"✅ Anki package successfully created: {output_file}")
            return str(output_file)
        except Exception as e:
            logger.error(f"Failed to write .apkg file to {output_path}: {e}", exc_info=True)
            return None


    def _convert_card_to_note(self, card: FlashCard, model: genanki.Model, lang_pair: LanguagePair) -> genanki.Note:
        """
        Convert a FlashCard domain model to a genanki Note using the specified model.

        Args:
            card: The FlashCard to convert.
            model: The genanki.Model (Note Type) to use.
            lang_pair: Tuple of (source_lang_code, target_lang_code).

        Returns:
            A genanki.Note instance.
        """
        source_lang_code, target_lang_code = lang_pair
        source_lang_name = self._get_language_name(source_lang_code, DEFAULT_SOURCE_LANG_NAME)
        target_lang_name = self._get_language_name(target_lang_code, DEFAULT_TARGET_LANG_NAME)

        # Prepare field data in the exact order defined in the model
        fields_data = [
            card.sentence.text,                             # Field 0: Source Language Text
            card.translation.text,                          # Field 1: Target Language Text
            self._format_word_breakdown(card, lang_pair),   # Field 2: WordBreakdown
            self._format_audio_field(card),                 # Field 3: Audio
            self._format_grammar_notes(card),               # Field 4: GrammarNotes
            " ".join(card.tags) if card.tags else "",      # Field 5: Tags
            card.sentence.id or str(uuid.uuid4()),          # Field 6: SentenceId (fallback to new UUID)
            source_lang_code,                               # Field 7: SourceLangCode (hidden)
            target_lang_code,                               # Field 8: TargetLangCode (hidden)
        ]

        # Generate a stable GUID for the note
        # Uses the Sentence ID and the Model ID to ensure uniqueness across note types
        # Corrected attribute access here:
        note_guid = genanki.guid_for(card.sentence.id, model.model_id) # CORRECTED LINE

        # Create the genanki Note
        note = genanki.Note(
            model=model,
            fields=fields_data,
            sort_field=source_lang_name, # Usually sort by the source text field
            tags=card.tags if card.tags else [],
            guid=note_guid
        )

        return note

    def _format_word_breakdown(self, card: FlashCard, lang_pair: LanguagePair) -> str:
        """Formats the word breakdown list into HTML for Anki."""
        if not card.word_breakdown or not card.word_breakdown.words:
            return ""

        source_lang_code, target_lang_code = lang_pair
        lines = []
        for word in card.word_breakdown.words:
            # Word (POS): Target Definition
            line = f"<b>{word.text}</b> <span class='pos'>({word.pos})</span>: <span class='definition-target'>{word.definition}</span>"
            lines.append(line)

            # Add native definition if available
            if word.definition_native:
                native_line = f"<span class='definition-native'>({source_lang_code}: {word.definition_native})</span>"
                lines.append(native_line)

        return "<br>".join(lines)

    def _format_grammar_notes(self, card: FlashCard) -> str:
        """Formats grammar notes into HTML for Anki."""
        if not card.grammar_notes:
            return ""

        lines = ["<ul>"] # Use an unordered list
        for note in card.grammar_notes:
            line = f"<li><strong>{note.title}:</strong> {note.explanation}"
            # Add examples if present, formatted as a sub-list or indented text
            if note.examples:
                examples_html = "".join([f"<em> - {ex}</em><br>" for ex in note.examples])
                line += f"<br>{examples_html}"
            line += "</li>"
            lines.append(line)
        lines.append("</ul>")

        return "".join(lines) # Join without separators as HTML takes care of it

    def _format_audio_field(self, card: FlashCard) -> str:
        """Formats the audio filename for Anki's [sound:] tag."""
        if not card.audio or not card.audio.filename:
            return ""
        # Basic sanitization - ensure no path characters are in the filename for the tag
        safe_filename = Path(card.audio.filename).name
        return f"[sound:{safe_filename}]"

    def _generate_stable_deck_id(self, deck_name: str, lang_pair: LanguagePair) -> int:
        """Generates a stable deck ID based on name and language pair."""
        id_str = f"{deck_name}-{lang_pair[0]}-{lang_pair[1]}"
        return self._generate_stable_id(id_str, DEFAULT_DECK_ID_SALT)

    def _resolve_media_paths(self, filenames: List[str]) -> List[str]:
        """
        Resolves relative audio filenames to absolute paths based on storage_path.

        Args:
            filenames: A list of audio filenames (e.g., "hash123.mp3").

        Returns:
            A list of absolute paths to existing audio files.
        """
        resolved_paths = []
        for filename in filenames:
            if not filename: continue # Skip empty filenames
            # Ensure we only use the filename part, not potential relative paths
            base_filename = Path(filename).name
            file_path = self.storage_path / base_filename
            if file_path.is_file(): # Check if it's actually a file
                resolved_paths.append(str(file_path))
            else:
                logger.warning(f"Audio file not found or is not a file: {file_path}")

        return resolved_paths

