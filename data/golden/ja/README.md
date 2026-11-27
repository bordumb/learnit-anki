# Japanese transcription benchmarks

Run `python -m evals.transcription --validate-only` from the repository root to check the manifests and local media without calling a model. Run `poetry run python -m evals.transcription --suite passages` to measure transcription quality with the configured adapters.

| Input | Passage samples | Smoke samples |
| --- | --- | --- |
| [Audio](audio/README.md) | Real two-speaker conversations with time-aligned human transcripts, plus public spoken articles | Short utterances |
| [Handwriting](handwriting/README.md) | Handwritten contemporary office memos and multi-column original manuscripts | Isolated historic glyphs |

Each modality has its own `cases.jsonl`. A row links the input to its reference text, the original sources, and the usage terms. The `passages/` directories hold the underlying images and audio clips. Keep cases with a shared speaker, writer, or copied prompt in the same split. Report results by category to account for different source styles and transcription conventions.

See the [evaluation guide](../../../evals/README.md) for metrics and offline scoring.
