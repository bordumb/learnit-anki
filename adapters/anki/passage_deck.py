"""Add a passage using the deck and note type from an existing Anki package."""

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from hashlib import file_digest, sha256
from html import escape
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

import genanki

from adapters.dictionary.pointers import parse_headwords, with_dictionary_links


class _OriginalNoteType(genanki.Model):
    def __init__(self, definition: dict):
        super().__init__(
            model_id=int(definition["id"]), name=definition["name"],
            fields=definition["flds"], templates=definition["tmpls"],
        )
        self.definition = definition

    def to_json(self, timestamp, deck_id):
        return self.definition


@dataclass(frozen=True)
class PassageDeck:
    deck: dict
    note_type: dict

    @classmethod
    def load(cls, path: Path) -> "PassageDeck":
        with TemporaryDirectory() as directory:
            try:
                with ZipFile(path) as package:
                    if any(name in package.namelist() for name in ("collection.anki21", "collection.anki21b")):
                        raise ValueError("Export the reference deck with Anki's older-version compatibility option.")
                    if "collection.anki2" not in package.namelist():
                        raise ValueError("The reference package is missing its Anki collection.")
                    database = package.extract("collection.anki2", directory)
                with closing(sqlite3.connect(Path(database).as_uri() + "?mode=ro", uri=True)) as db:
                    db.execute("PRAGMA trusted_schema=OFF")
                    models, decks = map(json.loads, db.execute("SELECT models, decks FROM col").fetchone())
                    links = db.execute(
                        "SELECT DISTINCT cards.did, notes.mid FROM cards JOIN notes ON cards.nid=notes.id"
                    ).fetchall()

                matches = []
                for deck_id, model_id in links:
                    deck, model = decks[str(deck_id)], models[str(model_id)]
                    fields = [field["name"] for field in model["flds"]]
                    if (fields == ["Expression", "Meaning", "Reading"] and model["type"] == 0
                            and len(model["tmpls"]) == 1 and not deck["dyn"]):
                        matches.append(cls(deck, model))
                if len(matches) != 1:
                    raise ValueError("Choose a package with one deck using Expression, Meaning, and Reading.")
                return matches[0]
            except (BadZipFile, KeyError, sqlite3.Error, TypeError) as error:
                raise ValueError("Could not read the reference Anki package.") from error

    def export(self, draft: dict, output: Path, *, pronunciation: Path | None = None,
               recording: Path | None = None) -> Path:
        values = {}
        for field in ("expression", "definitions", "source", "context", "translation", "reading", "headwords"):
            value = draft.get(field, "")
            if not isinstance(value, str):
                raise ValueError(f"{field} must be text.")
            # Anki uses the unit separator internally between note fields.
            if any(ord(character) < 32 and character not in "\t\r\n" for character in value):
                raise ValueError(f"{field} contains a control character. Paste it again as plain text.")
            values[field] = value.strip()
        if not values["expression"]:
            raise ValueError("Enter the full Japanese passage.")
        headwords = parse_headwords(values["headwords"])
        if not headwords and not any(values[key] for key in ("definitions", "context", "translation")):
            raise ValueError("Add a definition, translation, context note, or dictionary link.")

        def format_field(text: str) -> str:
            return escape(text).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")

        body = "<br><br>".join(
            format_field(values[key]) for key in ("definitions", "source", "context", "translation")
            if values[key]
        )
        meaning = with_dictionary_links(headwords, body)
        expression = format_field(values["expression"])
        reading = format_field(values["reading"])
        note_type = _OriginalNoteType(self.note_type)
        deck = genanki.Deck(self.deck["id"], self.deck["name"], self.deck.get("desc", ""))
        identity = ["learnit-passage", str(deck.deck_id), str(note_type.model_id), expression, meaning]
        if reading:
            # Separate new reading-bearing notes from earlier exports that may have been annotated in Anki.
            identity.append("with-reading")
        output.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=output) as directory:
            media_paths = []
            for label, kind, path in (
                ("Pronunciation", "pronunciation", pronunciation),
                ("Source audio", "recording", recording),
            ):
                if path is None:
                    continue
                if path.stat().st_size == 0:
                    raise ValueError(f"{label} is empty.")
                suffix = path.suffix.lower()
                if suffix not in {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".opus", ".flac", ".aiff", ".aif", ".caf", ".wma"}:
                    raise ValueError(f"Unsupported format for {label.lower()}: {suffix or 'missing extension'}.")
                staged_audio = Path(directory) / f"{kind}{suffix}"
                copyfile(path, staged_audio)
                with staged_audio.open("rb") as audio:
                    digest = file_digest(audio, "sha256").hexdigest()[:24]
                media = Path(directory) / f"learnit-{kind}-{digest}{suffix}"
                staged_audio.rename(media)
                media_paths.append(media)
                meaning += f"<br><br>{label} [sound:{media.name}]"

            # Audio variants are new notes, so they cannot overwrite readings added in Anki.
            guid = genanki.guid_for(*identity, *(media.name for media in media_paths))
            deck.add_note(genanki.Note(model=note_type, fields=[expression, meaning, reading], guid=guid))
            filename = f"learnit-passage-{sha256(guid.encode()).hexdigest()[:16]}.apkg"
            destination = (output / filename).resolve()
            staged = Path(directory) / filename
            genanki.Package(deck, media_files=[str(media) for media in media_paths]).write_to_file(staged)
            staged.replace(destination)
        return destination
