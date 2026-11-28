"""Commands used by the macOS study workspace."""

import json
import sqlite3
from contextlib import closing
from functools import wraps
from pathlib import Path

import click

from adapters.study.anki_import import import_package, inspect_package
from adapters.study.collection import Collection, connect
from adapters.study.reading_cleanup import apply_reading_cleanup, preview_reading_cleanup

EXISTING_FILE = click.Path(exists=True, dir_okay=False, path_type=Path)
DESTINATION = click.Path(dir_okay=False, path_type=Path)


@click.group()
@click.option("--database", type=DESTINATION, required=True)
@click.pass_context
def study(context, database):
    """Manage a local flashcard collection."""
    try:
        context.obj = Collection(context.with_resource(closing(connect(database))), database)
    except (OSError, sqlite3.Error, ValueError) as error:
        raise click.ClickException(str(error)) from error


def operation(function):
    @click.pass_obj
    @wraps(function)
    def run(collection, *args, **kwargs):
        try:
            result = function(collection, *args, **kwargs)
        except (OSError, sqlite3.Error, ValueError, KeyError) as error:
            raise click.ClickException(str(error)) from error
        click.echo(json.dumps(result, ensure_ascii=False))
    return run


@study.command()
@operation
def summary(collection):
    return collection.summary()


@study.command()
@click.argument("name")
@click.argument("description")
@operation
def create_deck(collection, name, description):
    return collection.create_deck(name, description)


@study.command()
@click.option("--deck", type=int)
@click.option("--offset", type=int, default=0)
@click.option("--unbracketed", is_flag=True, help="Only show passages with kanji and an unbracketed reading.")
@click.option("--all", "all_matches", is_flag=True, help="Return every match as a card summary.")
@click.argument("query")
@operation
def browse(collection, query, deck, offset, unbracketed, all_matches):
    return collection.browse(query, deck, offset, unbracketed, all_matches=all_matches)


@study.command()
@click.argument("card_id", type=int)
@operation
def card(collection, card_id):
    return collection.card(card_id)


@study.command()
@click.option("--deck", type=int)
@operation
def next_card(collection, deck):
    return collection.next_card(deck)


@study.command()
@click.argument("card_id", type=int)
@click.argument("revision", type=int)
@click.argument("rating", type=int)
@click.argument("elapsed", type=int)
@operation
def grade(collection, card_id, revision, rating, elapsed):
    return collection.grade(card_id, revision, rating, elapsed)


@study.command()
@click.option("--pronunciation", type=EXISTING_FILE)
@click.option("--recording", type=EXISTING_FILE)
@click.argument("deck", type=int)
@click.argument("draft", type=EXISTING_FILE)
@operation
def save(collection, deck, draft, pronunciation, recording):
    audio = [(label, path) for label, path in (("Pronunciation", pronunciation), ("Source audio", recording)) if path]
    return collection.save_card(deck, json.loads(draft.read_text(encoding="utf-8")), audio)


@study.command()
@click.argument("card_id", type=int)
@click.argument("revision", type=int)
@click.argument("deck", type=int)
@click.argument("draft", type=EXISTING_FILE)
@operation
def edit(collection, card_id, revision, deck, draft):
    return collection.update_card(card_id, revision, deck, json.loads(draft.read_text(encoding="utf-8")))


@study.command("preview-import")
@click.argument("package", type=EXISTING_FILE)
@operation
def preview_import(collection, package):
    return inspect_package(package)


@study.command("import")
@click.argument("package", type=EXISTING_FILE)
@operation
def import_cards(collection, package):
    return import_package(collection, package)


@study.command("preview-reading-cleanup")
@operation
def preview_cleanup(collection):
    return preview_reading_cleanup(collection)


@study.command("apply-reading-cleanup")
@click.argument("token")
@operation
def apply_cleanup(collection, token):
    return apply_reading_cleanup(collection, token)


@study.command()
@click.argument("new_limit", type=int)
@click.option("--auto-audio/--no-auto-audio", default=False)
@operation
def preferences(collection, new_limit, auto_audio):
    return collection.settings(new_limit, auto_audio)


@study.command()
@click.argument("path", type=DESTINATION)
@operation
def backup(collection, path):
    return collection.backup(path)


@study.command()
@click.argument("path", type=EXISTING_FILE)
@operation
def restore(collection, path):
    return collection.restore(path)


if __name__ == "__main__":
    study()
