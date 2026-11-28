# Japanese cards from text, images, and audio

## Launch on macOS

From the repository root, run the following on first setup. The app looks for Python at `.venv/bin/python`.

```sh
POETRY_VIRTUALENVS_IN_PROJECT=true poetry install
make install-furigana
open learnit-deck/learnit-deck.xcodeproj
```

Select the **learnit-deck** scheme and **My Mac** in Xcode and press **⌘R**. At the folder prompt, choose the repository root containing `pyproject.toml`. You can change this path in **Learnit → Settings** (⌘,).

## Study in Learnit

The Mac app opens to **Today**, with **Review**, **Create**, **Decks**, **Browse**, **Progress**, and **Settings** in the sidebar. The collection is stored locally in `~/Library/Application Support/Learnit Study/Collection.sqlite3`.

1. Choose **Import from Anki** on **Today** and open `output/nihongo-deck-repaired.apkg`. Inspect the counts, then click **Import collection**. The copy in Learnit includes the existing Japanese passages, dictionary text, readings, due dates, reviews, and referenced media. Reimporting the same cards leaves local edits and review state in place.
2. Go to **Create** to paste a passage, recognize an image, transcribe audio, or attach a source clip. **Look up words** suggests dictionary links you can edit. Hover over a linked word in the editor, preview, or review answer to read its entry from the enabled macOS dictionaries. Add context, definition notes, or a translation if needed. **Furigana** opens editable readings. Use **Preview card → Save card** to save it to the selected deck.
3. Choose **Start review** to study due cards and new cards. Press Space to reveal an answer and 1–4 to rate it. Learnit uses the imported due dates for the first review and its own scheduling rules for subsequent reviews.
4. Use **Browse** to find and edit cards, **Progress** to view reviews, and **Settings** to set the new-card limit or back up or restore the collection. Backups consist of one SQLite file that includes media.

To convert older handwritten readings, open **Settings → Clean up older readings…**. The preview uses the kana you entered to place furigana on the original passage, and keeps any trailing source annotations. Confirm the conversion to save a SQLite backup and update the matching notes. In **Browse**, turn on **Unbracketed readings** to find entries that still need manual attention.

For a new Anki export, select **Include Scheduling Information**, **Include Media**, and **Support older Anki versions** as needed. Learnit imports legacy-compatible packages with a single recognition template and Expression/Meaning or Front/Back fields. Preview lists the number of cards that use other templates. The repaired Japanese deck is already in the supported format.

## Export individual cards to Anki

Open **File → Anki Export Window** on the Mac to use these export workflows.

### Use the existing Japanese deck

Learnit picks up `output/nihongo-deck-repaired.apkg` when it is present. You can also use the deck menu in the toolbar to choose a compatible Anki package. The reference package identifies the destination and the original note type.

1. Paste or type the whole passage, or open an image or audio recording from **Add source**. Review the full recognized passage in the editor.
2. Click **Look up words** to add editable dictionary links. Hover over a word to see its definition in Learnit, or click it to open macOS Dictionary. Enable a Japanese dictionary in Dictionary settings. Use **Definition notes** to save any definitions or specific senses you want on the card itself.
3. Add the source or page, a context note, and an English translation if you want them on the card. **Translate** uses the configured translation provider. Manual entries can be exported directly.
4. For audio, turn on **Pronunciation audio** to use the Mac’s Japanese Kyoko voice, or click **Attach audio…** and choose a recording or excerpt. If the passage already has an audio source, **Include source audio** attaches the excerpt used for that passage. Playback appears on the back of the Anki card.
5. Click **Furigana** beside the passage heading to preview readings at any point, or **Preview card** when the card is ready. MeCab and UniDic generate furigana on your Mac for the whole passage. Click a word on the back preview to add or correct its kana. When an unfamiliar name is split into adjacent kanji chunks, open the first chunk's reading and include the next chunk before saving. If the local analyzer is unavailable, you can still enter readings in the same preview.
6. Click **Export to Anki**, then open the resulting package in Anki to add the card to the existing deck.

The new note uses the original note type. `Expression` holds the whole passage. `Meaning` contains the dictionary links, any definition notes, source, context note, and translation in that order. `Reading` holds the approved readings in Anki's bracket format, which the repaired Japanese deck displays on the back. The reference package is opened read-only.

### Standard cards and batch import

Choose **Use standard card format** from the deck menu. Type or paste Japanese in the editor, or add an image, audio file, or recording through **Add source**. The recognized text appears in the editor for review.

Choose the deck and whether to include **Pronunciation audio**, then select **Create card** (⌘↩). Pronunciation audio uses the final edited text. **More options** contains the language pair, grammar notes, and a source label. For multiple cards, use **Import text or CSV** with the same deck options. If you import a CSV, enter the column containing the text.

If automatic translation fails, **Use my own translation** keeps the recognized text and lets you enter the translation you want on the card. It is also available under **More options**. This path uses your translation with optional pronunciation audio and skips cloud vocabulary and grammar generation.

**Recognize on Mac** uses Apple Vision to recognize the selected image on the device. **Use Google instead** sends the selected image to Cloud Vision and shows Google’s error details when a request is rejected. Large uploads use a high-quality JPEG at the same resolution when it reduces the file size.

For a podcast or longer recording, turn on **Select a time range**, enter the start and end in seconds, and preview the excerpt. **Transcribe selection** sends only that excerpt. The card's source notes include the file or source label and the time range of the last successful transcription. The app can trim PCM audio natively and uses FFmpeg for compressed audio when installed. FFmpeg and `ffprobe` are also detected in the standard Homebrew bin directories.

After export, click **Open in Anki** to import the package or **Show in Finder** to locate it. Packages are saved under `output/` in the project folder. Import each package before creating another card for the same deck, since the next export writes to the same path.

## Command line

    poetry run python infrastructure/cli/main.py ocr notes.png
    poetry run python infrastructure/cli/main.py transcribe phrase.m4a
    poetry run python infrastructure/cli/main.py furigana passage.txt
    poetry run python infrastructure/cli/main.py add "週末に会おう" -s ja -t en --audio --source "Notebook, p. 42"

The two transcription commands print a JSON draft with text, language, and a source label. Pass a cropped file to the OCR command to limit it to the phrase. Add `--source` to record a URL or a short label. Review the draft before passing its text to `add`. The source label appears in the card's notes on the back. The original audio is used for review and transcription. The audio included on the card is the optional TTS rendering of the approved text.

Enable Google Cloud Vision and configure Application Default Credentials, or set `GOOGLE_APPLICATION_CREDENTIALS` to a service account key for image transcription. Google Cloud Text-to-Speech must also be configured if you enable pronunciation audio. Set `OPENAI_API_KEY` for speech transcription and the existing dictionary and card enrichment. `OPENAI_TRANSCRIPTION_MODEL` defaults to `gpt-transcribe`.

The two providers implement the same transcription interface. The CLI and Swift app use the same draft commands, and all three inputs call the existing card-generation use case after approval.

See [evaluation](../evals/README.md) for the Japanese golden datasets and scoring.
See the [design specification](specs/japanese-card-intake.md) for architecture, repository layout, and acceptance criteria.
