# infrastructure/cli/main.py
import click
import asyncio
from pathlib import Path
import sys
import os
import logging

# --- Logging Setup ---
# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
# --- End Logging Setup ---


# Add the project root to the Python path
# Ensure this runs only once and correctly finds the project root
try:
    project_root = Path(__file__).resolve().parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
        logger.info(f"Added project root to sys.path: {project_root}")
except Exception as e:
    logger.error(f"Error determining project root: {e}")
    sys.exit(1)


# Now we can import from the project
try:
    from infrastructure.config.dependency_injection import get_container
    from infrastructure.cli.importers import load_sentences
    from core.domain.models import Deck
    # Removed direct import of GenankiExporter as it's handled by DI
except ImportError as e:
     logger.error(f"Failed to import necessary modules. Check sys.path and project structure. Error: {e}")
     sys.exit(1)


# Get the DI container
try:
    container = get_container()
    logger.info("Dependency Injection container initialized successfully.")
except Exception as e:
    # Use logger instead of click.echo for initialization errors
    logger.error(f"❌ Error loading configuration or initializing DI container: {e}")
    logger.error("💡 Make sure your .env file is set up correctly and dependencies are installed.")
    # Provide more specific guidance if possible
    if "api_key" in str(e).lower():
        logger.error("💡 Check that OPENAI_API_KEY (and optionally DEEPL_API_KEY) are set in your .env file.")
    if "GOOGLE_APPLICATION_CREDENTIALS" in str(e):
         logger.error("💡 If using audio, ensure GOOGLE_APPLICATION_CREDENTIALS points to a valid file path in .env.")

    sys.exit(1)

# --- Language Code Validation ---
# Reuse the language names from the exporter for validation help
try:
    # Attempt to import for validation, handle if it fails
    from adapters.anki.genanki_exporter import LANGUAGE_NAMES
    SUPPORTED_LANG_CODES = list(LANGUAGE_NAMES.keys())
except ImportError:
    logger.warning("Could not import LANGUAGE_NAMES for validation help. Using basic codes.")
    SUPPORTED_LANG_CODES = ['fr', 'en', 'de', 'es', 'ca'] # Fallback

def validate_lang_code(ctx, param, value):
    """Click callback to validate language codes."""
    if value is None: # Allow None if default is used
        return None
    if value.lower() in SUPPORTED_LANG_CODES:
        return value.lower()
    else:
        raise click.BadParameter(f"Unsupported language code '{value}'. Supported codes: {', '.join(SUPPORTED_LANG_CODES)}")
# --- End Language Code Validation ---


@click.group()
def cli():
    """Language Flashcard Generator - Create Anki cards automatically"""
    # Create necessary directories if they don't exist
    try:
        Path("./output").mkdir(parents=True, exist_ok=True)
        Path("./storage/audio").mkdir(parents=True, exist_ok=True)
        Path("./logs").mkdir(parents=True, exist_ok=True)
        logger.info("Ensured output, storage/audio, and logs directories exist.")
    except OSError as e:
        logger.warning(f"Could not create necessary directories: {e}")
    pass

@cli.command()
@click.argument('sentence')
@click.option('--deck-name', default='Language Practice', help='Name of the Anki deck.')
@click.option('--source-lang', '-s', default=None, callback=validate_lang_code, help=f'Source language code (e.g., {", ".join(SUPPORTED_LANG_CODES)}). Defaults to setting from .env.')
@click.option('--target-lang', '-t', default=None, callback=validate_lang_code, help=f'Target language code (e.g., {", ".join(SUPPORTED_LANG_CODES)}). Defaults to setting from .env.')
@click.option('--no-grammar', is_flag=True, default=False, help='Disable grammar/phrase notes.')
@click.option('--audio/--no-audio', default=False, help='Enable/disable audio generation (requires setup, default: disabled).') # Changed to flag pair
def add(sentence, deck_name, source_lang, target_lang, no_grammar, audio):
    """
    Generate a single flashcard from a sentence.

    Example (French to English):
        anki-cli add "Je mange une pomme." -s fr -t en

    Example (German to English, default deck name):
        anki-cli add "Ich esse einen Apfel." -s de -t en
    """
    # Use defaults from settings if not provided via CLI
    final_source_lang = source_lang or container.settings.default_source_language
    final_target_lang = target_lang or container.settings.default_target_language

    click.echo(f"🔄 Generating card ({final_source_lang} -> {final_target_lang}) for: \"{sentence}\"")
    if audio:
        click.echo("🔊 Audio generation enabled.")

    async def generate_single_card_async():
        # 1. Get the use case from the container
        # The DI container now passes default languages to the use case constructor
        card_generator = container.create_card_generator()

        # 2. Execute the use case, passing specific languages
        card = await card_generator.execute(
            sentence_text=sentence,
            source_lang=final_source_lang, # Pass determined languages
            target_lang=final_target_lang,
            include_audio=audio,
            include_grammar=not no_grammar
        )

        if card is None:
             # Use case should ideally raise exceptions, but handle None defensively
             logger.error("Card generation failed (use case returned None).")
             raise RuntimeError("Card generation failed.")

        # 3. Get the exporter from the container
        exporter = container.deck_exporter # Use the exporter instance from DI

        # Create a Deck object with the single card and language pair
        deck = Deck(
            name=deck_name,
            cards=[card],
            language_pair=(final_source_lang, final_target_lang) # Set language pair on Deck
        )

        # Define output path relative to project root
        output_path = project_root / "output" / f"{deck_name}.apkg"
        output_path.parent.mkdir(parents=True, exist_ok=True) # Ensure directory exists

        # 4. Export the deck
        output_file = await exporter.export_deck(
            deck=deck,
            output_path=str(output_path)
        )

        return output_file

    try:
        # Run the async function
        output = asyncio.run(generate_single_card_async())
        click.echo(f"✅ Card created in deck '{deck_name}': {output}")
        click.echo(f"📥 Import this file into Anki!")
    except Exception as e:
        logger.error(f"❌ Error during single card generation: {e}", exc_info=True) # Log full traceback
        click.echo(f"❌ Error: {e}")
        # Provide specific hints based on common errors
        if "GOOGLE_APPLICATION_CREDENTIALS" in str(e) and audio:
             click.echo("💡 Audio generation failed. Check GOOGLE_APPLICATION_CREDENTIALS in .env and ensure the service account has Text-to-Speech API enabled.")
        elif "401" in str(e):
             click.echo("💡 Authentication failed. Check your API keys (OpenAI, DeepL) in the .env file.")
        elif "429" in str(e):
             click.echo("💡 API Rate limit or quota exceeded. Please check your API account usage.")
        sys.exit(1)


@cli.command()
@click.argument('file_path', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('--deck-name', default=None, help='Name of the Anki deck (defaults to filename).')
@click.option('--column', default='sentence', help='CSV column name containing sentences.')
@click.option('--source-lang', '-s', default=None, callback=validate_lang_code, help=f'Source language code (e.g., {", ".join(SUPPORTED_LANG_CODES)}). Defaults to setting from .env.')
@click.option('--target-lang', '-t', default=None, callback=validate_lang_code, help=f'Target language code (e.g., {", ".join(SUPPORTED_LANG_CODES)}). Defaults to setting from .env.')
@click.option('--no-grammar', is_flag=True, default=False, help='Disable grammar/phrase notes.')
@click.option('--audio/--no-audio', default=False, help='Enable/disable audio generation (slow for batches, requires setup, default: disabled).')
def batch(file_path, deck_name, column, source_lang, target_lang, no_grammar, audio):
    """
    Generate multiple cards from a .txt or .csv file.

    Example (French text file to English):
        anki-cli batch "data/french_article.txt" -s fr -t en --deck-name "French News"

    Example (German CSV to Spanish):
        anki-cli batch "data/german_vocab.csv" --column "GermanSentence" -s de -t es
    """
    # Determine default deck name from filename if not provided
    if deck_name is None:
        deck_name = Path(file_path).stem.replace('_', ' ').title()

    # Use defaults from settings if not provided via CLI
    final_source_lang = source_lang or container.settings.default_source_language
    final_target_lang = target_lang or container.settings.default_target_language

    # 1. Load sentences using the importer
    try:
        click.echo(f"🔄 Loading sentences from: {file_path}")
        sentences = load_sentences(file_path, column)
        if not sentences:
            click.echo("⚠️ No sentences found in the file. Exiting.")
            sys.exit(0)
        click.echo(f"✅ Found {len(sentences)} sentences.")
    except FileNotFoundError:
         click.echo(f"❌ Error: File not found at {file_path}")
         sys.exit(1)
    except ValueError as e: # Catch specific errors like bad column
         click.echo(f"❌ Error processing file: {e}")
         sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error loading file: {e}", exc_info=True)
        click.echo(f"❌ Unexpected error loading file: {e}")
        sys.exit(1)

    click.echo(f"🔄 Processing {len(sentences)} sentences for deck '{deck_name}' ({final_source_lang} -> {final_target_lang})...")
    if audio:
        click.echo("🔊 Audio generation enabled. This may take a while for large files.")

    async def generate_deck_async():
        # 2. Get the use case from the container
        deck_generator = container.create_deck_generator()

        # Define output path relative to project root
        output_path = project_root / "output" / f"{deck_name}.apkg"
        output_path.parent.mkdir(parents=True, exist_ok=True) # Ensure directory exists

        # 3. Execute the use case, passing languages
        output_file = await deck_generator.execute(
            sentences=sentences,
            deck_name=deck_name,
            output_path=str(output_path),
            source_lang=final_source_lang, # Pass determined languages
            target_lang=final_target_lang,
            include_audio=audio,
            include_grammar=not no_grammar
        )
        return output_file

    try:
        # Run the async function
        output = asyncio.run(generate_deck_async())
        # Use final count from deck object if available, otherwise use input count
        # (This requires deck_generator to return Deck object or count, currently it returns path)
        # For now, stick with input count for the message.
        click.echo(f"✅ Deck created for '{deck_name}': {output}")
        click.echo(f"📥 Import this file into Anki!")
    except Exception as e:
        logger.error(f"❌ Error during batch deck generation: {e}", exc_info=True) # Log full traceback
        click.echo(f"❌ Error: {e}")
        # Provide specific hints based on common errors
        if "GOOGLE_APPLICATION_CREDENTIALS" in str(e) and audio:
             click.echo("💡 Audio generation failed. Check GOOGLE_APPLICATION_CREDENTIALS in .env and ensure the service account has Text-to-Speech API enabled.")
        elif "401" in str(e):
             click.echo("💡 Authentication failed. Check your API keys (OpenAI, DeepL) in the .env file.")
        elif "429" in str(e):
             click.echo("💡 API Rate limit or quota exceeded. Please check your API account usage.")
        sys.exit(1)


@cli.command()
def test():
    """Test configuration and API connectivity."""
    click.echo("🧪 Testing configuration...")
    success = True

    # Test Settings Loading
    try:
        settings = container.settings
        click.echo("[1/6] ✅ Settings loaded successfully from .env")

        # Check essential keys
        if not settings.openai_api_key:
             click.echo("    ❌ OpenAI API key (OPENAI_API_KEY) missing in .env")
             success = False
        else:
            click.echo("    ✅ OpenAI API key found.")

        click.echo(f"    - Default Source Language: {settings.default_source_language}")
        click.echo(f"    - Default Target Language: {settings.default_target_language}")
        click.echo(f"    - Translation Provider: {settings.translation_provider}")
        click.echo(f"    - Storage Type: {settings.storage_type}")
        if settings.storage_type == 'local':
            click.echo(f"    - Storage Path: {settings.storage_path}")

    except Exception as e:
        click.echo(f"[1/6] ❌ Failed to load settings: {e}")
        success = False

    # Test Directories
    click.echo("[2/6] Checking required directories...")
    try:
        Path("./output").mkdir(parents=True, exist_ok=True)
        Path("./storage/audio").mkdir(parents=True, exist_ok=True)
        Path("./logs").mkdir(parents=True, exist_ok=True)
        click.echo("    ✅ Output, storage, and logs directories checked/created.")
    except OSError as e:
        click.echo(f"    ❌ Failed to create directories: {e}")
        success = False

    # Test OpenAI API Connectivity (if key exists)
    click.echo("[3/6] Testing OpenAI API connection...")
    if container.settings.openai_api_key:
        try:
            client = openai.OpenAI(api_key=container.settings.openai_api_key)
            client.models.list() # Simple API call to test connectivity/auth
            click.echo("    ✅ OpenAI API connection successful.")
        except openai.AuthenticationError:
            click.echo("    ❌ OpenAI Authentication Error: Invalid API key.")
            success = False
        except openai.APIConnectionError as e:
             click.echo(f"    ❌ OpenAI Connection Error: Could not connect to API. {e}")
             success = False
        except Exception as e:
            click.echo(f"    ❌ OpenAI Error: {e}")
            success = False
    else:
        click.echo("    ⚠️  Skipped (OpenAI API key not found).")


    # Test DeepL API Connectivity (if key exists and provider is deepl)
    click.echo("[4/6] Testing DeepL API connection...")
    if container.settings.translation_provider == "deepl" and container.settings.deepl_api_key:
         async def test_deepl():
             translator = container.translation_service # Get configured instance
             try:
                 # Use usage endpoint which requires less quota
                 await translator.client.get(f"{translator.base_url}/usage", params={'auth_key': translator.api_key})
                 click.echo("    ✅ DeepL API connection successful.")
             except Exception as e:
                 click.echo(f"    ❌ DeepL Error: {e}")
                 return False # Indicate failure
             return True # Indicate success

         if not asyncio.run(test_deepl()):
             success = False

    elif container.settings.translation_provider == "deepl":
        click.echo("    ❌ Skipped (DeepL API key missing in .env, but DeepL is selected provider).")
        success = False
    else:
         click.echo(f"    ℹ️  Skipped (Translation provider is '{container.settings.translation_provider}').")


    # Test Google TTS Credentials (if path exists)
    click.echo("[5/6] Testing Google Cloud Credentials for TTS...")
    google_creds_path = container.settings.google_application_credentials
    if google_creds_path:
        path_obj = Path(google_creds_path)
        if path_obj.exists() and path_obj.is_file():
             click.echo(f"    ✅ Google credentials file found at: {google_creds_path}")
             # You could add a simple TTS API call here for a deeper test, but file existence is a good start
             # Example: try container.audio_service.client.list_voices()
        else:
             click.echo(f"    ❌ Google credentials file NOT found at the specified path: {google_creds_path}")
             click.echo("       Audio generation will likely fail.")
             success = False
    else:
        click.echo("    ⚠️  Skipped (GOOGLE_APPLICATION_CREDENTIALS not set in .env). Audio generation disabled.")


    # Test Anki Exporter Dependencies (Genanki)
    click.echo("[6/6] Checking Anki exporter setup...")
    try:
        import genanki
        click.echo("    ✅ Genanki library is installed.")
    except ImportError:
        click.echo("    ❌ Genanki library not found. Please run 'poetry install'.")
        success = False


    # Final Summary
    click.echo("\n--- Test Summary ---")
    if success:
        click.echo("🎉 All basic checks passed! Configuration seems okay.")
        click.echo("\n💡 Try generating a card:")
        click.echo(f'   anki-cli add "Bonjour!" -s {container.settings.default_source_language} -t {container.settings.default_target_language}')
    else:
        click.echo("❌ Some configuration tests failed. Please review the errors above and check your .env file.")

if __name__ == '__main__':
    # Add simple check to ensure running from project root or venv
    expected_cli_path = project_root / "infrastructure" / "cli" / "main.py"
    if not Path(__file__).resolve() == expected_cli_path.resolve():
         logger.warning(f"CLI is being run from an unexpected location: {Path(__file__).resolve()}")
         logger.warning(f"Expected location: {expected_cli_path.resolve()}")
         logger.warning("Ensure you run commands from the project root directory or using 'poetry run'.")

    cli()
