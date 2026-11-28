import json
import sqlite3
from contextlib import closing
from pathlib import Path
from zipfile import ZipFile

import genanki
import pytest
from click.testing import CliRunner

from adapters.anki.passage_deck import PassageDeck
from infrastructure.cli import main


@pytest.fixture
def reference(tmp_path):
    model = genanki.Model(
        1348443974379, "Japanese Reference",
        fields=[{"name": name} for name in ("Expression", "Meaning", "Reading")],
        templates=[{
            "name": "Recognition", "qfmt": "{{Expression}}",
            "afmt": "{{FrontSide}}<hr>{{furigana:Reading}}<br>{{Meaning}}",
        }],
        css=".card { text-align: left; }",
    )
    deck = genanki.Deck(1577049437088, "日本語への知識欲")
    deck.add_note(genanki.Note(model=model, fields=["先に入っていた文。", "Existing", ""]))
    reference = tmp_path / "reference.apkg"
    genanki.Package(deck).write_to_file(reference)
    return reference


def test_export_passage_keeps_reference_note_type_and_all_text(reference, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main, "project_root", tmp_path)
    payload = tmp_path / "draft.json"
    payload.write_text(json.dumps({
        "expression": "先方から返事が来た。\nこちらの案で進める。",
        "definitions": "【先方】相手側。\n【案】考え。",
        "source": "会話メモ <04:12>",
        "context": "二人で決めた。",
        "translation": "They got back to me.",
        "reading": "先方[せんぽう]から 返事[へんじ]が 来[き]た。\nこちらの 案[あん]で 進[すす]める。",
    }, ensure_ascii=False), encoding="utf-8")
    runner = CliRunner()
    args = ["export-passage", str(reference), str(payload)]
    first = runner.invoke(main.cli, args)
    assert first.exit_code == 0, first.output
    second = runner.invoke(main.cli, args)
    assert second.exit_code == 0 and first.output == second.output
    package = Path(json.loads(first.output.splitlines()[-1])["package"])
    assert package != reference
    expected = PassageDeck.load(reference)
    assert PassageDeck.load(package).note_type == expected.note_type
    with ZipFile(package) as archive, closing(sqlite3.connect(":memory:")) as db:
        db.deserialize(archive.read("collection.anki2"))
        [(mid, fields, did)] = db.execute("SELECT mid, flds, did FROM notes JOIN cards ON nid=notes.id").fetchall()
    assert (mid, did) == (int(expected.note_type["id"]), expected.deck["id"])
    assert fields.split("\x1f") == [
        "先方から返事が来た。<br>こちらの案で進める。",
        "【先方】相手側。<br>【案】考え。<br><br>会話メモ &lt;04:12&gt;"
        "<br><br>二人で決めた。<br><br>They got back to me.",
        "先方[せんぽう]から 返事[へんじ]が 来[き]た。<br>こちらの 案[あん]で 進[すす]める。",
    ]


def test_export_rejects_control_characters_that_would_create_extra_fields(reference, tmp_path):
    profile = PassageDeck.load(reference)
    with pytest.raises(ValueError, match="control character"):
        profile.export({"expression": "先方", "definitions": "語義\x1f余分な項目"}, tmp_path)


def test_export_requires_meaning_content(reference, tmp_path):
    profile = PassageDeck.load(reference)
    with pytest.raises(ValueError, match="Add a definition"):
        profile.export({"expression": "先方", "source": "会話メモ"}, tmp_path)


def test_export_embeds_audio_on_back_under_original_note_type(reference, tmp_path, monkeypatch):
    import wave

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main, "project_root", tmp_path)
    pronunciation = tmp_path / "voice.wav"
    recording = tmp_path / "original [clip].wav"
    for path, sample in [(pronunciation, b"\x01\x02"), (recording, b"\x03\x04")]:
        with wave.open(str(path), "wb") as audio:
            audio.setparams((1, 2, 16000, 0, "NONE", ""))
            audio.writeframes(sample * 100)
    payload = tmp_path / "draft.json"
    payload.write_text(json.dumps({"expression": "先方から返事が来た。", "translation": "They got back to me."}))
    runner = CliRunner()
    args = ["export-passage", str(reference), str(payload)]
    plain = runner.invoke(main.cli, args)
    with_audio = runner.invoke(main.cli, [*args, "--pronunciation", str(pronunciation), "--recording", str(recording)])
    assert plain.exit_code == with_audio.exit_code == 0, with_audio.output

    def note(result):
        package = Path(json.loads(result.output.splitlines()[-1])["package"])
        with ZipFile(package) as archive, closing(sqlite3.connect(":memory:")) as db:
            db.deserialize(archive.read("collection.anki2"))
            guid, fields = db.execute("SELECT guid, flds FROM notes").fetchone()
            media = {name: archive.read(index) for index, name in json.loads(archive.read("media")).items()}
        return guid, fields.split("\x1f"), media

    original_guid, _, _ = note(plain)
    guid, (expression, meaning, reading), media = note(with_audio)
    assert guid != original_guid
    assert expression == "先方から返事が来た。" and reading == ""
    assert len(media) == 2
    for label, attachment in [("Pronunciation", pronunciation), ("Source audio", recording)]:
        [filename] = [name for name, data in media.items() if data == attachment.read_bytes()]
        assert f"{label} [sound:{filename}]" in meaning
