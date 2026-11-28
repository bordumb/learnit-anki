"""SQLite collection and review scheduling for the local Learnit study app."""

import datetime as dt
import hashlib
import html
import json
import sqlite3
import time
import uuid
from contextlib import closing, contextmanager
from pathlib import Path

from adapters.dictionary.pointers import parse_headwords, split_dictionary_links, with_dictionary_links
from adapters.readings.mecab import has_kanji

from .rendering import plain, render, unbracketed_reading

SCHEMA = """
CREATE TABLE IF NOT EXISTS decks(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notes(
    id INTEGER PRIMARY KEY, guid TEXT NOT NULL UNIQUE, expression TEXT NOT NULL,
    meaning TEXT NOT NULL, reading TEXT NOT NULL, searchable TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cards(
    id INTEGER PRIMARY KEY, note_id INTEGER NOT NULL REFERENCES notes,
    deck_id INTEGER NOT NULL REFERENCES decks, ordinal INTEGER NOT NULL,
    state TEXT NOT NULL, due REAL, position INTEGER NOT NULL, interval INTEGER NOT NULL,
    ease INTEGER NOT NULL, revision INTEGER NOT NULL DEFAULT 0, UNIQUE(note_id, ordinal)
);
CREATE TABLE IF NOT EXISTS reviews(
    card_id INTEGER NOT NULL REFERENCES cards, stamp INTEGER NOT NULL, grade INTEGER NOT NULL,
    interval INTEGER NOT NULL, previous_interval INTEGER NOT NULL, ease INTEGER NOT NULL,
    elapsed INTEGER NOT NULL, kind INTEGER NOT NULL, introduced INTEGER NOT NULL,
    PRIMARY KEY (card_id, stamp)
);
CREATE TABLE IF NOT EXISTS media(name TEXT PRIMARY KEY, data BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS note_media(
    note_id INTEGER NOT NULL REFERENCES notes, label TEXT NOT NULL, filename TEXT NOT NULL REFERENCES media,
    PRIMARY KEY(note_id,label)
);
CREATE TABLE IF NOT EXISTS preferences(key TEXT PRIMARY KEY, value INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS cards_queue ON cards(deck_id, state, due, position);
CREATE INDEX IF NOT EXISTS reviews_stamp ON reviews(stamp);
PRAGMA user_version=1;
"""
_CARD = """
    SELECT c.id, c.note_id, c.deck_id, c.state, c.due, c.interval, c.ease, c.revision,
           n.expression, n.meaning, n.reading
    FROM cards c JOIN notes n ON n.id=c.note_id
"""
_AUDIO_FORMATS = {".aac", ".aif", ".aiff", ".caf", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav", ".wma"}


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA trusted_schema=OFF")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            db.executescript(SCHEMA)
        elif version != 1:
            raise ValueError("This collection was saved in a newer version of Learnit.")
        return db
    except Exception:
        db.close()
        raise


@contextmanager
def transaction(db: sqlite3.Connection):
    db.execute("BEGIN IMMEDIATE")
    with db:
        yield


def encoded(text: str) -> str:
    return html.escape(text).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


def search_text(*values: str) -> str:
    return " ".join(plain(value) for value in values).casefold()


def day_boundary(now: float) -> dt.datetime:
    local = dt.datetime.fromtimestamp(now)
    day = local.date() - dt.timedelta(days=local.hour < 4)
    return dt.datetime.combine(day, dt.time(hour=4))


class Collection:
    def __init__(self, db: sqlite3.Connection, path: Path, now: float | None = None):
        self.db = db
        self.path = path
        self.now = time.time() if now is None else now

    def preferences(self) -> dict:
        return {
            "new_limit": 20, "auto_audio": 0,
            **{row["key"]: row["value"] for row in self.db.execute("SELECT key,value FROM preferences")},
        }

    def settings(self, new_limit: int, auto_audio: bool) -> dict:
        with self.db:
            self.db.executemany("INSERT OR REPLACE INTO preferences VALUES (?,?)", [
                ("new_limit", min(999, max(0, new_limit))), ("auto_audio", int(auto_audio)),
            ])
        return self.preferences()

    def summary(self) -> dict:
        decks = [dict(row) for row in self.db.execute("""
            SELECT d.id,d.name,d.description, COUNT(c.id) AS cards,
                SUM(CASE WHEN c.state IN ('review','learning') AND c.due<=? THEN 1 ELSE 0 END) AS due,
                SUM(CASE WHEN c.state='new' THEN 1 ELSE 0 END) AS fresh
            FROM decks d LEFT JOIN cards c ON c.deck_id=d.id
            GROUP BY d.id ORDER BY d.name COLLATE NOCASE
        """, (self.now,))]
        today = day_boundary(self.now)
        days = []
        for offset in range(6, -1, -1):
            start = today - dt.timedelta(days=offset)
            end = start + dt.timedelta(days=1)
            (reviews,) = self.db.execute(
                "SELECT count(*) FROM reviews WHERE stamp>=? AND stamp<?",
                (int(start.timestamp() * 1000), int(end.timestamp() * 1000)),
            ).fetchone()
            days.append({"label": start.date().isoformat(), "reviews": reviews})
        scheduled = self.db.execute("SELECT count(*) FROM cards WHERE state IN ('review','learning') AND due>?", (self.now,)).fetchone()[0]
        return {
            "decks": decks, "days": days, "scheduled": scheduled, "preferences": self.preferences(),
            "history": self.db.execute("SELECT count(*) FROM reviews").fetchone()[0],
        }

    def create_deck(self, name: str, description: str) -> dict:
        name = name.strip()
        if not name:
            raise ValueError("Enter a deck name.")
        try:
            with self.db:
                cursor = self.db.execute("INSERT INTO decks(name,description) VALUES (?,?)", (name, description.strip()))
        except sqlite3.IntegrityError as error:
            raise ValueError("A deck with that name already exists.") from error
        return {"id": cursor.lastrowid}

    def browse(self, query: str, deck: int | None, offset: int, unbracketed: bool = False, *, all_matches: bool = False) -> dict:
        terms = query.casefold().split()
        conditions = ["instr(n.searchable, ?) > 0"] * len(terms)
        parameters = list(terms)
        if deck is not None:
            conditions.append("c.deck_id=?")
            parameters.append(deck)
        if unbracketed:
            self.db.create_function("needs_reading_markup", 2,
                                    lambda expression, reading: unbracketed_reading(reading) and has_kanji(plain(expression)),
                                    deterministic=True)
            conditions.append("n.reading<>'' AND needs_reading_markup(n.expression,n.reading)")
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        sql = """
            SELECT c.id, c.deck_id, c.state, c.due, n.expression
            FROM cards c JOIN notes n ON n.id=c.note_id
        """ + where + " ORDER BY c.id DESC"
        if not all_matches:
            sql += " LIMIT 101 OFFSET ?"
            parameters.append(max(0, offset))
        rows = self.db.execute(sql, parameters).fetchall()
        more = not all_matches and len(rows) > 100
        if more:
            rows.pop()
        return {"cards": [{
            "id": row["id"], "deck_id": row["deck_id"], "expression": plain(row["expression"]),
            "state": row["state"], "due": row["due"],
        } for row in rows], "more": more}

    def card(self, card_id: int) -> dict:
        row = self.db.execute(_CARD + " WHERE c.id=?", (card_id,)).fetchone()
        if row is None:
            raise ValueError("This card is no longer in the collection.")
        return self._card_details(row)

    def next_card(self, deck: int | None) -> dict:
        where, parameters = (" AND c.deck_id=?", (deck,)) if deck is not None else ("", ())
        due = self.db.execute(
            _CARD + " WHERE c.state IN ('learning','review') AND c.due<=?" + where
            + " ORDER BY c.state='learning' DESC,c.due,c.id LIMIT 1", (self.now, *parameters),
        ).fetchone()
        if due is not None:
            return {"card": self._card_details(due)}
        if self._new_slot_available():
            fresh = self.db.execute(
                _CARD + " WHERE c.state='new' AND (c.due IS NULL OR c.due<=?)" + where + " ORDER BY c.position,c.id LIMIT 1",
                (self.now, *parameters),
            ).fetchone()
            if fresh is not None:
                return {"card": self._card_details(fresh)}
        next_due = self.db.execute(
            "SELECT min(c.due) FROM cards c WHERE c.state IN ('review','learning') AND c.due>?" + where,
            (self.now, *parameters),
        ).fetchone()[0]
        return {"card": None, "next_due": next_due}

    def _new_slot_available(self) -> bool:
        count = self.db.execute("SELECT count(*) FROM reviews WHERE introduced=1 AND stamp>=?",
                                (int(day_boundary(self.now).timestamp() * 1000),)).fetchone()[0]
        return count < self.preferences()["new_limit"]

    def _card_details(self, row: sqlite3.Row) -> dict:
        fields = {field: plain(row[field], keep_sound=True) for field in ("expression", "meaning", "reading")}
        words, meaning_body = split_dictionary_links(row["meaning"])
        meaning_html = self._field_html(row["note_id"], meaning_body)
        tracks = [(item["label"], item["filename"]) for item in self.db.execute(
            "SELECT label,filename FROM note_media WHERE note_id=? ORDER BY label", (row["note_id"],),
        )]
        audio = []
        for label, filename in tracks:
            if Path(filename).suffix.lower() in _AUDIO_FORMATS:
                url = self._cached_media(filename)
                if url:
                    audio.append({"label": label, "path": str(url)})
        return {
            **fields, "id": row["id"], "deck_id": row["deck_id"], "state": row["state"], "due": row["due"],
            "revision": row["revision"], "audio": audio,
            "front_html": self._field_html(row["note_id"], row["expression"]),
            "back_html": with_dictionary_links(words, meaning_html),
            "dictionary_words": words,
            "meaning_body": plain(meaning_body, keep_sound=True) if words else None,
            "meaning_body_html": meaning_html if words else None,
            "reading_html": self._field_html(row["note_id"], row["reading"], ruby=True),
            "grades": [self._grade_result(row, grade)[3] for grade in range(1, 5)],
        }

    def _field_html(self, note_id: int, value: str, ruby: bool = False) -> str:
        def lookup(name: str) -> bytes | None:
            row = self.db.execute("""
                SELECT m.data FROM note_media a JOIN media m ON m.name=a.filename
                WHERE a.note_id=? AND a.label=? AND length(m.data)<=8000000
            """, (note_id, name)).fetchone()
            return row[0] if row is not None else None
        return render(value, lookup, ruby=ruby)

    def _cached_media(self, name: str) -> Path | None:
        row = self.db.execute("SELECT data FROM media WHERE name=?", (name,)).fetchone()
        if row is None:
            return None
        suffix = Path(name).suffix.lower()
        data = row[0]
        cache = self.path.parent / "Playback"
        cache.mkdir(exist_ok=True)
        target = cache / (hashlib.sha256(data).hexdigest() + suffix)
        if not target.exists():
            temporary = cache / uuid.uuid4().hex
            try:
                temporary.write_bytes(data)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        return target

    def save_card(self, deck: int, draft: dict, audio: list[tuple[str, Path]]) -> dict:
        expression = draft["expression"].strip()
        content = [draft.get(key, "").strip() for key in ("definitions", "source", "context", "translation")]
        reading = draft.get("reading", "").strip()
        headwords = parse_headwords(draft.get("headwords", ""))
        if not expression or not any((headwords, content[0], content[2], content[3])):
            raise ValueError("Enter the passage and add a dictionary link, definition, context note, or translation.")
        expression, reading = encoded(expression), encoded(reading)
        meaning = with_dictionary_links(headwords, "<br><br>".join(encoded(block) for block in content if block))
        with transaction(self.db):
            if not self.db.execute("SELECT 1 FROM decks WHERE id=?", (deck,)).fetchone():
                raise ValueError("Choose a deck before saving.")
            cursor = self.db.execute(
                "INSERT INTO notes(guid,expression,meaning,reading,searchable) VALUES (?,?,?,?,?)",
                ("learnit-" + uuid.uuid4().hex, expression, meaning, reading, search_text(expression, meaning, reading)),
            )
            note = cursor.lastrowid
            for label, path in audio:
                suffix = path.suffix.lower()
                if suffix not in _AUDIO_FORMATS:
                    raise ValueError("This audio format is unsupported.")
                data = path.read_bytes()
                if not data:
                    raise ValueError("The selected audio file is empty.")
                name = "learnit-" + hashlib.sha256(data).hexdigest() + suffix
                self.db.execute("INSERT OR IGNORE INTO media VALUES (?,?)", (name, data))
                self.db.execute("INSERT INTO note_media VALUES (?,?,?)", (note, label, name))
            position = self.db.execute("SELECT COALESCE(MAX(position),0)+1 FROM cards WHERE deck_id=?", (deck,)).fetchone()[0]
            card = self.db.execute(
                "INSERT INTO cards(note_id,deck_id,ordinal,state,position,interval,ease) VALUES (?,?,0,'new',?,0,2500)",
                (note, deck, position),
            ).lastrowid
        return {"id": card}

    def update_card(self, card_id: int, revision: int, deck: int, draft: dict) -> dict:
        with transaction(self.db):
            row = self.db.execute(_CARD + " WHERE c.id=?", (card_id,)).fetchone()
            if row is None or row["revision"] != revision:
                raise ValueError("This card changed. Reopen the card before editing.")
            if not draft["expression"].strip():
                raise ValueError("Enter the passage.")
            fields = [
                row[field] if draft[field] == plain(row[field], keep_sound=True) else encoded(draft[field])
                for field in ("expression", "meaning", "reading")
            ]
            if "headwords" in draft:
                _, prior_body = split_dictionary_links(row["meaning"])
                body = prior_body if draft["meaning"] == plain(prior_body, keep_sound=True) else encoded(draft["meaning"])
                fields[1] = with_dictionary_links(parse_headwords(draft["headwords"]), body)
            self.db.execute("UPDATE notes SET expression=?,meaning=?,reading=?,searchable=? WHERE id=?",
                            (*fields, search_text(*fields), row["note_id"]))
            self.db.execute("UPDATE cards SET revision=revision+1 WHERE note_id=?", (row["note_id"],))
            self.db.execute("UPDATE cards SET deck_id=? WHERE id=?", (deck, card_id))
        return self.card(card_id)

    def _grade_result(self, card: sqlite3.Row, grade: int) -> tuple[str, float, int, str, int]:
        interval = max(card["interval"], 1)
        ease = max(card["ease"], 1300)
        if grade == 1:
            if card["state"] == "review":
                interval = max(1, round(interval * 0.25))
            return "learning", self.now + 60, interval, "1 min", max(1300, ease - 200)
        if card["state"] != "review" and grade == 2:
            return "learning", self.now + 360, interval, "6 min", ease
        if card["state"] != "review":
            days = 4 if grade == 4 else interval
        else:
            hard = max(interval + 1, round(interval * 1.2))
            good = max(hard + 1, round(interval * ease / 1000))
            easy = max(good + 1, round(good * 1.3))
            days = (hard, good, easy)[grade - 2]
        days = min(days, 36_500)
        target = day_boundary(self.now) + dt.timedelta(days=days)
        updated_ease = max(1300, ease + {2: -150, 3: 0, 4: 150}[grade])
        return "review", target.timestamp(), days, f"{days} d", updated_ease

    def grade(self, card_id: int, revision: int, grade: int, elapsed: int) -> dict:
        if grade not in range(1, 5):
            raise ValueError("Choose a rating from 1 to 4.")
        with transaction(self.db):
            row = self.db.execute(_CARD + " WHERE c.id=?", (card_id,)).fetchone()
            if row is None or row["revision"] != revision or row["state"] == "suspended":
                raise ValueError("The card changed. Reload the review queue.")
            if row["due"] is not None and row["due"] > self.now:
                raise ValueError("This card is already scheduled for later.")
            if row["state"] == "new" and not self._new_slot_available():
                raise ValueError("The daily limit for new cards has been reached.")
            state, due, interval, label, ease = self._grade_result(row, grade)
            introduced = int(row["state"] == "new")
            stamp = int(self.now * 1000)
            self.db.execute("""
                INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?,?)
            """, (card_id, stamp, grade, interval if state == "review" else -int(due - self.now),
                  row["interval"], ease, max(0, elapsed), 0 if introduced else int(row["state"] == "review"), introduced))
            self.db.execute("UPDATE cards SET state=?,due=?,interval=?,ease=?,revision=revision+1 WHERE id=?",
                            (state, due, interval, ease, card_id))
        return {"label": label}

    def backup(self, destination: Path) -> dict:
        if destination.resolve() == self.path.resolve():
            raise ValueError("Choose a new path for the backup.")
        temporary = destination.with_name("." + uuid.uuid4().hex + ".sqlite3")
        try:
            with closing(sqlite3.connect(temporary)) as target:
                self.db.backup(target)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return {"path": str(destination)}

    def restore(self, source: Path) -> dict:
        if source.resolve() == self.path.resolve():
            raise ValueError("Choose a previously saved Learnit backup.")
        with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as backup:
            backup.execute("PRAGMA trusted_schema=OFF")
            schema_query = "SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name"
            expected = [tuple(row) for row in self.db.execute(schema_query)]
            if backup.execute(schema_query).fetchall() != expected:
                raise ValueError("Choose a Learnit collection backup from this version of the app.")
            if backup.execute("PRAGMA quick_check").fetchone()[0] != "ok" or backup.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("This collection backup is damaged.")
            backup.backup(self.db)
        return self.summary()
