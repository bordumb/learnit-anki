# Quick Start Guide

Get your first French flashcard in under 5 minutes.

## Prerequisites

- Python 3.11+
- An OpenAI API key ([Get one here](https://platform.openai.com/api-keys))

---

## 1. Install
```bash
# Clone or download the project
cd anki-card-generator

# Install dependencies
poetry install

# Or use pip if you prefer
python3 -m venv .venv
source .venv/bin/activate
pip install click genanki httpx pydantic pydantic-settings python-dotenv openai
```

---

## 2. Configure

Create a `.env` file in the project root:
```bash
# .env
OPENAI_API_KEY=sk-your-key-here
TRANSLATION_PROVIDER=openai
STORAGE_PATH=./storage
```

**Get your OpenAI API key:**
1. Go to https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Copy and paste it into `.env`
4. Add $5 credit (will last for hundreds of cards)

---

## 3. Create Your First Card

### Single Card
```bash
poetry run python infrastructure/cli/main.py add "Je voudrais un café."
```

**What happens:**
1. ✅ Translates to English: "I would like a coffee."
2. ✅ Breaks down each word with definitions
3. ✅ Creates `output/French Practice.apkg`

**Import into Anki:**
1. Open Anki
2. File → Import
3. Select `output/French Practice.apkg`
4. Done! Study your card

---

## 4. Create a Deck (Multiple Cards)

### Step 1: Create a text file with French sentences
```bash
# sentences.txt
Je voudrais un café, s'il vous plaît.
Où est la gare?
Comment allez-vous aujourd'hui?
J'aime beaucoup la musique française.
Pouvez-vous m'aider?
Quelle heure est-il?
```

### Step 2: Generate the deck
```bash
poetry run python infrastructure/cli/main.py batch sentences.txt --deck-name "Daily French"
```

**Output:**
```
🔄 Processing 6 sentences...
  [1/6] Je voudrais un café, s'il vous plaît....
  [2/6] Où est la gare?...
  [3/6] Comment allez-vous aujourd'hui?...
  [4/6] J'aime beaucoup la musique française....
  [5/6] Pouvez-vous m'aider?...
  [6/6] Quelle heure est-il?...
✅ Deck created with 6 cards: ./output/Daily French.apkg
```

### Step 3: Import into Anki

Same process: File → Import → Select the `.apkg` file

---

## 5. What Your Cards Look Like

### Front (Question)
```
🇫🇷 Français

Je voudrais un café, s'il vous plaît.

💡 Tap to reveal translation
```

### Back (Answer)
```
🇬🇧 English

I would like a coffee, please.

📚 Word Breakdown
Je (pronoun): I
voudrais (verb): would like
un (article): a/an
café (noun): coffee
s'il vous plaît (phrase): please
```

---

## 6. Common Use Cases

### From a movie script
```bash
# Copy subtitles to a file
# Generate cards
poetry run python infrastructure/cli/main.py batch movie_subtitles.txt --deck-name "Amélie Movie"
```

### From a textbook chapter
```bash
# Copy example sentences from your textbook
poetry run python infrastructure/cli/main.py batch chapter_3.txt --deck-name "French 101 - Chapter 3"
```

### From a news article
```bash
# Copy interesting sentences
poetry run python infrastructure/cli/main.py batch news_article.txt --deck-name "Current Events"
```

---

## 7. Tips & Tricks

### Use the Makefile (easier commands)
```bash
# Install once
make install

# Test your setup
make test

# Create a card
make add SENTENCE="Bonjour, ça va?"

# Create a deck
make batch FILE=sentences.txt DECK="My Deck"
```

### Cost Estimate

With OpenAI GPT-4o-mini:
- **1 card** = ~$0.005 (half a cent)
- **100 cards** = ~$0.50
- **1000 cards** = ~$5

Your $5 credit will last a long time!

### File Organization
```
sentences/
├── beginner/
│   ├── greetings.txt
│   ├── food.txt
│   └── travel.txt
├── intermediate/
│   └── news.txt
└── advanced/
    └── literature.txt
```

Then batch process each:
```bash
poetry run python infrastructure/cli/main.py batch sentences/beginner/food.txt --deck-name "Food Vocabulary"
```

---

## 8. Troubleshooting

### "OpenAI API key not found"
- Check `.env` file exists in project root
- Verify key starts with `sk-`
- No quotes around the key in `.env`

### "Command not found: poetry"
Use `python3` directly:
```bash
python3 infrastructure/cli/main.py add "Your sentence"
```

### Cards not showing up in Anki
- Make sure you're importing the `.apkg` file, not opening it
- In Anki: File → Import (not File → Open)
- Check `output/` folder for the generated file

### Translation quality issues
- Sentences work best when they're complete thoughts
- Avoid fragments like "the cat" - use "The cat is sleeping"
- Context helps: "Il mange." is ambiguous, "Il mange une pomme." is clear

---

## 9. Next Steps

Once you're comfortable with the basics:

1. **Add audio** - Set up Google Cloud TTS for pronunciation
2. **Add grammar notes** - Enable `include_grammar=True`
3. **Customize templates** - Edit `adapters/anki/genanki_exporter.py`
4. **Add sentence search** - Automatically find example sentences

See the full documentation for advanced features.

---

## 10. Getting Help

**Common Questions:**

**Q: Can I use this for other languages?**  
A: Yes! Just change the sentence language. The code is French-focused but works for any language pair.

**Q: How do I update existing cards?**  
A: Re-import the deck. Anki will update cards with the same text.

**Q: Can I add images?**  
A: Not yet in the CLI version, but it's on the roadmap.

**Q: Is my data sent to OpenAI?**  
A: Yes, sentences are sent to OpenAI's API for translation. Don't use sensitive content.

---

## Example Output

Here's what a generated `.apkg` file contains:
```
French Practice.apkg
├── Card 1: "Je voudrais un café."
│   ├── Front: French sentence
│   ├── Back: English + word breakdown
│   └── Metadata: tags, timestamps
├── Card 2: "Où est la gare?"
│   └── ...
└── Media: (audio files when enabled)
```

Import this into Anki and start studying immediately!

---

## Quick Reference
```bash
# Single card
poetry run python infrastructure/cli/main.py add "French sentence here"

# Deck from file  
poetry run python infrastructure/cli/main.py batch file.txt --deck-name "Deck Name"

# Test setup
poetry run python infrastructure/cli/main.py test

# With Make
make add SENTENCE="French sentence"
make batch FILE=sentences.txt DECK="Deck Name"
```

**Cost:** ~$0.005 per card with OpenAI  
**Time:** ~2-3 seconds per card  
**Result:** Professional Anki flashcards with translations and definitions

---

Happy learning! 🇫🇷
