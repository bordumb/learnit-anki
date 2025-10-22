# Quick Start Guide

Get your first language flashcard in under 5 minutes.

## Prerequisites

- Python 3.11+
- An OpenAI API key ([Get one here](https://platform.openai.com/api-keys))
- (Optional) Google Cloud Credentials for audio generation
- (Optional) DeepL API key for alternative translation

## 1. Install
```bash
# Clone or download the project
# git clone <repository_url>
cd anki-card-generator

# Install dependencies using Poetry (recommended)
poetry install
```

## 2. Configure

Create a `.env` file in the project root based on `.env.example`:
```bash
# .env (Example with minimal setup)
OPENAI_API_KEY=sk-your-key-here

# --- Optional Settings ---
# DEEPL_API_KEY=your-deepl-key # Add :fx suffix for free tier
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/google-credentials.json
# GOOGLE_TTS_VOICES='{"fr": "fr-FR-Neural2-A", "de": "de-DE-Neural2-B", "es": "es-ES-Neural2-A", "en": "en-US-Standard-A"}' # JSON string!
# DEFAULT_SOURCE_LANGUAGE=fr
# DEFAULT_TARGET_LANGUAGE=en
# TRANSLATION_PROVIDER=openai # or deepl
# STORAGE_TYPE=local # or s3
# STORAGE_PATH=./storage # if local
# S3_BUCKET=your-s3-bucket-name # if s3
# S3_REGION=us-east-1 # if s3
```

**Get your OpenAI API key:**

1. Go to https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Copy and paste it into `.env`
4. Consider adding billing credit (e.g., $5) for extensive use

## 3. Create Your First Card

### Single Card

French:
```bash
poetry run python infrastructure/cli/main.py add "Bonjour, comment ça va ?" -s fr -t en --deck-name "French Greetings" --audio"
```

German:
```bash
poetry run python infrastructure/cli/main.py add "Guten Tag, wie geht es Ihnen?" -s de -t en --deck-name "German Greetings" --audio
```

Spanish:
```bash
poetry run python infrastructure/cli/main.py add "Hola, ¿cómo estás?" -s es -t en --deck-name "Spanish Greetings" --audio
```

Catalan:
```bash
poetry run python infrastructure/cli/main.py add "Bon dia, com va?" -s ca -t en --deck-name "Catalan Basics" --audio
```

### Single Card (German to English)
```bash
poetry run python infrastructure/cli/main.py add "Ich möchte einen Kaffee." -s de -t en --deck-name "German Basics"
# Or using make:
# make add SENTENCE="Ich möchte einen Kaffee." SOURCE_LANG=de TARGET_LANG=en DECK="German Basics"
```

**What happens:**

- ✅ Translates the source sentence to the target language
- ✅ Breaks down each word with definitions in both languages
- ✅ (Optional) Generates audio using Google TTS if configured and `--audio` flag is used
- ✅ Creates an `.apkg` file (e.g., `output/French Practice.apkg` or `output/German Basics.apkg`)

**Import into Anki:**

1. Open Anki desktop application
2. Go to **File → Import...**
3. Select the generated `.apkg` file from the `output/` folder
4. Click **Import**. Done! Study your card.

## 4. Create a Deck (Multiple Cards)

### Step 1: Create a text file with sentences (one per line or paragraph)
```text
# german_sentences.txt
Ich möchte einen Kaffee, bitte.
Wo ist der Bahnhof?
Wie geht es Ihnen heute?
Ich mag deutsche Musik sehr.
Können Sie mir helfen?
Wie spät ist es?
```

### Step 2: Generate the deck (German to English)
```bash
poetry run python infrastructure/cli/main.py batch german_sentences.txt -s de -t en --deck-name "Daily German"
# Or using make:
# make batch FILE=german_sentences.txt SOURCE_LANG=de TARGET_LANG=en DECK="Daily German"
```

**Output (example):**
```
Loading sentences from german_sentences.txt...
Found 6 sentences.
🔄 Processing 6 sentences (de -> en)...
✅ Card generated for 'Ich möchte einen Kaffee, bitte.'
✅ Card generated for 'Wo ist der Bahnhof?'
✅ Card generated for 'Wie geht es Ihnen heute?'
✅ Card generated for 'Ich mag deutsche Musik sehr.'
✅ Card generated for 'Können Sie mir helfen?'
✅ Card generated for 'Wie spät ist es?'
✅ Deck created with 6 cards: ./output/Daily German_de-en.apkg
```

### Step 3: Import into Anki

Same process: **File → Import...** → Select the `.apkg` file.

## 5. What Your Cards Look Like (Example: French → English)

### Front (Question)
```html
<div class="card-container">
    <div class="source-text">
        Je voudrais un café, s'il vous plaît.
    </div>
    <!-- Audio player here if enabled -->
    <div class="hint">
        💡 Tap to reveal translation (English)
    </div>
</div>
```

### Back (Answer)
```html
<!-- Front side content repeated -->
<hr class="divider">
<div class="card-container">
    <div class="target-text">
        I would like a coffee, please.
    </div>
    <div class="breakdown-section">
        <div class="section-title">📚 Word Breakdown</div>
        <div class="breakdown-content">
            <b>Je</b> <span class='pos'>(pronoun)</span>: <span class='definition-target'>I</span><br><span class='definition-native'>(Fr: Je)</span><br>
            <b>voudrais</b> <span class='pos'>(verb)</span>: <span class='definition-target'>would like</span><br><span class='definition-native'>(Fr: vouloir)</span><br>
            <b>un</b> <span class='pos'>(article)</span>: <span class='definition-target'>a/an</span><br><span class='definition-native'>(Fr: un)</span><br>
            <b>café</b> <span class='pos'>(noun)</span>: <span class='definition-target'>coffee</span><br><span class='definition-native'>(Fr: café)</span><br>
            <b>s'il vous plaît</b> <span class='pos'>(phrase)</span>: <span class='definition-target'>please</span><br><span class='definition-native'>(Fr: s'il vous plaît)</span><br>
        </div>
    </div>
    <!-- Grammar notes here if enabled -->
</div>
```

*(Note: Actual appearance depends on Anki version and CSS)*

## 6. Common Use Cases

### From a movie script (Spanish to English)
```bash
# Copy subtitles to movie_subtitles_es.txt
poetry run python infrastructure/cli/main.py batch movie_subtitles_es.txt -s es -t en --deck-name "Movie Spanish"
```

### From a textbook chapter (French to German)
```bash
# Copy example sentences to chapter_3_fr.txt
poetry run python infrastructure/cli/main.py batch chapter_3_fr.txt -s fr -t de --deck-name "French 101 - Ch 3 (De)"
```

### From a news article (using defaults fr→en)
```bash
# Copy interesting sentences to news_article_fr.txt
poetry run python infrastructure/cli/main.py batch news_article_fr.txt --deck-name "Current Events (Fr)"
```

## 7. Tips & Tricks

### Using the Makefile

The Makefile provides shorter commands:
```bash
# Install once
make install

# Test your setup
make test

# Create a French card (defaults)
make add SENTENCE="Bonjour, ça va?"

# Create a German card
make add SENTENCE="Guten Tag" SOURCE_LANG=de TARGET_LANG=en DECK="German Greetings"

# Create a deck from a French file (defaults)
make batch FILE=french_sentences.txt DECK="My French Deck"

# Create a deck from a German CSV, specify column
make batch FILE=german_words.csv SOURCE_LANG=de TARGET_LANG=en DECK="German Vocab" COLUMN="GermanWord"

# Add extra CLI args (like --audio or --no-grammar)
make batch FILE=sentences.txt ARGS='--audio --no-grammar'
```

See `make help` for more details.

### Cost Estimate

With OpenAI GPT-4o-mini (prices may vary):

- 1 card ≈ $0.005 - $0.01 (translation + analysis + grammar)
- 100 cards ≈ $0.50 - $1.00
- 1000 cards ≈ $5 - $10

Audio generation (Google TTS) has separate costs, usually very low per sentence.

### File Organization
```
sentences/
├── french/
│   ├── greetings.txt
│   └── travel.txt
├── german/
│   └── news.txt
└── spanish/
    └── literature.txt
```

Then process each:
```bash
poetry run python infrastructure/cli/main.py batch sentences/german/news.txt -s de -t en --deck-name "German News"
```

## 8. Troubleshooting

### "OpenAI API key not found" or Authentication Errors

- Ensure `.env` file exists in the project root (`anki-card-generator/`)
- Verify the key starts with `sk-` and is correct
- Check there are no extra spaces or quotes around the key in `.env`
- Ensure you have billing set up or credits available on OpenAI

### "Command not found: poetry"

- Make sure Poetry is installed correctly (`pip install poetry`)
- If installed, ensure its bin directory is in your system's PATH
- Alternatively, use `python3` directly if you installed via pip into a venv:
```bash
source .venv/bin/activate # Activate virtual environment first
python3 infrastructure/cli/main.py add "Your sentence" -s fr -t en
```

### "google.auth.exceptions.DefaultCredentialsError" (Audio)

- Ensure `GOOGLE_APPLICATION_CREDENTIALS` in `.env` points to a valid JSON key file
- Make sure the service account associated with the key file has the "Cloud Text-to-Speech API User" role in Google Cloud
- Try running `gcloud auth application-default login` if using user credentials (less common for servers)

### Cards not showing up or importing incorrectly in Anki

- Make sure you are importing the `.apkg` file via **File → Import...** in Anki Desktop
- Check the `output/` folder for the generated file. Does it have content?
- If updating a deck, ensure you use the exact same deck name

### Translation or Analysis Quality Issues

- LLMs work best with complete, context-rich sentences
- Avoid very short fragments or ambiguous phrases if possible
- Experiment with different models (e.g., GPT-4o instead of GPT-4o-mini via settings) if quality is consistently poor, but be mindful of higher costs

## 9. Next Steps

- **Configure Audio:** Set up `GOOGLE_APPLICATION_CREDENTIALS` and `GOOGLE_TTS_VOICES` in `.env` and use the `--audio` flag (or `ARGS='--audio'` with make)
- **Configure DeepL:** Add `DEEPL_API_KEY` and set `TRANSLATION_PROVIDER=deepl` in `.env`
- **Customize Card Template:** Modify HTML/CSS in `adapters/anki/genanki_exporter.py`
- **Explore API:** Run `uvicorn infrastructure.api.main:app --reload` (after `poetry install`) and check http://127.0.0.1:8000/docs for the API interface

## 10. Getting Help

**Q: Can I use this for any language pair?**  
A: Yes! Use the `-s` (source) and `-t` (target) options. Supported languages depend on the underlying services (OpenAI, DeepL, Google TTS). Check their documentation for full lists.

**Q: How do I update existing cards in my Anki deck?**  
A: Simply re-import an `.apkg` file generated with the exact same deck name. Anki matches cards based on the first field (the source sentence) and will update existing ones or add new ones. Your review progress is preserved. See `docs/add_to_existing_deck.md`.

**Q: Can I add images?**  
A: Not directly supported by this tool yet. You would need to manually add images in Anki after importing.

**Q: Is my data sent externally?**  
A: Yes, sentences are sent to OpenAI (and potentially DeepL/Google Cloud) APIs for processing. Do not process sensitive or private information.

## Quick Reference
```bash
# Single card (Specify languages)
poetry run python infrastructure.cli.main add "Sentence here" -s <source_code> -t <target_code> --deck-name "My Deck" [--audio] [--no-grammar]

# Deck from file (Specify languages)
poetry run python infrastructure.cli.main batch <filepath> -s <source_code> -t <target_code> --deck-name "My Deck" [--column <csv_col>] [--audio] [--no-grammar]

# Test setup
poetry run python infrastructure.cli.main test

# With Make (Example: Spanish -> English)
make add SENTENCE="Hola Mundo" SOURCE_LANG=es TARGET_LANG=en DECK="Spanish Hello" ARGS='--audio'
make batch FILE=spanish.txt SOURCE_LANG=es TARGET_LANG=en DECK="Spanish Sentences"
```

**Cost:** ≈ $0.01 per card (OpenAI GPT-4o-mini) + low cost for audio  
**Time:** ≈ 2-5 seconds per card (without audio), longer with audio  
**Result:** Customizable Anki flashcards for various languages

Happy learning! 🌍