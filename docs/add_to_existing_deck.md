# Adding New Cards to an Existing Anki Deck

This guide explains the correct and most efficient workflow for continuously adding new flashcards to a deck you've already started studying in Anki.

## Key Principle

You don't need to re-process old sentences. By using a consistent deck name, you can generate small, separate packages of only new cards and Anki will intelligently merge them into your main deck.

This method avoids making redundant API calls for sentences that have already been processed, saving time and money.

## The Incremental Workflow

Follow this process to add cards from a new source (e.g., a new article or CSV file) to a deck that's already in your Anki collection.

### Step 1: Create Your Initial Deck

First, generate and import your starting set of cards. The most important part of this command is the `--deck-name`. This name will be the permanent identifier for your deck.

```bash
# Process your first file
poetry run python infrastructure/cli/main.py batch chapter_1.txt --deck-name "My Master French Deck"
```

This creates `output/My Master French Deck.apkg`.

**Action:** Import this `.apkg` file into Anki. You will now have a deck named "My Master French Deck" in your collection.

### Step 2: Generate a Package for a New File

Weeks later, you have a new file, `article_on_philosophy.txt`, and you want to add its sentences to your existing deck.

Run the `batch` command on this new file only, but use the exact same `--deck-name` as before.

```bash
# Process ONLY the new file
poetry run python infrastructure/cli/main.py batch article_on_philosophy.txt --deck-name "My Master French Deck"
```

This command will overwrite the old `.apkg` file in your `output/` folder with a new one that contains only the cards from `article_on_philosophy.txt`. This is the correct and intended behavior.

### Step 3: Import the New Package

Go back into Anki and import the newly generated `output/My Master French Deck.apkg` file.

Anki will recognize that the package is for an existing deck. It will check the new cards against the cards already in your collection and show you a summary like this:

- **Cards added:** 25 (the new cards from the article)
- **Cards updated:** 0
- **Cards unchanged:** 0

The new cards will be seamlessly added to your "My Master French Deck," while all your existing cards and their study progress remain untouched.

You can repeat this process indefinitely with `text_file_3.txt`, `text_file_4.txt`, and so on.

## Why This Method Works

This workflow is both safe and efficient because of two key technical details:

1. **Stable Deck ID:** The script creates a unique ID for your deck by hashing the string you provide in `--deck-name`. As long as the name "My Master French Deck" is identical every time, the generated `.apkg` will always target the same deck inside Anki's database.

2. **Anki's Note Uniqueness:** When importing, Anki checks the first field of each note (for this project, the French sentence). If a card with that same first field already exists in the deck, Anki will either update it or skip it. Since you are only processing new sentences, Anki will see them as new and add them.

This is the ideal way to manage a large, evolving flashcard collection without risking data loss or making unnecessary API calls.
