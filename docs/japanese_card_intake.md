# Japanese cards from text, images, and audio

Open the macOS app's **Japanese Card** tab. Type Japanese directly, open an image and drag a rectangle around a phrase, or import or record audio. Click **Read Image** or **Transcribe Audio**, adjust the draft, then choose **Create Card**. You can replay the audio or inspect the original image as you edit. The app uses your selected project directory and its `.venv/bin/python`.

For a podcast or longer recording, turn on **Select a time range**, enter the start and end in seconds, and preview the excerpt. **Transcribe Selection** sends only that excerpt. The card's source notes include the file or source label and the time range of the last successful transcription. The app can trim PCM audio natively and uses FFmpeg for compressed audio when installed. FFmpeg and `ffprobe` are also detected in the standard Homebrew bin directories.

## Command line

    poetry run python infrastructure/cli/main.py ocr notes.png
    poetry run python infrastructure/cli/main.py transcribe phrase.m4a
    poetry run python infrastructure/cli/main.py add "週末に会おう" -s ja -t en --audio --source "Notebook, p. 42"

The two transcription commands print a JSON draft with text, language, and a source label. Pass a cropped file to the OCR command to limit it to the phrase. Add `--source` to record a URL or a short label. Review the draft before passing its text to `add`. The source label appears in the card's notes on the back. The original audio is used for review and transcription. The audio included on the card is the optional TTS rendering of the approved text.

Install the Poetry dependencies with `poetry install`. Enable Google Cloud Vision and configure Application Default Credentials, or set `GOOGLE_APPLICATION_CREDENTIALS` to a service account key for image transcription. Google Cloud Text-to-Speech must also be configured if you enable pronunciation audio. Set `OPENAI_API_KEY` for speech transcription and the existing dictionary and card enrichment. `OPENAI_TRANSCRIPTION_MODEL` defaults to `gpt-transcribe`.

The two providers implement the same transcription interface. The CLI and Swift app use the same draft commands, and all three inputs call the existing card-generation use case after approval.

See [evaluation](../evals/README.md) for the Japanese golden datasets and scoring.
