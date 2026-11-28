"""Store dictionary headwords as links in a card's Meaning field."""

import re
from html import escape, unescape
from urllib.parse import quote, unquote

_LINK_SEPARATOR = " · "
_SECTION_SEPARATOR = "<br><br>"
_LINK = re.compile(r'<a href="dict://([^"<>]+)">([^<>]+)</a>')


def parse_headwords(text: str) -> list[str]:
    if not isinstance(text, str):
        raise ValueError("Dictionary links must be text.")
    return list(dict.fromkeys(word.strip() for word in re.split(r"[,、\n]", text) if word.strip()))


def with_dictionary_links(words: list[str], body: str) -> str:
    links = _LINK_SEPARATOR.join(f'<a href="dict://{quote(word, safe="")}">{escape(word)}</a>' for word in words)
    return _SECTION_SEPARATOR.join(part for part in (links, body) if part)


def split_dictionary_links(meaning: str) -> tuple[list[str], str]:
    """Recognize Learnit's leading link block without altering other imported markup."""
    section, _, body = meaning.partition(_SECTION_SEPARATOR)
    links = list(_LINK.finditer(section))
    if not links or _LINK_SEPARATOR.join(link[0] for link in links) != section:
        return [], meaning
    words = [unescape(link[2]) for link in links]
    if any(word != unquote(link[1]) for word, link in zip(words, links)):
        return [], meaning
    return words, body
