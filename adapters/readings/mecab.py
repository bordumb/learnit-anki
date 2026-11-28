"""Propose furigana spans from the on-device MeCab/UniDic tokenizer."""

import re
import unicodedata
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from shlex import quote


@dataclass(frozen=True)
class ReadingSpan:
    text: str
    reading: str | None = None
    editable: bool = False


def _is_kanji(character: str) -> bool:
    return character in "々〆〇" or unicodedata.name(character, "").startswith((
        "CJK UNIFIED IDEOGRAPH", "CJK COMPATIBILITY IDEOGRAPH",
    ))


def has_kanji(text: str) -> bool:
    return any(map(_is_kanji, text))


def _hiragana(text: str) -> str:
    return "".join(
        chr(ord(character) - 0x60) if "ァ" <= character <= "ヶ" else character
        for character in unicodedata.normalize("NFKC", text)
    )


def _spans(surface: str, kana: str | None) -> list[ReadingSpan]:
    runs = [(is_kanji, "".join(run)) for is_kanji, run in groupby(surface, key=_is_kanji)]
    if not any(is_kanji for is_kanji, _ in runs):
        return [ReadingSpan(surface)]

    # Kana already printed in the source anchors the readings of the kanji runs.
    # Require a plausible reading for each run, and leave uncertain alignments editable.
    reading = _hiragana(kana or "")
    pattern = "".join(
        r"([ぁ-ゖー\u3099\u309a]+?)" if is_kanji else re.escape(_hiragana(text))
        for is_kanji, text in runs
    )
    match = re.fullmatch(pattern, reading)
    if match is None:
        return [ReadingSpan(text, editable=is_kanji) for is_kanji, text in runs]

    readings = iter(match.groups())
    return [ReadingSpan(text, next(readings), True) if is_kanji else ReadingSpan(text) for is_kanji, text in runs]


def reading_tagger():
    try:
        from fugashi import Tagger
        from unidic_lite import DICDIR
    except ImportError as error:
        raise ValueError("Install local furigana support with make install-furigana, then reopen the preview.") from error

    return Tagger(f"-r {quote(str(Path(DICDIR) / 'mecabrc'))} -d {quote(DICDIR)}")


def generate_reading(text: str, *, tagger=None) -> list[ReadingSpan]:
    if not has_kanji(text):
        return [ReadingSpan(text)] if text else []

    if tagger is None:
        tagger = reading_tagger()
    spans = []
    for line in text.splitlines(keepends=True):
        cursor = 0
        for word in tagger(line.rstrip("\r\n")):
            surface = word.surface
            if not surface:
                continue
            start = line.find(surface, cursor)
            if start < 0:
                # MeCab's surfaces are normally verbatim. Leave the rest reviewable if they differ.
                break
            if start > cursor:
                spans.extend(_spans(line[cursor:start], None))
            spans.extend(_spans(surface, None if word.is_unk else word.feature.kana))
            cursor = start + len(surface)
        if cursor < len(line):
            spans.extend(_spans(line[cursor:], None))
    return spans
