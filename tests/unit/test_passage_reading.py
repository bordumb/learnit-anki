import json
import sys
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from adapters.readings.mecab import generate_reading
from infrastructure.cli.main import cli


def test_passage_reading_cli_preserves_surface_and_allows_unknown_kanji_correction(monkeypatch):
    words = {
        "父の 助左衛門、男らしい。": [
            ("父", "チチ"), ("の", "ノ"), ("助左衛門", None), ("、", None),
            ("男らしい", "オトコラシイ"), ("。", None),
        ],
        "取り扱い": [("取り扱い", "トリアツカイ")],
    }

    def tagger(_):
        return lambda text: [
            SimpleNamespace(surface=surface, is_unk=kana is None, feature=SimpleNamespace(kana=kana))
            for surface, kana in words[text]
        ]

    monkeypatch.setitem(sys.modules, "fugashi", SimpleNamespace(Tagger=tagger))
    monkeypatch.setitem(sys.modules, "unidic_lite", SimpleNamespace(DICDIR="/local/dictionary"))
    source = "父の 助左衛門、男らしい。\n取り扱い"
    result = CliRunner().invoke(cli, ["furigana", "-"], input=source)
    assert result.exit_code == 0, result.output
    spans = json.loads(result.output)
    assert "".join(span["text"] for span in spans) == source
    assert [(span["text"], span["reading"]) for span in spans if span["editable"]] == [
        ("父", "ちち"), ("助左衛門", None), ("男", "おとこ"), ("取", "と"), ("扱", "あつか"),
    ]


def test_me_cab_unidic_uses_kana_form_for_furigana():
    pytest.importorskip("fugashi")
    pytest.importorskip("unidic_lite")
    source = "父は寡黙だが男らしい人間だった。"
    spans = generate_reading(source)
    assert "".join(span.text for span in spans) == source
    assert {span.text: span.reading for span in spans if span.editable} == {
        "父": "ちち", "寡黙": "かもく", "男": "おとこ", "人間": "にんげん",
    }


def test_dictionary_headwords_uses_passage_context():
    pytest.importorskip("fugashi")
    pytest.importorskip("unidic_lite")
    source = "明日の会議は午後3時からです。\n資料をコピーして、受付に置いてください。\n明日また会議です。"
    result = CliRunner().invoke(cli, ["dictionary-headwords", "-"], input=source)
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == ["明日", "会議", "午後", "資料", "コピー", "受付", "置く", "また"]
