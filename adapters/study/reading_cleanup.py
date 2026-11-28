"""Align older, manually entered kana to the written Japanese passage."""

import datetime as dt
import hashlib
import json
import re
import sqlite3
import unicodedata
import uuid
from contextlib import closing
from dataclasses import dataclass
from functools import lru_cache
from itertools import groupby, pairwise

from adapters.readings.mecab import _hiragana, generate_reading, has_kanji, reading_tagger

from .collection import Collection, encoded, search_text, transaction
from .rendering import READING_ANNOTATION, plain, unbracketed_reading

_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
_KANA = re.compile(r"[ぁ-ゖゝゞー\u3099\u309a]+")


@dataclass(frozen=True)
class Unit:
    text: str
    preferred: str
    kanji: bool


def _compact(text):
    """Return comparable text and boundaries explicitly marked by the original author."""
    chunks = []
    boundaries = {0}
    for character in _hiragana(text):
        if character in "・·":
            continue
        if character.isspace() or character in "-−‐‑" or unicodedata.category(character).startswith("P"):
            boundaries.add(len(chunks))
        else:
            chunks.append(character)
    boundaries.add(len(chunks))
    return "".join(chunks), dict(pairwise(sorted(boundaries)))


def _units(spans, *, group_kanji=True):
    units = []
    key = lambda pair: (pair[1].editable, pair[0] if pair[1].editable and not group_kanji else 0)
    for (kanji, _), group in groupby(enumerate(spans), key=key):
        run = [span for _, span in group]
        text = "".join(span.text for span in run)
        if kanji:
            preferred = "".join(span.reading for span in run) if all(span.reading for span in run) else ""
        else:
            preferred = text
        units.append(Unit(text, _compact(preferred)[0], kanji))
    return units


def _align(units, typed):
    manual, boundaries = _compact(typed)
    if not manual:
        return None

    @lru_cache(maxsize=None)
    def align(index, start):
        if index == len(units):
            return (0, ((),)) if start == len(manual) else None
        unit = units[index]
        if not unit.kanji:
            if not manual.startswith(unit.preferred, start):
                return None
            return align(index + 1, start + len(unit.preferred))

        # The default reading is evidence for the split; the actual kana come from the
        # user's field. A different reading needs a word boundary marked on both sides.
        options = []
        if unit.preferred and manual.startswith(unit.preferred, start):
            options.append((start + len(unit.preferred), 0))
        explicit_end = boundaries.get(start)
        if explicit_end is not None and 0 < explicit_end - start <= 14:
            if manual[start:explicit_end] != unit.preferred and _KANA.fullmatch(manual[start:explicit_end]):
                options.append((explicit_end, 1))
        best = None
        for stop, penalty in options:
            remainder = align(index + 1, stop)
            if remainder is None:
                continue
            cost, matches = remainder
            cost += penalty
            candidates = tuple((manual[start:stop], *match) for match in matches)
            if best is None or cost < best[0]:
                best = (cost, candidates)
            elif cost == best[0]:
                best = (cost, (best[1] + candidates)[:2])
        return best

    found = align(0, 0)
    return iter(found[1][0]) if found is not None and len(found[1]) == 1 else None


def _reading_bodies(typed):
    """Try the full reading first, then detach any trailing source annotations."""
    body = typed
    while body:
        yield body, typed[len(body):]
        if body[-1] not in ")）":
            return
        depth = 0
        for index in range(len(body) - 1, -1, -1):
            character = body[index]
            if character in ")）":
                depth += 1
            elif character in "(（":
                depth -= 1
                if depth == 0:
                    body = body[:index].rstrip()
                    break
        else:
            return


def _format(units, readings):
    pieces = []
    for kanji, group in groupby(units, key=lambda unit: unit.kanji):
        run = list(group)
        text = "".join(unit.text for unit in run)
        if kanji:
            if pieces and not pieces[-1][-1].isspace():
                pieces.append(" ")
            kana = "".join(next(readings) for _ in run)
            pieces.append(f"{text}[{kana}]")
        else:
            pieces.append(text)
    return "".join(pieces)


def bracket_reading(expression, reading, tagger):
    # Source passages are plain text by this point; preserve the original Reading
    # field if it has embedded formatting or if it is already annotated.
    if not unbracketed_reading(reading) or "<" in _BREAK.sub("", reading):
        return None
    expression, typed = plain(expression), plain(reading)
    if not expression or READING_ANNOTATION.search(expression):
        return None
    spans = generate_reading(expression, tagger=tagger)
    variants = [_units(spans), _units(spans, group_kanji=False)]
    for body, suffix in _reading_bodies(typed):
        for units in variants:
            if len(units) <= 200 and any(unit.kanji for unit in units):
                readings = _align(units, body)
                if readings is not None:
                    return _format(units, readings) + suffix
    return None


def _plan(db):
    rows = db.execute("SELECT id, expression, meaning, reading FROM notes WHERE reading<>'' ORDER BY id")
    tagger = None
    changes = []
    examples = []
    pending = 0
    kana_only = 0
    token = hashlib.sha256()
    for row in rows:
        if not unbracketed_reading(row["reading"]):
            continue
        if not has_kanji(plain(row["expression"])):
            kana_only += 1
            continue
        if tagger is None:
            tagger = reading_tagger()
        result = bracket_reading(row["expression"], row["reading"], tagger)
        if result is None:
            pending += 1
            continue
        stored = encoded(result)
        changes.append((stored, search_text(row["expression"], row["meaning"], stored), row["id"]))
        token.update(json.dumps([row["id"], row["expression"], row["reading"], stored], ensure_ascii=False).encode())
        if len(examples) < 3 and len(result) < 220:
            examples.append({"id": row["id"], "before": plain(row["reading"]), "after": result})
    return changes, {
        "convertible": len(changes), "needs_review": pending, "no_kanji": kana_only,
        "examples": examples, "token": token.hexdigest(),
    }


def preview_reading_cleanup(collection):
    return _plan(collection.db)[1]


def apply_reading_cleanup(collection, token):
    with transaction(collection.db):
        changes, report = _plan(collection.db)
        if report["token"] != token:
            raise ValueError("The collection changed. Preview the reading cleanup again.")
        if not changes:
            return {"updated": 0, "backup": None, "needs_review": report["needs_review"]}
        stamp = dt.datetime.now().strftime("%Y-%m-%d %H%M%S")
        destination = collection.path.parent / "Backups" / f"Reading Cleanup {stamp}-{uuid.uuid4().hex[:8]}.sqlite3"
        destination.parent.mkdir(mode=0o700, exist_ok=True)
        # BEGIN IMMEDIATE excludes other writers. A separate reader can then
        # back up the exact state that precedes the transaction.
        with closing(sqlite3.connect(collection.path.resolve().as_uri() + "?mode=ro", uri=True)) as reader:
            Collection(reader, collection.path).backup(destination)
        collection.db.executemany("UPDATE notes SET reading=?,searchable=? WHERE id=?", changes)
        collection.db.executemany("UPDATE cards SET revision=revision+1 WHERE note_id=?", ((note,) for _, _, note in changes))
    return {"updated": len(changes), "backup": str(destination), "needs_review": report["needs_review"]}
