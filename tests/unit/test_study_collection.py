import datetime as dt
import hashlib
import json
import sqlite3
import wave
from contextlib import closing
from pathlib import Path
from zipfile import ZipFile

import genanki
import pytest
from click.testing import CliRunner

from adapters.study.anki_import import import_package, inspect_package
from adapters.study.collection import Collection, connect
from adapters.study.reading_cleanup import apply_reading_cleanup, bracket_reading, preview_reading_cleanup
from adapters.readings.mecab import reading_tagger
from infrastructure.cli.study import study


@pytest.fixture
def collection(tmp_path):
    path = tmp_path / "Collection.sqlite3"
    with closing(connect(path)) as db:
        yield Collection(db, path, dt.datetime(2026, 11, 28, 12).timestamp())


@pytest.fixture
def source_package(tmp_path):
    audio = tmp_path / "voice.wav"
    with wave.open(str(audio), "wb") as recording:
        recording.setparams((1, 2, 8000, 0, "NONE", ""))
        recording.writeframes(b"\x00\x00" * 80)
    model = genanki.Model(1348443974379, "Japanese", [
        {"name": name} for name in ("Expression", "Meaning", "Reading")
    ], [{"name": "Recognition", "qfmt": "{{Expression}}", "afmt": "{{furigana:Reading}}<br>{{Meaning}}"}])
    deck = genanki.Deck(1577049437088, "日本語への知識欲")
    deck.add_note(genanki.Note(model=model, guid="first", fields=[
        "父の助左衛門は寡黙だった。",
        "<b>寡黙</b><br>蝉しぐれ<script>alert(1)</script>[sound:voice.wav]",
        "父[ちち]の 助左衛門[すけざえもん]は 寡黙[かもく]だった。",
    ]))
    deck.add_note(genanki.Note(model=model, guid="second", fields=["まだ新しい。", "New.", ""]))
    raw = tmp_path / "raw.apkg"
    genanki.Package(deck, media_files=[str(audio)]).write_to_file(raw)
    archive_path = tmp_path / "reference.apkg"
    database_path = tmp_path / "source.sqlite3"
    with ZipFile(raw) as source, ZipFile(archive_path, "w") as target:
        database_path.write_bytes(source.read("collection.anki2"))
        with closing(sqlite3.connect(database_path)) as database, database:
            created = int(dt.datetime(2026, 11, 20, 4).timestamp())
            database.execute("UPDATE col SET crt=?", (created,))
            (card,) = database.execute("SELECT cards.id FROM cards JOIN notes ON cards.nid=notes.id WHERE guid='first'").fetchone()
            database.execute("UPDATE cards SET queue=2,type=2,due=1,ivl=9,factor=2500 WHERE id=?", (card,))
            database.execute("INSERT INTO revlog VALUES (?,?,?,?,?,?,?,?,?)", (created*1000, card, 0, 3, 9, 3, 2500, 2000, 1))
        target.write(database_path, "collection.anki2")
        for member in ("media", "0"):
            target.writestr(member, source.read(member))
    return archive_path, audio


def test_migration_reviews_and_backup_preserve_existing_content(collection, source_package, tmp_path):
    reference, audio = source_package
    original = hashlib.sha256(reference.read_bytes()).digest()
    preview = inspect_package(reference)
    assert preview == {"decks": ["日本語への知識欲"], "notes": 2, "cards": 2, "reviews": 1, "media": 1, "skipped": 0}
    assert import_package(collection, reference)["added"] == 2
    summary = collection.summary()
    deck = summary["decks"][0]
    assert (deck["cards"], deck["due"], deck["fresh"], summary["history"]) == (2, 1, 1, 1)

    due = collection.next_card(deck["id"])["card"]
    assert "\u52a9\u5de6\u885b\u9580" in due["expression"]
    assert "<ruby>助左衛門<rt>すけざえもん</rt>" in due["reading_html"]
    assert "<b>寡黙</b>" in due["back_html"] and "<script>" not in due["back_html"]
    assert Path(due["audio"][0]["path"]).read_bytes() == audio.read_bytes()
    assert collection.browse("蝉しぐれ 助左衛門", deck["id"], 0)["cards"][0]["id"] == due["id"]

    pack = tmp_path / "backup.sqlite3"
    collection.backup(pack)
    collection.grade(due["id"], due["revision"], 3, 2000)
    with pytest.raises(ValueError, match="changed"):
        collection.grade(due["id"], due["revision"], 3, 2000)
    assert collection.summary()["history"] == 2
    repeated = import_package(collection, reference)
    assert repeated["added"] == 0 and collection.summary()["history"] == 2
    assert collection.card(due["id"])["due"] > collection.now
    assert hashlib.sha256(reference.read_bytes()).digest() == original
    restored = collection.restore(pack)
    assert restored["history"] == 1 and restored["decks"][0]["due"] == 1
    assert collection.next_card(None)["card"]["id"] == due["id"]


def test_create_edit_rate_and_enforce_new_limit(collection, tmp_path):
    runner = CliRunner()
    args = ["--database", str(collection.path)]
    result = runner.invoke(study, [*args, "create-deck", "--", "読書ノート", "Passages"])
    assert result.exit_code == 0, result.output
    deck = json.loads(result.output)["id"]
    collection.settings(1, True)
    saved = collection.save_card(deck, {
        "expression": "折り合いをつける。", "headwords": "折り合い、つける",
        "source": "Conversation notes", "reading": "折[お]り 合[あ]いをつける。",
    }, [])
    next_card = collection.next_card(None)["card"]
    assert next_card["id"] == saved["id"]
    assert "dict://%E6%8A%98" in next_card["back_html"]
    assert "Conversation notes" in next_card["back_html"]
    assert next_card["dictionary_words"] == ["折り合い", "つける"]
    assert next_card["meaning_body"] == "Conversation notes"
    assert next_card["meaning_body_html"] == "Conversation notes"
    changes = {key: next_card[key] for key in ("expression", "meaning", "reading")}
    changes["reading"] = "折り合[おりあ]いをつける。"
    edited = collection.update_card(saved["id"], next_card["revision"], deck, changes)
    assert "dict://" in edited["back_html"]
    assert "おりあ" in edited["reading_html"]
    changes.update(headwords="折り合い、案", meaning="Updated context")
    edited = collection.update_card(saved["id"], edited["revision"], deck, changes)
    assert edited["dictionary_words"] == ["折り合い", "案"]
    assert edited["meaning_body_html"] == "Updated context"
    collection.grade(saved["id"], edited["revision"], 1, 2000)
    collection.save_card(deck, {"expression": "駅まで歩く。", "translation": "Walk to the station."}, [])
    queue = collection.next_card(None)
    assert queue["card"] is None and queue["next_due"] == collection.now + 60
    collection.now += 60
    assert collection.next_card(deck)["card"]["id"] == saved["id"]
    assert collection.summary()["days"][-1]["reviews"] == 1


def test_browse_all_returns_every_match_and_searches_older_cards(collection):
    deck = collection.create_deck("Passages", "")['id']
    archived = collection.create_deck("Archived", "")['id']
    oldest = collection.save_card(deck, {"expression": "珍しい言い回し。", "translation": "An unusual phrase."}, [])['id']
    for _ in range(110):
        collection.save_card(deck, {"expression": "次の文章。", "translation": "The next phrase."}, [])
    collection.save_card(archived, {"expression": "別の文章。", "translation": "Another phrase."}, [])

    page = collection.browse("phrase", deck, 0)
    assert len(page["cards"]) == 100 and page["more"]
    assert oldest not in {card["id"] for card in page["cards"]}

    runner = CliRunner()
    args = ["--database", str(collection.path), "browse", "--all", "--deck", str(deck)]
    result = runner.invoke(study, [*args, "phrase"])
    assert result.exit_code == 0, result.output
    complete = json.loads(result.output)
    assert len(complete["cards"]) == 111 and not complete["more"]
    assert complete["cards"][-1]["id"] == oldest

    result = runner.invoke(study, [*args, "珍しい言い回し"])
    assert result.exit_code == 0, result.output
    assert [card["id"] for card in json.loads(result.output)["cards"]] == [oldest]


def test_reading_cleanup_keeps_manual_pronunciation_and_suffix():
    pytest.importorskip("fugashi")
    pytest.importorskip("unidic_lite")
    tagger = reading_tagger()
    passage = "これくらいぶっ続けに映画館に通うとさすがに映画を観たなあという手応えのようなものが感じられる。"
    reading = ("これ　くらい　ぶっつづけ　に　えい・が・かん　に　かよ−う　と　さすが　に　えい・が　を"
               "　み−た　なあ　と　いう　て・ごたえ　の　ような　もの　が　かん−じられる。（村上朝日堂の逆襲３２）")
    result = bracket_reading(passage, reading, tagger)
    assert result == ("これくらいぶっ 続[つづ]けに 映画館[えいがかん]に 通[かよ]うとさすがに 映画[えいが]を"
                      " 観[み]たなあという 手応[てごた]えのようなものが 感[かん]じられる。（村上朝日堂の逆襲３２）")
    assert bracket_reading("日本で暮らす。", "に・ほん　で　く−らす。（本（上））", tagger) == "日本[にほん]で 暮[く]らす。（本（上））"
    assert bracket_reading("日本で暮らす。", "にほん　を　でる。", tagger) is None
    assert bracket_reading("日本で暮らす。", "日本[にっぽん]で 暮[く]らす。", tagger) is None
    assert bracket_reading("日本で暮らす。", "<ruby>日本<rt>にほん</rt></ruby>", tagger) is None


def test_reading_cleanup_is_backed_up_and_idempotent(collection):
    pytest.importorskip("fugashi")
    pytest.importorskip("unidic_lite")
    deck = collection.create_deck("Japanese", "")['id']
    card_ids = [collection.save_card(deck, {"expression": "父が帰る。", "translation": "Father returns.", "reading": reading}, [])['id']
                for reading in ("ちち　が　かえ−る。（出典）", "父[ちち]が 帰[かえ]る。", "ちち　を　よんだ。", "")]
    collection.save_card(deck, {"expression": "うん。", "translation": "Yeah.", "reading": "うん。"}, [])
    preview = preview_reading_cleanup(collection)
    assert (preview["convertible"], preview["needs_review"]) == (1, 1)
    assert preview["no_kanji"] == 1
    assert len(collection.browse("", deck, 0, unbracketed=True)["cards"]) == 2
    card = collection.card(card_ids[0])
    collection.grade(card["id"], card["revision"], 3, 1000)
    due = collection.card(card["id"])["due"]
    with pytest.raises(ValueError, match="changed"):
        apply_reading_cleanup(collection, "stale preview")
    assert collection.card(card["id"])["reading"] == "ちち　が　かえ−る。（出典）"
    outcome = apply_reading_cleanup(collection, preview["token"])
    assert outcome["updated"] == 1 and outcome["needs_review"] == 1
    migrated = collection.card(card["id"])
    assert migrated["reading"] == "父[ちち]が 帰[かえ]る。（出典）"
    assert migrated["due"] == due and collection.summary()["history"] == 1
    assert [row["id"] for row in collection.browse("", deck, 0, unbracketed=True)["cards"]] == [card_ids[2]]
    assert preview_reading_cleanup(collection)["convertible"] == 0
    with closing(sqlite3.connect(outcome["backup"])) as backup:
        assert backup.execute("SELECT reading FROM notes ORDER BY id LIMIT 1").fetchone()[0] == "ちち　が　かえ−る。（出典）"
        assert backup.execute("SELECT count(*) FROM reviews").fetchone()[0] == 1
