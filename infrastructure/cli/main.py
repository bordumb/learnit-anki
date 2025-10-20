# infrastructure/cli/main.py
import click
import asyncio
from pathlib import Path
import sys
import os

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Now we can import from the project
from infrastructure.config.dependency_injection import get_container
from infrastructure.cli.importers import load_sentences
from core.domain.models import Deck
from adapters.anki.genanki_exporter import GenankiExporter

# Get the DI container
try:
    container = get_container()
except Exception as e:
    click.echo(f"❌ Error loading configuration: {e}")
    click.echo("💡 Make sure your .env file is set up correctly.")
    sys.exit(1)

@click.group()
def cli():
    """French Flashcard Generator - Create Anki cards automatically"""
    pass

@cli.command()
@click.argument('sentence')
@click.option('--deck-name', default='French Practice', help='Name of the Anki deck')
@click.option('--no-grammar', is_flag=True, help='Disable grammar/phrase notes')
@click.option('--audio', is_flag=True, help='Enable audio generation (slower)')
def add(sentence, deck_name, no_grammar, audio):
    """
    Generate a single flashcard from a French sentence.
    
    Example:
        python infrastructure/cli/main.py add "Je mange une pomme."
    """
    click.echo(f"🔄 Generating card for: {sentence}")
    
    async def generate_card():
        # 1. Get the use case from the container
        card_generator = container.create_card_generator()
        
        # 2. Execute the use case
        card = await card_generator.execute(
            sentence_text=sentence,
            include_audio=audio,
            include_grammar=not no_grammar
        )
        
        # 3. Get the exporter
        # We use the base exporter directly for a single card
        exporter = GenankiExporter()
        deck = Deck(name=deck_name, cards=[card])
        
        output_path = Path("output") / f"{deck_name}.apkg"
        
        # 4. Export the deck
        output_file = await exporter.export_deck(
            deck=deck,
            output_path=str(output_path)
        )
        
        return output_file

    try:
        output = asyncio.run(generate_card())
        click.echo(f"✅ Card created: {output}")
        click.echo(f"📥 Import this file into Anki!")
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        if "GOOGLE_APPLICATION_CREDENTIALS" in str(e):
             click.echo("💡 Audio generation failed. Did you set GOOGLE_APPLICATION_CREDENTIALS in .env?")
             click.echo("   Try running with the --audio flag disabled (it's off by default).")

@cli.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--deck-name', default='French Batch', help='Name of the Anki deck')
@click.option('--column', default='sentence', help='CSV column name to use')
@click.option('--no-grammar', is_flag=True, help='Disable grammar/phrase notes')
@click.option('--audio', is_flag=True, help='Enable audio generation (very slow for batches!)')
def batch(file_path, deck_name, column, no_grammar, audio):
    """
    Generate multiple cards from a .txt (article or list) or .csv file.
    
    Example (Text file):
        python infrastructure/cli/main.py batch "my_article.txt" --deck-name "Article Deck"
        
    Example (CSV file):
        python infrastructure/cli/main.py batch "vocab.csv" --column "FrenchSentence"
    """
    
    # 1. Load sentences using the new importer
    try:
        click.echo(f"Loading sentences from {file_path}...")
        sentences = load_sentences(file_path, column)
        click.echo(f"Found {len(sentences)} sentences.")
    except Exception as e:
        click.echo(f"❌ Error loading file: {e}")
        return
        
    if not sentences:
        click.echo("No sentences found. Exiting.")
        return

    click.echo(f"🔄 Processing {len(sentences)} sentences...")
    if audio:
        click.echo("🔊 Audio generation enabled. This may take a while.")
    
    async def generate_deck():
        # 2. Get the use case from the container
        deck_generator = container.create_deck_generator()
        
        output_path = Path("output") / f"{deck_name}.apkg"
        
        # 3. Execute the use case
        output_file = await deck_generator.execute(
            sentences=sentences,
            deck_name=deck_name,
            output_path=str(output_path),
            include_audio=audio,
            include_grammar=not no_grammar
        )
        return output_file

    try:
        output = asyncio.run(generate_deck())
        click.echo(f"✅ Deck created with {len(sentences)} cards: {output}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        if "GOOGLE_APPLICATION_CREDENTIALS" in str(e):
             click.echo("💡 Audio generation failed. Did you set GOOGLE_APPLICATION_CREDENTIALS in .env?")


@cli.command()
def test():
    """Test your configuration"""
    click.echo("🧪 Testing configuration...")
    
    try:
        settings = container.settings
        click.echo("✅ Settings loaded")
        
        if settings.openai_api_key:
            click.echo("✅ OpenAI API key found")
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            client.models.list()
            click.echo("✅ OpenAI key is valid")
        else:
            click.echo("❌ OpenAI API key missing")

        if settings.google_application_credentials:
            click.echo("✅ Google credentials path found")
        else:
            click.echo("⚠️  Google credentials missing (audio will be disabled)")
        
        Path("./output").mkdir(exist_ok=True)
        click.echo("✅ Output directory ready")
        
        click.echo("\n🎉 Everything looks good! Try:")
        click.echo('   python infrastructure/cli/main.py add "Bonjour!"')
        
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        click.echo("\n💡 Make sure you have a .env file with:")
        click.echo("   OPENAI_API_KEY=sk-your-key-here")

if __name__ == '__main__':
    cli()