import asyncio
import json
from pathlib import Path
import unittest

from core.use_cases.generate_card import GenerateCardUseCase
from core.use_cases.transcribe_media import TranscribeMediaUseCase
from evals.transcription import GOLDEN, load_cases, score_predictions, summarize
from tests.mocks import (
    MockAudioService, MockDictionaryService, MockStorageService,
    MockTranslationService,
)


class FixtureTranscriber:
    def __init__(self, text):
        self.text = text
        self.calls = []

    async def transcribe(self, path, language):
        self.calls.append((path, language))
        return self.text


class CardIntakeTests(unittest.TestCase):
    def test_typed_image_and_audio_use_the_same_approved_text_path(self):
        cases = load_cases(sorted(GOLDEN.glob("*/cases.jsonl")))
        generator = GenerateCardUseCase(
            MockTranslationService(), MockDictionaryService(), MockAudioService(),
            MockStorageService(), None, "fr", "en",
        )

        async def generate(text, source=None):
            return await generator.execute(
                text, source_lang="ja", target_lang="en", source=source
            )

        typed = asyncio.run(generate("週末に会おう"))
        self.assertEqual(typed.sentence.text, "週末に会おう")
        self.assertIsNone(typed.sentence.source)

        for kind in ("image", "audio"):
            with self.subTest(kind=kind):
                case = next(case for case in cases if case.kind == kind)
                adapter = FixtureTranscriber("  週未に会おう\n")
                draft = asyncio.run(TranscribeMediaUseCase(adapter).execute(
                    case.media, "ja", source=f"Native Japanese {kind} source"
                ))
                self.assertEqual(adapter.calls, [(case.media, "ja")])
                self.assertEqual(draft.text, "週未に会おう")

                card = asyncio.run(generate("週末に会おう", draft.source))
                self.assertEqual(card.sentence.text, typed.sentence.text)
                self.assertEqual(card.sentence.language, "ja")
                self.assertEqual(card.sentence.source, f"Native Japanese {kind} source")
                self.assertEqual(card.audio.filename, typed.audio.filename)

    def test_benchmark_scores_all_references_and_detects_mutated_predictions(self):
        cases = load_cases(sorted(GOLDEN.glob("*/cases.jsonl")))
        self.assertEqual({case.kind for case in cases}, {"image", "audio"})
        self.assertGreaterEqual(len(cases), 12)
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "predictions.jsonl"
            predictions = [
                {"id": case.id, "prediction": case.reference, "latency_seconds": 0.1}
                for case in cases
            ]
            predictions[0]["prediction"] += "違"
            path.write_text("\n".join(json.dumps(item) for item in predictions), encoding="utf-8")
            rows = score_predictions(cases, path)
        summary = summarize(rows)
        self.assertEqual(summary["scored"], len(cases))
        self.assertEqual(sum(row["character_edits"] for row in rows), 1)
        self.assertEqual(summary["exact_match_rate"], (len(cases) - 1) / len(cases))
        self.assertGreater(summary["character_error_rate"], 0)
        self.assertEqual(summary["median_latency_seconds"], 0.1)


if __name__ == "__main__":
    unittest.main()
