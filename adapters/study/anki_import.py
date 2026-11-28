"""Read the legacy-compatible Anki package format into the Learnit collection."""

import datetime as dt
import hashlib
import json
import shutil
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

from .collection import Collection, search_text, transaction
from .rendering import media_names


@contextmanager
def read_package(path: Path):
    try:
        with ZipFile(path) as package, TemporaryDirectory() as directory:
            members = set(package.namelist())
            if "collection.anki21b" in members:
                raise ValueError("Export the Anki deck with the older-version compatibility option selected.")
            member = next((name for name in ("collection.anki21", "collection.anki2") if name in members), None)
            if member is None:
                raise ValueError("This package does not contain an Anki collection.")
            local = Path(directory) / "collection"
            with local.open("wb") as target, package.open(member) as source:
                shutil.copyfileobj(source, target)
            with closing(sqlite3.connect(local.as_uri() + "?mode=ro", uri=True)) as db:
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA trusted_schema=OFF")
                item = db.execute("SELECT crt,conf,models,decks FROM col").fetchone()
                conf, models, decks = (json.loads(item[key]) for key in ("conf", "models", "decks"))
                media = json.loads(package.read("media")) if "media" in members else {}
                if not isinstance(media, dict):
                    raise ValueError("The package's media index is invalid.")
                yield package, db, item["crt"], conf, models, decks, {name: member for member, name in media.items()}
    except (BadZipFile, KeyError, TypeError, sqlite3.Error) as error:
        raise ValueError("Could not read the Anki package.") from error


def map_fields(models):
    mappings = {}
    for key, model in models.items():
        if model["type"] != 0:
            continue
        names = {field["name"].casefold(): index for index, field in enumerate(model["flds"])}
        front = names.get("expression", names.get("front"))
        back = names.get("meaning", names.get("back"))
        if front is not None and back is not None and len(model["tmpls"]) == 1:
            mappings[int(key)] = (len(names), front, back, names.get("reading"))
    return mappings


def rows_to_import(source, models, decks):
    mappings = map_fields(models)
    for row in source.execute("""
        SELECT c.id,c.nid,c.did,c.ord,c.type,c.queue,c.due,c.ivl,c.factor,c.odue,c.odid,n.guid,n.mid,n.flds
        FROM cards c JOIN notes n ON n.id=c.nid ORDER BY c.id
    """):
        deck = decks.get(str(row["odid"] or row["did"]))
        mapping = mappings.get(row["mid"])
        if deck is None or mapping is None or deck.get("dyn") or row["ord"] != 0:
            continue
        count, front, back, reading = mapping
        fields = row["flds"].split("\x1f")
        if len(fields) == count and fields[front].strip():
            yield row, deck, (fields[front], fields[back], fields[reading] if reading is not None else "")


def inspect_package(path: Path) -> dict:
    with read_package(path) as (_, db, _, _, models, decks, media):
        notes, cards, names = set(), set(), set()
        for row, deck, _ in rows_to_import(db, models, decks):
            notes.add(row["nid"])
            cards.add(row["id"])
            names.add(deck["name"])
        review_count = sum(row[0] in cards for row in db.execute("SELECT cid FROM revlog"))
        return {
            "decks": sorted(names), "notes": len(notes), "cards": len(cards), "reviews": review_count,
            "media": len(media), "skipped": db.execute("SELECT count(*) FROM cards").fetchone()[0] - len(cards),
        }


def scheduling(row, created, rollover, now):
    queue = row["queue"]
    due = row["odue"] if row["odid"] else row["due"]
    card_type = row["type"]
    if queue == -1:
        return "suspended", None, due
    if queue in (-2, -3):
        queue = 0 if card_type == 0 else 2
    tomorrow = dt.datetime.combine(dt.datetime.fromtimestamp(now).date() + dt.timedelta(days=1), dt.time(hour=rollover))
    if queue == 0 and card_type == 0:
        return "new", tomorrow.timestamp() if row["queue"] in (-2, -3) else None, due
    if queue in (1, 4) and not row["odid"]:
        return "learning", due, 0
    target_day = dt.datetime.fromtimestamp(created).date() + dt.timedelta(days=due)
    target = dt.datetime.combine(target_day, dt.time(hour=rollover)).timestamp()
    if row["queue"] in (-2, -3):
        target = max(target, tomorrow.timestamp())
    return ("learning" if queue == 3 else "review"), target, 0


def import_package(collection: Collection, path: Path) -> dict:
    summary = inspect_package(path)
    if not summary["cards"]:
        raise ValueError("This package has no supported single-sided Expression/Meaning or Front/Back cards.")
    with read_package(path) as (package, source, created, conf, models, decks, manifest):
        saved_media, imported_decks, card_ids = {}, {}, {}
        rollover = conf.get("rollover")
        if not isinstance(rollover, int) or not 0 <= rollover < 24:
            rollover = dt.datetime.fromtimestamp(created).hour
        db = collection.db
        inserted = 0
        with transaction(db):
            for row, deck, fields in rows_to_import(source, models, decks):
                deck_name = deck["name"]
                if deck_name not in imported_decks:
                    db.execute("INSERT OR IGNORE INTO decks(name,description) VALUES (?,?)", (deck_name, deck.get("desc") or ""))
                    imported_decks[deck_name] = db.execute("SELECT id FROM decks WHERE name=?", (deck_name,)).fetchone()[0]
                note = db.execute("SELECT id FROM notes WHERE guid=?", (row["guid"],)).fetchone()
                if note is None:
                    note_id = db.execute(
                        "INSERT INTO notes(guid,expression,meaning,reading,searchable) VALUES (?,?,?,?,?)",
                        (row["guid"], *fields, search_text(*fields)),
                    ).lastrowid
                    for name in media_names(*fields):
                        saved_name = _save_media(db, package, manifest, saved_media, name)
                        if saved_name:
                            db.execute("INSERT INTO note_media VALUES (?,?,?)", (note_id, name, saved_name))
                else:
                    note_id = note[0]
                state, due, position = scheduling(row, created, rollover, collection.now)
                cursor = db.execute("""
                    INSERT OR IGNORE INTO cards(note_id,deck_id,ordinal,state,due,position,interval,ease)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (note_id, imported_decks[deck_name], row["ord"], state, due, position, row["ivl"], row["factor"] or 2500))
                inserted += cursor.rowcount
                card_ids[row["id"]] = db.execute(
                    "SELECT id FROM cards WHERE note_id=? AND ordinal=?", (note_id, row["ord"]),
                ).fetchone()[0]
            introductions = set()
            reviews = []
            for row in source.execute("SELECT id,cid,ease,ivl,lastIvl,factor,time,type FROM revlog ORDER BY id"):
                if row["cid"] in card_ids:
                    reviews.append((
                        card_ids[row["cid"]], row["id"], row["ease"], row["ivl"], row["lastIvl"],
                        row["factor"], row["time"], row["type"], int(row["type"] == 0 and row["cid"] not in introductions),
                    ))
                    introductions.add(row["cid"])
            db.executemany("INSERT OR IGNORE INTO reviews VALUES (?,?,?,?,?,?,?,?,?)", reviews)
        return {**summary, "added": inserted}


def _save_media(db, package, manifest, cached, name):
    if name not in cached:
        member = manifest.get(name)
        if member is None:
            return None
        if package.getinfo(member).file_size > 200_000_000:
            raise ValueError(f"Media file {name} exceeds the 200 MB import limit.")
        data = package.read(member)
        suffix = Path(name).suffix.lower()
        target = "anki-" + hashlib.sha256(data).hexdigest() + suffix
        db.execute("INSERT OR IGNORE INTO media VALUES (?,?)", (target, data))
        cached[name] = target
    return cached[name]
