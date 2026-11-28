import asyncio
import json
from pathlib import Path
import tempfile
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
        self.assertEqual({row["suite"] for row in rows}, {case.suite for case in cases})


if __name__ == "__main__":
    unittest.main()


def test_cli_approval_exports_only_corrected_text_and_source(monkeypatch, tmp_path):
    import sqlite3
    import zipfile

    from click.testing import CliRunner
    from adapters.anki.genanki_exporter import GenankiExporter
    from adapters.storage.local_file_storage import LocalFileStorage
    from infrastructure.cli import main

    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main, "project_root", tmp_path)
    storage = LocalFileStorage(str(tmp_path / "storage"))
    audio_provider = MockAudioService()
    generator = GenerateCardUseCase(MockTranslationService(), MockDictionaryService(),
                                    audio_provider, storage, None, "fr", "en")
    monkeypatch.setattr(main.container, "create_card_generator", lambda: generator)
    monkeypatch.setattr(main.container, "_deck_exporter", GenankiExporter(str(storage.audio_path)))
    source = "episode.mp3 [0:12.5–0:19.3]"
    for command, factory in (("ocr", "create_image_transcriber"), ("transcribe", "create_audio_transcriber")):
        monkeypatch.setattr(main.container, factory,
                            lambda: TranscribeMediaUseCase(FixtureTranscriber("週未に会おう")))
        media = tmp_path / "selected"
        media.write_bytes(b"fixture")
        result = runner.invoke(main.cli, [command, "--source", source, str(media)])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == {"text": "週未に会おう", "language": "ja", "source": source}
        assert not list((tmp_path / "output").glob("*.apkg"))

    result = runner.invoke(main.cli, ["add", "-s", "ja", "-t", "en", "--deck-name", "Japanese",
                                      "--json-result", "--audio", "--source", source, "--", "週末に会おう"])
    assert result.exit_code == 0, result.output
    path = tmp_path / "output/Japanese.apkg"
    assert json.loads(result.output.splitlines()[-1]) == {"package": str(path)}
    expected_audio, _ = asyncio.run(audio_provider.generate_audio("週末に会おう", "ja"))
    with zipfile.ZipFile(path) as package:
        database = package.extract("collection.anki2", tmp_path)
        assert expected_audio.filename in json.loads(package.read("media")).values()
    with sqlite3.connect(database) as db:
        fields, = db.execute("select flds from notes").fetchone()
        assert db.execute("select count(*) from cards").fetchone() == (1,)
    japanese, english, vocabulary, audio, notes, *_ = fields.split("\x1f")
    assert japanese == "週末に会おう"
    assert english and vocabulary
    assert audio == f"[sound:{expected_audio.filename}]"
    assert source in notes


def test_optional_audio_exceptions_preserve_card():
    from unittest.mock import AsyncMock

    for stage in ("synthesis", "storage"):
        audio = MockAudioService()
        storage = MockStorageService()
        if stage == "synthesis":
            audio.generate_audio = AsyncMock(side_effect=RuntimeError("offline"))
        else:
            storage.save_audio = AsyncMock(side_effect=OSError("disk full"))
        generator = GenerateCardUseCase(MockTranslationService(), MockDictionaryService(),
                                        audio, storage, None, "ja", "en")
        card = asyncio.run(generator.execute("週末に会おう"))
        assert card.audio is None
        assert card.translation.text


def test_export_failure_preserves_package_and_reports_cli_error(monkeypatch, tmp_path):
    from click.testing import CliRunner
    from genanki import Package
    from adapters.anki.genanki_exporter import GenankiExporter
    from infrastructure.cli import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main, "project_root", tmp_path)
    generator = GenerateCardUseCase(MockTranslationService(), MockDictionaryService(),
                                    MockAudioService(), MockStorageService(), None, "ja", "en")
    monkeypatch.setattr(main.container, "create_card_generator", lambda: generator)
    monkeypatch.setattr(main.container, "_deck_exporter", GenankiExporter(str(tmp_path)))
    target = tmp_path / "output/Japanese.apkg"
    target.parent.mkdir()
    target.write_bytes(b"previous package")

    def interrupted_write(self, path):
        Path(path).write_bytes(b"incomplete")
        raise OSError("disk full")

    monkeypatch.setattr(Package, "write_to_file", interrupted_write)
    result = CliRunner().invoke(main.cli, ["add", "--deck-name", "Japanese", "週末に会おう"])
    assert result.exit_code != 0
    assert "Could not write Anki package" in result.output
    assert target.read_bytes() == b"previous package"


def test_existing_voice_overrides_keep_japanese_pronunciation():
    from infrastructure.config.settings import Settings

    settings = Settings(_env_file=None, google_tts_voices={"fr": "fr-FR-Standard-B"})
    assert settings.google_tts_voices["ja"] == "ja-JP-Standard-A"
    assert settings.google_tts_voices["fr"] == "fr-FR-Standard-B"


def test_batch_json_result_reports_created_package_and_empty_input(monkeypatch, tmp_path):
    from click.testing import CliRunner
    from adapters.anki.genanki_exporter import GenankiExporter
    from core.use_cases.generate_deck import GenerateDeckUseCase
    from infrastructure.cli import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main, "project_root", tmp_path)
    storage = MockStorageService()
    card_generator = GenerateCardUseCase(MockTranslationService(), MockDictionaryService(),
                                         MockAudioService(), storage, None, "ja", "en")
    deck_generator = GenerateDeckUseCase(card_generator, GenankiExporter(str(tmp_path)), storage, "ja", "en")
    monkeypatch.setattr(main.container, "create_deck_generator", lambda: deck_generator)

    input_file = tmp_path / "sentences.csv"
    input_file.write_text("japanese\n週末に会おう\nじゃあまた\n", encoding="utf-8")
    args = ["batch", "-s", "ja", "-t", "en", "--deck-name", "Japanese",
            "--column", "japanese", "--json-result", "--", str(input_file)]
    runner = CliRunner()
    result = runner.invoke(main.cli, args)
    assert result.exit_code == 0, result.output
    path = tmp_path / "output/Japanese.apkg"
    assert json.loads(result.output.splitlines()[-1]) == {"package": str(path)}
    original = path.read_bytes()

    input_file.write_text("japanese\n", encoding="utf-8")
    result = runner.invoke(main.cli, args)
    assert result.exit_code != 0
    assert "No sentences found" in result.output
    assert path.read_bytes() == original


def test_add_offers_manual_translation_after_provider_failure(monkeypatch, tmp_path):
    import sqlite3
    import zipfile

    from click.testing import CliRunner
    from infrastructure.cli import main
    from infrastructure.config.dependency_injection import ServiceContainer
    from infrastructure.config.settings import Settings

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main, "project_root", tmp_path)
    container = ServiceContainer(Settings(_env_file=None, openai_api_key=None, deepl_api_key=None,
                                          google_application_credentials=None, storage_path=str(tmp_path / "storage")))
    monkeypatch.setattr(main, "container", container)
    runner = CliRunner()
    args = ["add", "-s", "ja", "-t", "en", "--no-audio", "--deck-name", "Japanese",
            "--json-result", "--source", "notebook.jpg"]
    text = "次の駅で乗り換えます。"
    failed = runner.invoke(main.cli, [*args, "--", text])
    assert failed.exit_code != 0
    assert any(line.startswith('{"error": "translation"') for line in failed.output.splitlines())
    assert not (tmp_path / "output/Japanese.apkg").exists()

    approved = "I'll change trains at the next station."
    created = runner.invoke(main.cli, [*args, "--translation", approved, "--", text])
    assert created.exit_code == 0, created.output
    path = Path(json.loads(created.output.splitlines()[-1])["package"])
    with zipfile.ZipFile(path) as package:
        database = package.extract("collection.anki2", tmp_path)
    with sqlite3.connect(database) as db:
        fields, = db.execute("select flds from notes").fetchone()
    japanese, english, vocabulary, audio, notes, *_ = fields.split("\x1f")
    assert japanese == text
    from html import unescape
    assert unescape(english) == approved
    assert not vocabulary
    assert not audio
    assert "notebook.jpg" in notes
