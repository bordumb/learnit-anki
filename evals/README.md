# Transcription evaluation

The [Japanese golden datasets](../data/golden/ja) have two suites. Use `smoke` to check that the two transcription adapters work with known short samples. Use `passages` to measure continuous speech and multi-line handwriting. Inspect the source category and provenance before drawing conclusions about a particular type of audio or handwriting.

Run from the project root:

    python -m evals.transcription --validate-only
    poetry run python -m evals.transcription --suite passages --kind image --output output/transcription-evals/ocr.json
    poetry run python -m evals.transcription --suite passages --kind audio --output output/transcription-evals/speech.json

For offline scoring, pass `--predictions path/to/predictions.jsonl` with one record per selected case using `id`, `prediction`, and optionally `latency_seconds`. Pass `--manifest` one or more times to evaluate a different collection. Each JSONL case supplies `id`, `media` (relative to the manifest), `reference`, `language`, `group`, `source_url`, and `license`. Set `suite` to `passages` for extended samples. Omitted values default to `smoke`. For custom folder names add `kind` as `image` or `audio` and optionally `category`. Keep images from the same source and clips from the same speaker together when making development and held-out splits.

## Offline baselines

Generate predictions with a local [whisper.cpp](https://github.com/ggml-org/whisper.cpp) build and `ffmpeg`, or with Tesseract and Japanese [`tessdata_best`](https://github.com/tesseract-ocr/tessdata_best) models (`jpn.traineddata` and `jpn_vert.traineddata`). The runner passes the manifest's known language to Whisper and uses its writing direction to select Tesseract's layout. It never passes reference text to either engine. Use the resulting JSONL to run the same scorer as the cloud adapters.

    python -m evals.local_predictions whisper --whisper-model /path/to/ggml-base.bin --output output/audio-predictions.jsonl
    python -m evals.transcription --suite passages --kind audio --predictions output/audio-predictions.jsonl --output output/audio-baseline.json
    python -m evals.local_predictions tesseract --tessdata /path/to/tessdata --output output/ocr-predictions.jsonl
    python -m evals.transcription --suite passages --kind image --predictions output/ocr-predictions.jsonl --output output/ocr-baseline.json

## Metrics

The runner reports exact match, character error rate, and provider latency by suite, modality, and source category. It ignores Unicode canonical equivalence and whitespace differences, while preserving kana, kanji, punctuation, and other differences. Character error rate is total edit distance divided by total reference characters. API errors are counted separately, reported per case, and make the live run exit nonzero.

For a workflow comparison, time several cards from capture through approval and export, then compare with manual typing of the same phrase. Model latency is recorded by the runner. Human review time is measured separately.
