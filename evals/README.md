# Transcription evaluation

The [Japanese golden datasets](../data/golden/ja) have two suites. Use `smoke` to check that the two transcription adapters work with known short samples. Use `passages` to measure continuous speech and multi-line handwriting. Inspect the source category and provenance before drawing conclusions about a particular type of audio or handwriting.

Run from the project root:

    python -m evals.transcription --validate-only
    poetry run python -m evals.transcription --suite passages --kind image --output output/transcription-evals/ocr.json
    poetry run python -m evals.transcription --suite passages --kind audio --output output/transcription-evals/speech.json

For offline scoring, pass `--predictions path/to/predictions.jsonl` with one record per selected case using `id`, `prediction`, and optionally `latency_seconds`. Pass `--manifest` one or more times to evaluate a different collection. Each JSONL case supplies `id`, `media` (relative to the manifest), `reference`, `language`, `group`, `source_url`, and `license`. Set `suite` to `passages` for extended samples. Omitted values default to `smoke`. For custom folder names add `kind` as `image` or `audio` and optionally `category`. Keep images from the same source and clips from the same speaker together when making development and held-out splits.

The runner reports exact match, character error rate, and provider latency by suite, modality, and source category. It ignores Unicode canonical equivalence and whitespace differences, while preserving kana, kanji, punctuation, and other differences. Character error rate is total edit distance divided by total reference characters. API errors are counted separately, reported per case, and make the live run exit nonzero.

For a workflow comparison, time several cards from capture through approval and export, then compare with manual typing of the same phrase. Model latency is recorded by the runner. Human review time is measured separately.
